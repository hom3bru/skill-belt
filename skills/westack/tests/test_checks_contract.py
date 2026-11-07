"""The output shape of checks.py `parse` that other skills read.

westack-tdd's scripts/controls.py (judge) classifies a broken copy from checks.py's parse of saved runner
output, and relies on exactly these things: the result and per-test field names (`runner`, `tests`, `counts`,
`complete`, `warnings`, and each test's `name`, `status`, `raw_status`, `flaky`), `raw_status` telling an
assertion failure apart from an error, the " (collection)" suffix on a pytest collection error, the
"_FailedTest" marker on a unittest import failure, and an incomplete run being flagged when the failing
module is not parsed as a test. If checks.py changes any of these, controls.py would misjudge a copy (an
import failure counted as a kill, an error as an assertion failure), so these tests fail first and name what
to change in both places. Inputs are samples of each runner's real output format; nothing is run. One test also
pins the core rule behind judge's default of two kills: references/evidence.md asks for at least two distinct
broken copies per detection claim.
"""
import hashlib
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest

import test_westack as fixtures

SCRIPT =fixtures.ROOT / "scripts" / "checks.py"
RESULT_KEYS = {"format", "kind", "runner", "tests", "counts", "reported", "complete", "warnings"}
TEST_KEYS = {"name", "status", "raw_status", "occurrences", "flaky"}
COUNT_KEYS = {"parsed", "passed", "failed", "skipped"}

UNITTEST_MIXED = """\
test_bad (tests.test_ok.T.test_bad) ... FAIL
test_err (tests.test_ok.T.test_err) ... ERROR
test_one (tests.test_ok.T.test_one) ... ok
test_skip (tests.test_ok.T.test_skip) ... skipped 'why'

======================================================================
ERROR: test_err (tests.test_ok.T.test_err)
----------------------------------------------------------------------
Traceback (most recent call last):
ValueError: x

======================================================================
FAIL: test_bad (tests.test_ok.T.test_bad)
----------------------------------------------------------------------
Traceback (most recent call last):
AssertionError: 1 != 2

----------------------------------------------------------------------
Ran 4 tests in 0.004s

FAILED (failures=1, errors=1, skipped=1)
"""

# `python -m unittest discover -v` with a top-level test module that fails to import.
UNITTEST_IMPORT_FAILURE = """\
test_broken (unittest.loader._FailedTest.test_broken) ... ERROR
test_one (test_ok.T.test_one) ... ok

======================================================================
ERROR: test_broken (unittest.loader._FailedTest.test_broken)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_broken
Traceback (most recent call last):
ModuleNotFoundError: No module named 'nonexistent_module_xyz'

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (errors=1)
"""

# The same failure inside a package (Python 3.14 output): the dotted name is not a `name (id)` line.
UNITTEST_PACKAGE_IMPORT_FAILURE = """\
tests.test_broken (unittest.loader._FailedTest.tests.test_broken) ... ERROR
test_one (tests.test_ok.T.test_one) ... ok

======================================================================
ERROR: tests.test_broken (unittest.loader._FailedTest.tests.test_broken)
----------------------------------------------------------------------
ImportError: Failed to import test module: tests.test_broken
Traceback (most recent call last):
ModuleNotFoundError: No module named 'nonexistent_module_xyz'

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (errors=1)
"""

PYTEST = """\
tests/test_a.py::test_bad FAILED                                         [ 25%]
tests/test_a.py::test_err ERROR                                          [ 50%]
tests/test_a.py::test_ok PASSED                                          [ 75%]
tests/test_b.py::test_skipped SKIPPED (why)                              [100%]
=========================== short test summary info ============================
FAILED tests/test_a.py::test_bad - assert 1 == 2
ERROR tests/test_a.py::test_err - ValueError: x
ERROR tests/test_c.py - ModuleNotFoundError: No module named 'x'
======= 1 failed, 1 passed, 1 skipped, 2 errors in 0.12s =======
"""


