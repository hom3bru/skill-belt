"""Behavioral checks for the descriptive comparison helper; no model or candidate execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare.py"
spec = importlib.util.spec_from_file_location("ror_compare", SCRIPT)
compare_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_module)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.cases = {
            "schema_version": 1, "task_id": "example",
            "oracle": {"kind": "synthetic", "source": "authored fixture",
                       "independent_of_candidate": True},
            "cases": [
                {"id": "a", "group_id": "one", "stratum": "ordinary",
                 "expectation": {"status": "answered", "output": "東京"}},
                {"id": "b", "group_id": "one", "stratum": "ordinary",
                 "expectation": {"status": "answered", "output": 1}},
                {"id": "c", "group_id": "two", "stratum": "missing-evidence",
                 "expectation": {"status": "abstained"}},
            ],
        }

    def arm(self, name, rows):
        return {"schema_version": 1, "case_set_sha256": self.digest,
                "arm_id": name, "records": rows}

    def report(self, candidate, baseline=None):
        baseline = baseline if baseline is not None else [
            {"case_id": "a", "status": "answered", "output": "東京"},
            {"case_id": "b", "status": "answered", "output": 1},
            {"case_id": "c", "status": "abstained"},
        ]
        return compare_module.compare_records(
            self.cases, self.arm("baseline", baseline),
            self.arm("candidate", candidate), self.digest)

    def test_unicode_and_appropriate_abstention(self):
        report = self.report([
            {"case_id": "a", "status": "answered", "output": "東京"},
            {"case_id": "b", "status": "answered", "output": 1},
            {"case_id": "c", "status": "abstained"},
        ])
        self.assertEqual(report["candidate"]["correct"], 3)
        self.assertEqual(report["candidate"]["answered"], 2)
        self.assertEqual(report["candidate"]["answer_precision"], 1.0)
        self.assertEqual(report["candidate"]["group_all_correct"], 2)

    def test_boolean_is_not_numeric_one(self):
        report = self.report([
            {"case_id": "b", "status": "answered", "output": True}
        ])
        self.assertEqual(report["candidate"]["correct"], 0)
        self.assertEqual(report["candidate"]["incorrect_answered"], 1)

    def test_missing_predictions_stay_in_denominator(self):
        report = self.report([])
        self.assertEqual(report["candidate"]["eligible"], 3)
        self.assertEqual(report["candidate"]["missing"], 3)
        self.assertEqual(report["candidate"]["accuracy"], 0.0)
        self.assertEqual(report["paired"]["baseline_only_correct"], 3)

    def test_errors_and_abstention_do_not_hide_answer_failures(self):
        report = self.report([
            {"case_id": "a", "status": "error", "error": "runtime failed"},
            {"case_id": "b", "status": "abstained"},
            {"case_id": "c", "status": "abstained"},
        ])
        self.assertEqual(report["candidate"]["correct"], 1)
        self.assertEqual(report["candidate"]["errors"], 1)
        self.assertEqual(report["candidate"]["coverage"], 0.0)

    def test_paired_wins_losses_and_groups(self):
        report = self.report(
            [{"case_id": "a", "status": "answered", "output": "東京"},
             {"case_id": "b", "status": "answered", "output": 2},
             {"case_id": "c", "status": "abstained"}],
            [{"case_id": "a", "status": "error"},
             {"case_id": "b", "status": "answered", "output": 1},
             {"case_id": "c", "status": "abstained"}])
        self.assertEqual(report["paired"]["candidate_only_correct"], 1)
        self.assertEqual(report["paired"]["baseline_only_correct"], 1)
        self.assertEqual(report["candidate"]["group_all_correct"], 1)

    def test_unknown_measurements_remain_unknown(self):
        report = self.report([
            {"case_id": "a", "status": "answered", "output": "東京",
             "runtime_llm_calls": 0, "cost_usd": 0.0},
            {"case_id": "b", "status": "answered", "output": 1},
            {"case_id": "c", "status": "abstained"},
        ])
        self.assertIsNone(report["candidate"]["measurements"]["cost_usd"]["total"])
        self.assertEqual(report["candidate"]["measurements"]["cost_usd"]["reported_cases"], 1)
        self.assertEqual(report["candidate"]["measurements"]["cost_usd"]["reported_sum"], 0.0)
        self.assertFalse(report["runtime_model_freedom_verified"])

    def test_complete_measurement_totals(self):
        rows = [{"case_id": key, "status": "abstained", "cost_usd": 0.25,
                 "latency_ms": 2.0, "runtime_llm_calls": 0}
                for key in ("a", "b", "c")]
        report = self.report(rows)
        self.assertEqual(report["candidate"]["measurements"]["cost_usd"]["total"], 0.75)
        self.assertEqual(report["candidate"]["measurements"]["runtime_llm_calls"]["total"], 0)

    def test_duplicate_and_unknown_predictions_refused(self):
        for rows in (
            [{"case_id": "a", "status": "error"}, {"case_id": "a", "status": "error"}],
            [{"case_id": "unknown", "status": "error"}],
        ):
            with self.subTest(rows=rows), self.assertRaises(compare_module.InputError):
                self.report(rows)

    def test_duplicate_case_and_empty_case_set_refused(self):
        self.cases["cases"].append(dict(self.cases["cases"][0]))
        with self.assertRaises(compare_module.InputError):
            self.report([])
        self.cases["cases"] = []
        with self.assertRaises(compare_module.InputError):
            self.report([])

    def test_snapshot_mismatch_and_identical_arm_identity_refused(self):
        baseline = self.arm("same", [])
        candidate = self.arm("other", [])
        candidate["case_set_sha256"] = "b" * 64
        with self.assertRaises(compare_module.InputError):
            compare_module.compare_records(self.cases, baseline, candidate, self.digest)
        candidate["case_set_sha256"] = self.digest
        candidate["arm_id"] = "same"
        with self.assertRaises(compare_module.InputError):
            compare_module.compare_records(self.cases, baseline, candidate, self.digest)

    def test_invalid_measurements_and_unknown_fields_refused(self):
        for extra in ({"cost_usd": -1}, {"latency_ms": float("inf")},
                      {"runtime_llm_calls": True}, {"runtime_llm_calls": 1.5},
                      {"ignored_failure": True}):
            with self.subTest(extra=extra), self.assertRaises(compare_module.InputError):
                self.report([{"case_id": "a", "status": "error", **extra}])

    def test_answered_requires_output_and_nonanswers_forbid_it(self):
        for row in ({"case_id": "a", "status": "answered"},
                    {"case_id": "a", "status": "error", "output": None}):
            with self.subTest(row=row), self.assertRaises(compare_module.InputError):
                self.report([row])

    def test_output_order_is_irrelevant_but_array_order_is_not(self):
        self.cases["cases"][0]["expectation"]["output"] = {"x": 1, "y": [1, 2]}
        report = self.report([{"case_id": "a", "status": "answered",
                               "output": {"y": [1, 2], "x": 1}}])
        self.assertEqual(report["candidate"]["correct"], 1)
        report = self.report([{"case_id": "a", "status": "answered",
                               "output": {"y": [2, 1], "x": 1}}])
        self.assertEqual(report["candidate"]["correct"], 0)

    def test_nested_nonfinite_and_unsupported_schema_refused(self):
        self.cases["cases"][0]["expectation"]["output"] = {"x": float("nan")}
        with self.assertRaises(compare_module.InputError):
            self.report([])
        self.cases["cases"][0]["expectation"]["output"] = "valid"
        self.cases["schema_version"] = 2
        with self.assertRaises(compare_module.InputError):
            self.report([])

    def test_duplicate_json_keys_refused_and_size_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"x": 1, "x": 2}', encoding="utf-8")
            with self.assertRaises(compare_module.InputError):
                compare_module.load_json(path)
            path.write_bytes(b" " * (compare_module.MAX_BYTES + 1))
            with self.assertRaises(compare_module.InputError):
                compare_module.load_json(path)

    def test_cli_hash_and_descriptive_exit_status_without_input_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            raw = json.dumps(self.cases, ensure_ascii=False).encode("utf-8")
            cases.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            baseline = self.arm("baseline", [])
            candidate = self.arm("candidate", [])
            baseline["case_set_sha256"] = digest
            candidate["case_set_sha256"] = digest
            for name, value in (("baseline", baseline), ("candidate", candidate)):
                (root / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "hash", str(cases)],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["case_set_sha256"], digest)
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "compare", "--cases", str(cases),
                 "--baseline", str(root / "baseline.json"),
                 "--candidate", str(root / "candidate.json")],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["candidate"]["accuracy"], 0.0)
            self.assertEqual(cases.read_bytes(), raw)

    def test_teacher_labels_are_not_independent_truth(self):
        self.cases["oracle"] = {"kind": "teacher", "source": "recorded model",
                                "independent_of_candidate": False}
        report = self.report([])
        self.assertEqual(report["evidence_scope"], "descriptive-authored-records")
        self.assertEqual(report["oracle"]["kind"], "teacher")
        self.assertFalse(report["oracle_provenance_verified"])

    def test_invalid_unicode_and_extreme_numbers_are_input_errors(self):
        self.cases["task_id"] = "\ud800"
        with self.assertRaises(compare_module.InputError):
            self.report([])
        self.cases["task_id"] = "valid"
        with self.assertRaises(compare_module.InputError):
            self.report([{"case_id": "a", "status": "error", "latency_ms": 10 ** 1000}])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large-number.json"
            path.write_text('{"number": ' + '9' * 5000 + '}', encoding="utf-8")
            with self.assertRaises(compare_module.InputError):
                compare_module.load_json(path)


    def test_decimal_tokens_are_not_rounded_before_output_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "number.json"
            for expected, actual in (
                ("9007199254740993.0", "9007199254740992.0"),
                ("0.10000000000000001", "0.1"),
                ("1.0", "1.00"), ("1", "1.0"),
                ("1e400", "1e401"),
            ):
                with self.subTest(expected=expected, actual=actual):
                    path.write_text(expected, encoding="utf-8")
                    wanted, _ = compare_module.load_json(path)
                    path.write_text(actual, encoding="utf-8")
                    got, _ = compare_module.load_json(path)
                    self.cases["cases"][0]["expectation"]["output"] = {"nested": [wanted]}
                    report = self.report([{"case_id": "a", "status": "answered",
                                           "output": {"nested": [got]}}])
                    self.assertEqual(report["candidate"]["correct"], 0)
                    report = self.report([{"case_id": "a", "status": "answered",
                                           "output": {"nested": [wanted]}}])
                    self.assertEqual(report["candidate"]["correct"], 1)

    def test_decoded_decimal_measurements_are_finite_and_do_not_mutate_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "measurement.json"
            path.write_text('{"latency_ms": 2.5, "cost_usd": 0.125}', encoding="utf-8")
            metrics, _ = compare_module.load_json(path)
            row = {"case_id": "a", "status": "answered", "output": "東京", **metrics}
            before = dict(row)
            report = self.report([row])
            self.assertEqual(report["candidate"]["measurements"]["latency_ms"]["reported_sum"], 2.5)
            self.assertEqual(report["candidate"]["measurements"]["cost_usd"]["reported_sum"], 0.125)
            self.assertEqual(row, before)
            path.write_text('{"latency_ms": 1e400}', encoding="utf-8")
            metrics, _ = compare_module.load_json(path)
            with self.assertRaises(compare_module.InputError):
                self.report([{"case_id": "a", "status": "error", **metrics}])
            path.write_text('{"cost_usd": -1e-400}', encoding="utf-8")
            metrics, _ = compare_module.load_json(path)
            with self.assertRaises(compare_module.InputError):
                self.report([{"case_id": "a", "status": "error", **metrics}])
            path.write_text('{"runtime_llm_calls": 1.0}', encoding="utf-8")
            metrics, _ = compare_module.load_json(path)
            with self.assertRaises(compare_module.InputError):
                self.report([{"case_id": "a", "status": "error", **metrics}])


if __name__ == "__main__":
    unittest.main()
