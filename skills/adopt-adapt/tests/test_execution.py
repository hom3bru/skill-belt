"""Execution receipts are local records, not sandbox or semantic attestations."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import execution  # noqa: E402


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        scratch = SCRIPTS.parent / ".scratch-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.harness = self.root / "harness.py"
        self.harness.write_text("# owned fixture\n", encoding="utf-8")
        self.input = self.root / "input.txt"
        self.input.write_text("fixture", encoding="utf-8")

    def run_python(self, code, **kwargs):
        timeout = kwargs.pop("timeout", 3)
        env_keys = kwargs.pop("env_keys", [])
        return execution.execute(
            self.root / "run", [sys.executable, "-c", code], cwd=self.root,
            harnesses=[self.harness], inputs=[self.input],
            authorization="Run the owned receipt fixture", timeout=timeout,
            env_keys=env_keys, subject="fixture", revision="owned", **kwargs,
        )

    def test_capture_and_verify_derives_counts_from_raw_stdout(self):
        rows = {"checks": [
            {"id": "positive", "kind": "positive", "status": "pass", "detail": "matched"},
            {"id": "control", "kind": "negative-control", "status": "pass", "detail": "wrong answer rejected"},
        ]}
        evidence = self.run_python(f"import json; print({json.dumps(json.dumps(rows))})")
        self.assertEqual(evidence["artifact_kind"], "execution")
        checked = execution.verify_evidence(evidence, self.root / "run", live=True)
        self.assertTrue(checked["eligible"])
        self.assertEqual(checked["run_counts"], {"total": 1, "skipped": 0, "failed": 0})
        self.assertEqual(checked["assertions"], 1)
        self.assertEqual(checked["negative_controls"], 1)

    def test_env_is_allowlisted(self):
        code = "import json, os; print(json.dumps({'checks':[{'id':'p','kind':'positive','status':'pass','detail':os.getenv('EXEC_RECEIPT_SECRET','missing')},{'id':'n','kind':'negative-control','status':'pass','detail':'control'}]}))"
        old = os.environ.get("EXEC_RECEIPT_SECRET")
        os.environ["EXEC_RECEIPT_SECRET"] = "do-not-inherit"
        self.addCleanup(lambda: os.environ.pop("EXEC_RECEIPT_SECRET", None) if old is None else os.environ.__setitem__("EXEC_RECEIPT_SECRET", old))
        evidence = self.run_python(code)
        receipt = execution.verify_evidence(evidence, self.root / "run")
        self.assertEqual(receipt["checks"][0]["detail"], "missing")

    def test_documented_cli_runs_a_scoped_owned_fixture(self):
        code = 'import json; print(json.dumps({"checks":[{"id":"p","kind":"positive","status":"pass","detail":"owned check"},{"id":"n","kind":"negative-control","status":"pass","detail":"wrong value rejected"}]}))'
        run = self.root / 'cli-run'
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'execution.py'), str(run), '--authorization', 'Owned CLI regression', '--cwd', str(self.root), '--timeout', '10', '--harness', str(self.harness), '--input', str(self.input), '--', sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = execution.verify_evidence(json.loads(result.stdout), run)
        self.assertTrue(receipt['eligible'])

    def test_cli_does_not_exit_success_for_a_capture_without_controls(self):
        code = 'print(\'{"checks":[{"id":"p","kind":"positive","status":"pass","detail":"owned check"}]}\')'
        run = self.root / 'cli-ineligible'
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'execution.py'), str(run), '--authorization', 'Owned CLI regression', '--cwd', str(self.root), '--timeout', '10', '--harness', str(self.harness), '--', sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stderr)
        receipt = execution.verify_evidence(json.loads(result.stdout), run)
        self.assertFalse(receipt['eligible'])
        self.assertIn('no passing negative-control', receipt['reason'])

    def test_failure_modes_are_retained_but_ineligible(self):
        cases = [
            ("import sys; print('not json'); sys.exit(0)", "malformed"),
            ("import sys; print('{\"checks\":[]}'); sys.exit(4)", "exit"),
            ("import time; time.sleep(2)", "timeout"),
            ("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"skip\",\"detail\":\"not applicable\",\"reason\":\"not applicable\"}]}')", "all positive checks skipped"),
            ("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"pass\",\"detail\":\"ok\"}]}')", "no passing negative-control"),
            ("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"pass\",\"detail\":\"ok\"},{\"id\":\"n\",\"kind\":\"negative-control\",\"status\":\"skip\",\"detail\":\"not run\",\"reason\":\"missing fixture\"}]}')", "negative-control skipped or failed"),
        ]
        for code, reason in cases:
            with self.subTest(reason=reason):
                evidence = self.run_python(code, timeout=1 if reason == "timeout" else 3)
                receipt = execution.verify_evidence(evidence, self.root / "run")
                self.assertFalse(receipt["eligible"])
                self.assertIn(reason, receipt["reason"])

    def test_duplicate_or_malformed_check_rows_make_receipt_ineligible(self):
        output = {"checks": [
            {"id": "same", "kind": "positive", "status": "pass", "detail": "ok"},
            {"id": "same", "kind": "negative-control", "status": "pass", "detail": "bad rejected"},
        ]}
        evidence = self.run_python(f"print({json.dumps(json.dumps(output))})")
        receipt = execution.verify_evidence(evidence, self.root / "run")
        self.assertFalse(receipt["eligible"])
        self.assertIn("duplicate", receipt["reason"])

    def test_live_verification_detects_changed_harness(self):
        evidence = self.run_python("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"pass\",\"detail\":\"ok\"},{\"id\":\"n\",\"kind\":\"negative-control\",\"status\":\"pass\",\"detail\":\"caught\"}]}')")
        self.harness.write_text("# changed\n", encoding="utf-8")
        with self.assertRaises(execution.Invalid):
            execution.verify_evidence(evidence, self.root / "run", live=True)
        self.assertTrue(execution.verify_evidence(evidence, self.root / "run", live=False)["eligible"])

    def test_receipt_or_log_tampering_is_detected(self):
        evidence = self.run_python("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"pass\",\"detail\":\"ok\"},{\"id\":\"n\",\"kind\":\"negative-control\",\"status\":\"pass\",\"detail\":\"caught\"}]}')")
        receipt = execution.verify_evidence(evidence, self.root / "run")
        log = self.root / "run" / receipt["logs"][0]["path"]
        log.write_bytes(log.read_bytes() + b"tamper")
        with self.assertRaises(execution.Invalid):
            execution.verify_evidence(evidence, self.root / "run", live=False)

    def test_forged_receipt_totals_are_detected(self):
        evidence = self.run_python("print('{\"checks\":[{\"id\":\"p\",\"kind\":\"positive\",\"status\":\"pass\",\"detail\":\"ok\"},{\"id\":\"n\",\"kind\":\"negative-control\",\"status\":\"pass\",\"detail\":\"caught\"}]}')")
        receipt_path = self.root / "run" / evidence["path"]
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        data["run_counts"]["total"] = 900
        receipt_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(execution.Invalid):
            execution.verify_evidence(evidence, self.root / "run", live=False)


if __name__ == "__main__":
    unittest.main()