def load_checks():
    spec = importlib.util.spec_from_file_location("westack_checks_contract_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checks = load_checks()


def by_name(result):
    return {t["name"]: t for t in result["tests"]}


class ResultShapeTests(unittest.TestCase):
    def test_a_parse_result_carries_the_fields_controls_reads(self):
        for sample in (UNITTEST_MIXED, PYTEST):
            with self.subTest(runner=checks.parse_text(sample)["runner"]):
                result = checks.parse_text(sample)
                self.assertGreaterEqual(set(result), RESULT_KEYS)
                self.assertEqual((result["format"], result["kind"]), ("westack-checks-1", "parse"))
                self.assertEqual(set(result["counts"]), COUNT_KEYS)
                self.assertIsInstance(result["complete"], bool)
                self.assertIsInstance(result["warnings"], list)

    def test_every_test_carries_name_status_raw_status_and_flaky(self):
        for sample in (UNITTEST_MIXED, PYTEST):
            for test in checks.parse_text(sample)["tests"]:
                with self.subTest(test=test["name"]):
                    self.assertGreaterEqual(set(test), TEST_KEYS)
                    self.assertIn(test["status"], {"passed", "failed", "skipped"})
                    self.assertIsInstance(test["raw_status"], str)
                    self.assertIsInstance(test["flaky"], bool)

    def test_the_runner_is_named_and_a_complete_run_says_so(self):
        unittest_result = checks.parse_text(UNITTEST_MIXED)
        self.assertEqual((unittest_result["runner"], unittest_result["complete"]), ("unittest", True))
        self.assertEqual(unittest_result["counts"], {"parsed": 4, "passed": 1, "failed": 2, "skipped": 1})
        pytest_result = checks.parse_text(PYTEST)
        self.assertEqual((pytest_result["runner"], pytest_result["complete"]), ("pytest", True))

    def test_unrecognised_output_is_unknown_with_no_tests_and_not_complete(self):
        result = checks.parse_text("Everything is fine, honest.\n")
        self.assertEqual((result["runner"], result["tests"], result["complete"]), ("unknown", [], False))

    def test_a_run_cut_short_is_not_complete(self):
        cut = "\n".join(UNITTEST_MIXED.splitlines()[:3]) + "\n"
        result = checks.parse_text(cut)
        self.assertFalse(result["complete"])
        self.assertTrue(result["warnings"])


class RawStatusTests(unittest.TestCase):
    """judge counts a failure as an assertion kill unless every failed test's raw_status is exactly "ERROR"."""

    def test_unittest_tells_an_assertion_failure_from_an_error(self):
        tests = by_name(checks.parse_text(UNITTEST_MIXED))
        bad, err = tests["tests.test_ok.T.test_bad"], tests["tests.test_ok.T.test_err"]
        self.assertEqual((bad["status"], bad["raw_status"]), ("failed", "FAIL"))
        self.assertEqual((err["status"], err["raw_status"]), ("failed", "ERROR"))

    def test_unittest_progress_lines_alone_still_tell_them_apart(self):
        # the failure blocks and the "Ran N tests" line may be cut off or filtered out; the verdict is then
        # incomplete, but the two raw statuses must not collapse
        text = "test_bad (m.T.test_bad) ... FAIL\ntest_err (m.T.test_err) ... ERROR\n"
        result = checks.parse_text(text)
        tests = by_name(result)
        self.assertEqual((tests["m.T.test_bad"]["raw_status"], tests["m.T.test_err"]["raw_status"]), ("FAIL", "ERROR"))
        self.assertFalse(result["complete"])

    def test_pytest_tells_an_assertion_failure_from_an_error(self):
        tests = by_name(checks.parse_text(PYTEST))
        bad, err = tests["tests/test_a.py::test_bad"], tests["tests/test_a.py::test_err"]
        self.assertEqual((bad["status"], bad["raw_status"]), ("failed", "FAILED"))
        self.assertEqual((err["status"], err["raw_status"]), ("failed", "ERROR"))

    def test_a_skip_and_a_pass_are_not_failures(self):
        tests = by_name(checks.parse_text(UNITTEST_MIXED))
        self.assertEqual(tests["tests.test_ok.T.test_skip"]["status"], "skipped")
        self.assertEqual(tests["tests.test_ok.T.test_one"]["status"], "passed")

    def test_a_test_seen_both_passing_and_failing_is_flaky_and_failed(self):
        text = "test_a (m.T.test_a) ... ok\ntest_a (m.T.test_a) ... FAIL\n\nRan 2 tests in 0.001s\n\nFAILED (failures=1)\n"
        test = by_name(checks.parse_text(text))["m.T.test_a"]
        self.assertEqual((test["status"], test["flaky"], test["occurrences"]), ("failed", True, 2))


class LoadFailureTests(unittest.TestCase):
    """A module that fails to load must never read as a clean kill."""

    def test_a_pytest_collection_error_is_a_failed_test_with_the_collection_suffix(self):
        tests = by_name(checks.parse_text(PYTEST))
        collected = [t for name, t in tests.items() if name.endswith(" (collection)")]
        self.assertEqual([t["name"] for t in collected], ["tests/test_c.py (collection)"])
        self.assertEqual((collected[0]["status"], collected[0]["raw_status"]), ("failed", "ERROR"))

    def test_a_top_level_unittest_import_failure_is_named_with_the_failed_test_marker(self):
        result = checks.parse_text(UNITTEST_IMPORT_FAILURE)
        broken = [t for t in result["tests"] if "_FailedTest" in t["name"]]
        self.assertEqual([t["name"] for t in broken], ["unittest.loader._FailedTest.test_broken"])
        self.assertEqual((broken[0]["status"], broken[0]["raw_status"]), ("failed", "ERROR"))
        self.assertTrue(result["complete"])

    def test_a_packaged_unittest_import_failure_is_marked_or_the_run_is_incomplete(self):
        result = checks.parse_text(UNITTEST_PACKAGE_IMPORT_FAILURE)
        marked = any("_FailedTest" in t["name"] for t in result["tests"])
        self.assertTrue(marked or not result["complete"],
                        "an import failure must either carry the _FailedTest name or leave the run incomplete; "
                        "otherwise controls.py judge would read it as a clean run of fewer tests")
        if not marked:
            self.assertTrue(any("runner reported" in w for w in result["warnings"]), result["warnings"])


class ControlRuleTests(unittest.TestCase):
    """The count behind judge's default (--min-kills 2) is a core rule too, not only westack-tdd's."""

    def test_the_evidence_reference_asks_for_at_least_two_distinct_broken_copies_per_detection_claim(self):
        text = re.sub(r"\s+", " ", (fixtures.ROOT / "references" / "evidence.md").read_text(encoding="utf-8"))
        self.assertRegex(text, r"(?i)detection claim[^.]*at least two distinct[^.]*broken cop")


class LoadTests(unittest.TestCase):
    """controls.py calls checks.load(path) on a raw output file or on a saved parse result."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-checks-contract-")
        self.addCleanup(self.temp.cleanup)
        self.dir = pathlib.Path(self.temp.name)

    def test_a_raw_file_is_parsed_and_carries_the_source_digest(self):
        path = self.dir / "run.txt"
        path.write_text(UNITTEST_MIXED, encoding="utf-8")
        result = checks.load(path)
        self.assertEqual(result["runner"], "unittest")
        self.assertEqual(result["source_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["source"], str(path))

    def test_a_saved_parse_result_loads_back_unchanged(self):
        saved = checks.parse_text(PYTEST)
        path = self.dir / "parsed.json"
        path.write_text(json.dumps(saved), encoding="utf-8")
        self.assertEqual(checks.load(path), saved)

    def test_a_missing_file_raises_the_checks_usage_error(self):
        with self.assertRaises(checks.UsageError):
            checks.load(self.dir / "absent.txt")


if __name__ == "__main__":
    unittest.main()
