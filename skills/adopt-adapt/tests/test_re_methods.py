import unittest

from test_aa import aa, fixture
from pathlib import Path
import tempfile


def claim(method="matching-decompilation", **changes):
    row = {"id": "re1", "claim": "Scoped reconstruction result", "method": method,
           "status": "pass", "scope": "bounded", "verified": True,
           "assertions": 3, "negative_controls": 1, "oracle_kind": "exact",
           "run_counts": {"total": 3, "skipped": 0, "failed": 0},
           "output": "Owned fixture output revision B", "baseline": "Owned fixture revision A",
           "contribution": "Reconstruction of fixture only", "distribution": "Owned synthetic code, no third-party assets",
           "legal_posture": "GREEN owned fixture",
           "provenance": {"tool": "fixture-check", "version": "1", "sha256": "a" * 64, "options": "bounded", "label": "observed"},
           "method_checks": {key: {"status": "pass", "evidence": "Fixture comparison plus wrong-result negative control"} for key in aa.RE_METHOD_CHECKS[method]}}
    if method == "other":
        row["method_reason"] = "Narrow parser investigation"
    row.update(changes)
    return row


class MethodTests(unittest.TestCase):
    def check(self, row):
        aa.check_re_claims({"re_claims": [row]})

    def test_each_method_accepts_complete_scoped_evidence(self):
        for method in aa.RE_METHOD_CHECKS:
            with self.subTest(method=method):
                self.check(claim(method))

    def test_missing_or_ambiguous_method_rejected(self):
        for method in (None, [], "hybrid", "decompile"):
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, "recognised method"):
                self.check(claim(method= "other") | {"method": method})

    def test_missing_required_check_rejected_for_every_method(self):
        for method in aa.RE_METHOD_CHECKS:
            row = claim(method)
            row["method_checks"].pop(next(iter(row["method_checks"])))
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, "method_checks"):
                self.check(row)

    def test_behavioral_success_does_not_prove_matching_bytes(self):
        with self.assertRaisesRegex(ValueError, "exact original-byte"):
            self.check(claim(oracle_kind="behavioral"))

    def test_decoding_bytes_alone_cannot_verify_runtime_behavior(self):
        for method in ("functional-reconstruction", "static-recompilation", "engine-reimplementation", "recovered-source-port"):
            with self.subTest(method=method):
                with self.assertRaisesRegex(ValueError, "behavioral oracle"):
                    self.check(claim(method, oracle_kind="independent-decode"))
                self.check(claim(method, oracle_kind="differential"))

    def test_one_unrun_subsystem_prevents_whole_claim_pass(self):
        row = claim("engine-reimplementation")
        row["method_checks"]["save_script_compatibility"]["status"] = "not-run"
        with self.assertRaisesRegex(ValueError, "every method check"):
            self.check(row)
        row.update(status="unknown", verified=False)
        self.check(row)

    def test_planned_work_can_remain_unexecuted(self):
        row = claim("recovered-source-port", status="not-run", verified=False, assertions=0, negative_controls=0)
        row.pop("run_counts")
        row.pop("oracle_kind")
        for check in row["method_checks"].values():
            check["status"] = "not-run"
        self.check(row)

    def test_hybrid_keeps_matching_and_port_results_separate(self):
        matching = claim()
        port = claim("recovered-source-port", id="port", status="not-run", verified=False)
        for check in port["method_checks"].values():
            check["status"] = "not-run"
        aa.check_re_claims({"re_claims": [matching, port]})
        port.update(status="pass", verified=True)
        with self.assertRaisesRegex(ValueError, "every method check"):
            aa.check_re_claims({"re_claims": [matching, port]})

    def test_duplicate_claim_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate RE"):
            aa.check_re_claims({"re_claims": [claim(), claim()]})

    def test_pass_requires_run_counts_and_executed_checks(self):
        row = claim()
        row.pop("run_counts")
        with self.assertRaisesRegex(ValueError, "requires run_counts"):
            self.check(row)
        row["run_counts"] = {"total": 1, "skipped": 1, "failed": 0}
        row["skip_allowlist"] = ["No compatible host"]
        with self.assertRaisesRegex(ValueError, "all-skipped"):
            self.check(row)

    def test_unverified_pass_cannot_evade_oracle_or_negative_control(self):
        with self.assertRaisesRegex(ValueError, "discriminating oracle"):
            self.check(claim(verified=False, oracle_kind="recompile-only"))
        with self.assertRaisesRegex(ValueError, "negative control"):
            self.check(claim(verified=False, negative_controls=0))

    def test_lineage_and_distribution_cannot_be_omitted(self):
        for key in ("output", "baseline", "contribution", "distribution"):
            row = claim()
            row.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "method contract"):
                self.check(row)

    def test_other_requires_reason(self):
        row = claim("other")
        row.pop("method_reason")
        with self.assertRaisesRegex(ValueError, "other method"):
            self.check(row)

    def test_progress_requires_real_denominator_and_exclusions(self):
        progress = {"numerator": 10, "denominator": 12, "unit": "functions", "basis": "revision A function inventory", "exclusions": ["2 assembly primitives"]}
        self.check(claim(progress=progress))
        for changes in ({"denominator": 0}, {"numerator": 13}, {"numerator": True}, {"basis": ""}, {"exclusions": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(claim(progress=progress | changes))

    def test_optional_unrun_metrics_render_without_crashing(self):
        row = claim(status="unknown", verified=False, run_counts=None, progress=None)
        self.check(row)
        self.assertIn("Runs: not supplied", aa.render_re_claim(row))
        with self.assertRaisesRegex(ValueError, "skip_allowlist"):
            self.check(row | {"skip_allowlist": None})

    def test_validated_contract_is_visible_before_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            run, record = fixture(Path(directory))
            from test_evidence_workflow import attach_execution
            row = claim()
            attach_execution(run, record, row)
            record["items"][0]["ledger"]["re_claims"] = [row]
            output = aa.render(record, run)
            for text in ("matching-decompilation", "original_bytes", "Owned fixture revision A", "Owned synthetic code", "Oracle: exact", "verified: True", "total 3, skipped 0, failed 0", row["provenance"]["sha256"], "options: bounded"):
                self.assertIn(text, output)
                self.assertLess(output.index(text), output.index("aa:verdict:q1"))


if __name__ == "__main__":
    unittest.main()
