"""Efficient checked operations preserve evidence, freshness and pilot outcomes."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from gate_fixtures import aa, measured_counter, recapture_donor, v2_fixture


class EfficientCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.record, self.intake = v2_fixture(self.root)

    def save(self):
        aa.save(self.run / "run.json", self.record)
        aa.save(self.run / "intake.json", self.intake)

    def report(self):
        return self.run / "report.md"


class ParsingTests(EfficientCase):
    def test_each_capture_is_parsed_once_with_many_accounted_links(self):
        links = [f"https://example.test/navigation/{i}" for i in range(120)]
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "Owned source navigation fixture.\n" + "\n".join(links), kind="docs")
        evidence = self.record["evidence"][0]["id"]
        self.intake["artifacts"][0]["links"] = [
            {"url": url, "resolved": url, "source": None, "classification": "non-research",
             "evidence": [evidence], "reason": "Owned navigation-only parser fixture."} for url in links]
        self.save()
        gates = aa.gates_module()
        with mock.patch.object(gates, "urls", wraps=gates.urls) as parser:
            status = aa.contract_status(self.record, self.run)
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(len(status["links"]), len(links))
        self.assertFalse(any("unaccounted" in row for row in status["outstanding"]))

    def test_repeated_coverage_roles_share_usable_content_inspection(self):
        node = self.intake["artifacts"][0]
        node["coverage"].update({name: dict(node["coverage"]["body"]) for name in ("extra-a", "extra-b", "extra-c")})
        self.save()
        gates = aa.gates_module()
        with mock.patch.object(gates, "_usable", wraps=gates._usable) as usable:
            self.assertEqual(aa.validate(self.record, self.run), [])
        self.assertEqual(usable.call_count, 1)

    def test_read_cache_overflow_rereads_and_checks_bytes_without_rejecting_size(self):
        path = self.run / "large.txt"
        path.write_bytes(b"first")
        reads = aa._ReadSet(self.run)
        reads.CACHE_BYTES = 3
        self.assertEqual(reads.read("large.txt"), b"first")
        self.assertEqual(reads.read("large.txt"), b"first")
        self.assertEqual(reads.cached_bytes, 0)
        path.write_bytes(b"other")
        with self.assertRaisesRegex(aa.Invalid, "changed during operation"):
            reads.read("large.txt")

    def test_next_public_operation_does_not_reuse_evidence_cache(self):
        self.save()
        self.assertEqual(aa.validate(self.record, self.run), [])
        capture = self.run / self.record["evidence"][0]["path"]
        capture.write_bytes(b"Changed after the first operation.")
        self.assertRegex(" ".join(aa.validate(self.record, self.run)), "byte/hash mismatch")

    def test_next_public_operation_rechecks_inputs_intake_and_recipient(self):
        self.save()
        self.assertEqual(aa.validate(self.record, self.run), [])
        files = [(self.run / "inputs.json", b"{}"), (self.run / "intake.json", b"{}"),
                 (self.root / "recipient/entry.py", b"def changed(): pass\n")]
        for path, changed in files:
            with self.subTest(path=path.name):
                before = path.read_bytes()
                path.write_bytes(changed)
                self.assertTrue(aa.validate(self.record, self.run))
                path.write_bytes(before)
        self.assertEqual(aa.validate(self.record, self.run), [])


class CliPassTests(EfficientCase):
    def test_read_commands_run_core_validation_once(self):
        self.save()
        aa.record_readback(self.run / "run.json")
        self.report().write_text(aa.render(self.record, self.run), encoding="utf-8")
        commands = [("validate",), ("status",), ("render", "--output", str(self.run / "other.md")),
                    ("check-output", str(self.report())),
                    ("history", "--ledger", str(self.run / "history.jsonl"), "--published-report", str(self.report()))]
        for command in commands:
            with self.subTest(command=command[0]):
                with mock.patch.object(aa, "_validate", wraps=aa._validate) as core:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = aa.main([command[0], str(self.run / "run.json"), *command[1:]])
                self.assertEqual(result, 0)
                self.assertEqual(core.call_count, 1)

    def test_cli_commands_reject_capture_mutation_after_first_checked_context(self):
        self.save()
        aa.record_readback(self.run / "run.json")
        self.report().write_text(aa.render(self.record, self.run), encoding="utf-8")
        capture = self.run / self.record["evidence"][0]["path"]
        before = capture.read_bytes()
        output = self.run / "new.md"
        history = self.run / "history.jsonl"
        commands = [("validate", "--complete"), ("status",),
                    ("render", "--complete", "--output", str(output)),
                    ("check-output", str(self.report()), "--complete"),
                    ("history", "--ledger", str(history), "--published-report", str(self.report()))]
        gates = aa.gates_module()
        original = gates.check
        for command in commands:
            with self.subTest(command=command[0]):
                def mutate_after_check(*args, **kwargs):
                    status = original(*args, **kwargs)
                    capture.write_bytes(b"mutated after the checked context was returned")
                    return status
                with mock.patch.object(gates, "check", side_effect=mutate_after_check):
                    with mock.patch.object(aa, "_validate", wraps=aa._validate) as core:
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
                            result = aa.main([command[0], str(self.run / "run.json"), *command[1:]])
                self.assertEqual(result, 2)
                self.assertIn("changed during operation", errors.getvalue())
                self.assertEqual(core.call_count, 1)
                self.assertFalse(output.exists())
                self.assertFalse(history.exists())
                capture.write_bytes(before)

    def test_historical_cli_skips_live_recipient_guard_but_still_guards_captures(self):
        self.save()
        aa.record_readback(self.run / "run.json")
        gates = aa.gates_module()
        original = gates.check
        recipient = self.root / "recipient/entry.py"
        def changed_live_recipient(*args, **kwargs):
            status = original(*args, **kwargs)
            recipient.write_bytes(b"a different current recipient revision")
            return status
        with mock.patch.object(gates, "check", side_effect=changed_live_recipient):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = aa.main(["validate", str(self.run / "run.json"), "--historical"])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output.getvalue())["live_recipient_checked"])
        self.assertTrue(aa.validate(self.record, self.run))
        capture = self.run / self.record["evidence"][0]["path"]
        def changed_capture(*args, **kwargs):
            status = original(*args, **kwargs)
            capture.write_bytes(b"invalid historical capture")
            return status
        with mock.patch.object(gates, "check", side_effect=changed_capture):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = aa.main(["validate", str(self.run / "run.json"), "--historical"])
        self.assertEqual(result, 2)

    def test_render_checks_again_after_writing_without_reparsing_ledger(self):
        self.save()
        output = self.run / "rendered.md"
        capture = self.run / self.record["evidence"][0]["path"]
        original = Path.read_bytes
        def mutate_after_report_read(path):
            data = original(path)
            if path == output:
                capture.write_bytes(b"changed while the report was written")
            return data
        with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=mutate_after_report_read):
            with mock.patch.object(aa, "_validate", wraps=aa._validate) as core:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = aa.main(["render", str(self.run / "run.json"), "--output", str(output)])
        self.assertEqual(result, 2)
        self.assertEqual(core.call_count, 1)
        self.assertFalse(output.exists())


class FinalizeTests(EfficientCase):
    def test_finalize_checks_once_and_retains_unknown_cost_and_both_recipients(self):
        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.record, self.intake = v2_fixture(self.root, two_recipients=True)
        row = {"id": "unknown-cost", "status": "unknown", "metric": "runtime-cost", "unit": "USD",
               "scope": "No runtime comparison executed.", "note": "Missing measurements are not negative evidence."}
        first = self.record["items"][0]
        first["ledger"]["measurements"] = [row]
        first["decision"]["basis"]["measurements"] = [row["id"]]
        self.save()
        before = (self.run / "run.json").read_bytes()
        with mock.patch.object(aa, "_validate", wraps=aa._validate) as core:
            result = aa.finalize(self.run / "run.json", self.report(), complete=True)
        self.assertEqual(core.call_count, 1)
        self.assertEqual((self.run / "run.json").read_bytes(), before)
        self.assertTrue(result["contract"]["complete"])
        self.assertEqual(len(result["contract"]["coverage"]), 2)
        self.assertEqual(result["contract"]["retained_leads"], 1)
        self.assertIn("Measurement (unknown)", self.report().read_text(encoding="utf-8"))
        self.assertIn("Experiment (not executed)", self.report().read_text(encoding="utf-8"))
        self.assertEqual(self.report().read_text(encoding="utf-8"), aa.render(self.record, self.run, complete=True))
        self.assertEqual(first["decision"]["result"], "ADAPT-with-prerequisite")

    def test_incomplete_finalize_stays_available_and_complete_refuses_without_writes(self):
        queued = self.root / "queued"
        record = aa.init_run(queued, ["https://example.test/unread"], ["recipient=generic"])
        before = (queued / "intake.json").read_bytes()
        with self.assertRaisesRegex((aa.Invalid, ValueError), "complete coverage gate"):
            aa.finalize(queued / "run.json", queued / "complete.md", complete=True)
        self.assertFalse((queued / "complete.md").exists())
        self.assertEqual((queued / "intake.json").read_bytes(), before)
        result = aa.finalize(queued / "run.json", queued / "partial.md")
        self.assertFalse(result["contract"]["complete"])
        self.assertEqual(record["items"][0]["state"], "QUEUED")
        self.assertIn("no verdict", (queued / "partial.md").read_text(encoding="utf-8"))

    def test_existing_output_or_output_appearing_during_preparation_is_preserved(self):
        self.save()
        original = aa._render_checked
        def operator_output(*args):
            report = original(*args)
            self.report().write_bytes(b"operator output")
            return report
        with mock.patch.object(aa, "_render_checked", side_effect=operator_output):
            with self.assertRaises(FileExistsError):
                aa.finalize(self.run / "run.json", self.report())
        self.assertEqual(self.report().read_bytes(), b"operator output")
        with self.assertRaisesRegex(aa.Invalid, "output exists"):
            aa.finalize(self.run / "run.json", self.report())

    def test_changed_capture_or_recipient_during_render_rejects_before_writes(self):
        self.save()
        original = aa._render_checked
        for path in (self.run / self.record["evidence"][0]["path"], self.root / "recipient/entry.py"):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                intake = (self.run / "intake.json").read_bytes()
                def mutate(*args):
                    report = original(*args)
                    path.write_bytes(b"changed during render")
                    return report
                with mock.patch.object(aa, "_render_checked", side_effect=mutate):
                    with self.assertRaisesRegex(aa.Invalid, "changed|stale"):
                        aa.finalize(self.run / "run.json", self.report())
                self.assertFalse(self.report().exists())
                self.assertEqual((self.run / "intake.json").read_bytes(), intake)
                path.write_bytes(before)

    def test_changed_execution_inputs_and_logs_reject_before_success(self):
        row, evidence = measured_counter(self.run, self.record)
        self.save()
        receipt = aa.load(self.run / evidence["path"])
        paths = [Path(receipt["inputs"][0]["path"]), self.run / receipt["logs"][0]["path"]]
        original = aa._render_checked
        for path in paths:
            with self.subTest(path=path.name):
                before = path.read_bytes()
                def mutate(*args):
                    report = original(*args)
                    path.write_bytes(b"changed during finalization")
                    return report
                with mock.patch.object(aa, "_render_checked", side_effect=mutate):
                    with self.assertRaises(ValueError):
                        aa.finalize(self.run / "run.json", self.report())
                self.assertFalse(self.report().exists())
                path.write_bytes(before)

    def test_post_write_dependency_change_restores_receipt_and_removes_owned_report(self):
        self.save()
        intake = (self.run / "intake.json").read_bytes()
        original = aa.save
        def mutate(path, value):
            original(path, value)
            (self.run / self.record["evidence"][0]["path"]).write_bytes(b"concurrent capture edit")
        with mock.patch.object(aa, "save", side_effect=mutate):
            with self.assertRaisesRegex(aa.Invalid, "changed"):
                aa.finalize(self.run / "run.json", self.report())
        self.assertEqual((self.run / "intake.json").read_bytes(), intake)
        self.assertFalse(self.report().exists())

    def test_post_write_exception_recovers_exact_prior_receipt_bytes(self):
        self.save()
        intake = (self.run / "intake.json").read_bytes()
        original = aa.save
        def fail_after_write(path, value):
            original(path, value)
            raise OSError("injected after successful receipt write")
        with mock.patch.object(aa, "save", side_effect=fail_after_write):
            with self.assertRaisesRegex(OSError, "injected"):
                aa.finalize(self.run / "run.json", self.report())
        self.assertEqual((self.run / "intake.json").read_bytes(), intake)
        self.assertFalse(self.report().exists())

    def test_concurrent_report_edit_survives_failed_finalization(self):
        self.save()
        original = aa.save
        def mutate_report(path, value):
            original(path, value)
            self.report().write_bytes(b"operator report edit")
        with mock.patch.object(aa, "save", side_effect=mutate_report):
            with self.assertRaisesRegex(aa.Invalid, "report bytes changed"):
                aa.finalize(self.run / "run.json", self.report())
        self.assertEqual(self.report().read_bytes(), b"operator report edit")

    def test_concurrent_intake_edit_is_preserved(self):
        self.save()
        original = aa._check_rendering
        changed = b'{"operator":"concurrent intake edit"}\n'
        def mutate_intake(*args):
            result = original(*args)
            (self.run / "intake.json").write_bytes(changed)
            return result
        with mock.patch.object(aa, "_check_rendering", side_effect=mutate_intake):
            with self.assertRaisesRegex(aa.Invalid, "changed"):
                aa.finalize(self.run / "run.json", self.report())
        self.assertEqual((self.run / "intake.json").read_bytes(), changed)
        self.assertFalse(self.report().exists())

    def test_index_receipt_remains_bound_to_actual_saved_record(self):
        self.save()
        index = self.run / "index.json"
        aa.save(index, {"record_sha256": aa.digest((self.run / "run.json").read_bytes()),
                        "source_ids": [s["id"] for s in self.record["sources"]],
                        "item_ids": [i["id"] for i in self.record["items"]]})
        result = aa.finalize(self.run / "run.json", self.report(), complete=True, index=index)
        self.assertEqual(result["recording"]["state"], "indexed")
        self.assertEqual(aa.validate(self.record, self.run, complete=True), [])


if __name__ == "__main__":
    unittest.main()
