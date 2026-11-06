"""checks.py: parse saved test-runner output into per-test results and diff a baseline against an
after-run (new failures, pre-existing failures, fixed, missing or renamed). It never runs commands.
Inputs are synthetic samples of each runner's output format."""
import ast
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
SCRIPT = ROOT / "scripts" / "checks.py"

UNITTEST = """\
test_a (pkg.test_mod.Cls.test_a) ... ok
test_b (pkg.test_mod.Cls.test_b) ... FAIL
test_c (pkg.test_mod.Cls.test_c) ... ERROR
test_d (pkg.test_mod.Cls.test_d) ... skipped 'needs network'
test_e (pkg.test_mod.Cls.test_e) ... expected failure
test_f (pkg.test_mod.Cls.test_f) ... unexpected success
test_g (pkg.test_mod.Cls.test_g)
Checks the docstring line. ... ok
test_h (pkg.test_mod.Cls.test_h) ... printed by the test
ok
test_i (pkg.test_mod.Cls.test_i) ...
  test_i (pkg.test_mod.Cls.test_i) (case='x') ... FAIL
  test_i (pkg.test_mod.Cls.test_i) (case='y') ... ok

======================================================================
FAIL: test_b (pkg.test_mod.Cls.test_b)
----------------------------------------------------------------------
Traceback (most recent call last):
AssertionError: 1 != 2

======================================================================
ERROR: test_c (pkg.test_mod.Cls.test_c)
----------------------------------------------------------------------
Traceback (most recent call last):
ValueError: boom

======================================================================
FAIL: test_i (pkg.test_mod.Cls.test_i) (case='x')
----------------------------------------------------------------------
AssertionError

----------------------------------------------------------------------
Ran 9 tests in 0.012s

FAILED (failures=2, errors=1, skipped=1, expected failures=1, unexpected successes=1)
"""

PYTEST_VERBOSE = """\
============================= test session starts =============================
collected 6 items

tests/test_a.py::test_ok PASSED                                          [ 16%]
tests/test_a.py::test_bad FAILED                                         [ 33%]
tests/test_a.py::test_param[1-2] PASSED                                  [ 50%]
tests/test_a.py::test_param[a b] PASSED                                  [ 66%]
tests/test_b.py::test_skip SKIPPED (no db)                               [ 83%]
tests/test_b.py::test_known XFAIL (bug 12)                               [100%]

=================================== FAILURES ===================================
=========================== short test summary info ============================
FAILED tests/test_a.py::test_bad - assert 1 == 2
============== 1 failed, 3 passed, 1 skipped, 1 xfailed in 0.12s ===============
"""

PYTEST_QUIET = """\
.F..s
=========================== short test summary info ============================
FAILED tests/test_a.py::test_bad - assert 1 == 2
1 failed, 3 passed, 1 skipped in 0.05s
"""

TAP = """\
TAP version 13
# Subtest: math
    # Subtest: adds
    ok 1 - adds
      ---
      duration_ms: 0.4
      ...
    # Subtest: subtracts
    not ok 2 - subtracts
      ---
      error: 'expected 1'
      ...
    # Subtest: later
    ok 3 - later # SKIP not ready
    1..3
not ok 1 - math
  ---
  type: 'suite'
  ...
# Subtest: top level
ok 2 - top level
# Subtest: wish
ok 3 - wish # TODO someday
1..3
# tests 5
# suites 1
# pass 2
# fail 1
# cancelled 0
# skipped 1
# todo 1
"""

JEST = {
    "numTotalTests": 4, "numPassedTests": 2, "numFailedTests": 1, "numPendingTests": 1,
    "testResults": [
        {"name": "C:/work/app/src/a.test.js", "status": "failed", "message": "",
         "assertionResults": [
             {"ancestorTitles": ["sum"], "title": "adds", "fullName": "sum adds", "status": "passed"},
             {"ancestorTitles": ["sum"], "title": "carries", "fullName": "sum carries", "status": "failed"},
             {"ancestorTitles": [], "title": "later", "fullName": "later", "status": "pending"}]},
        {"name": "C:/work/app/src/deep/b.test.js", "status": "passed", "message": "",
         "assertionResults": [{"ancestorTitles": [], "title": "works", "fullName": "works", "status": "passed"}]},
        {"name": "C:/work/app/src/broken.test.js", "status": "failed", "message": "SyntaxError: Unexpected token",
         "assertionResults": []},
    ],
}


def load():
    spec = importlib.util.spec_from_file_location("westack_checks_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def statuses(result):
    return {t["name"]: t["status"] for t in result["tests"]}


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.c = load()

    def test_unittest_verbose(self):
        result = self.c.parse_text(UNITTEST)
        self.assertEqual(result["runner"], "unittest")
        self.assertEqual(statuses(result), {
            "pkg.test_mod.Cls.test_a": "passed", "pkg.test_mod.Cls.test_b": "failed",
            "pkg.test_mod.Cls.test_c": "failed", "pkg.test_mod.Cls.test_d": "skipped",
            "pkg.test_mod.Cls.test_e": "skipped", "pkg.test_mod.Cls.test_f": "failed",
            "pkg.test_mod.Cls.test_g": "passed", "pkg.test_mod.Cls.test_h": "passed",
            "pkg.test_mod.Cls.test_i": "failed"})
        self.assertTrue(result["complete"], result["warnings"])
        self.assertEqual(result["reported"]["total"], 9)

    def test_unittest_old_format_and_count_mismatch(self):
        result = self.c.parse_text("test_a (test_mod.Cls) ... ok\n\nRan 2 tests in 0.001s\n\nOK\n")
        self.assertEqual(statuses(result), {"test_mod.Cls.test_a": "passed"})
        self.assertFalse(result["complete"])

    def test_pytest_verbose(self):
        result = self.c.parse_text(PYTEST_VERBOSE)
        self.assertEqual(result["runner"], "pytest")
        self.assertEqual(statuses(result), {
            "tests/test_a.py::test_ok": "passed", "tests/test_a.py::test_bad": "failed",
            "tests/test_a.py::test_param[1-2]": "passed", "tests/test_a.py::test_param[a b]": "passed",
            "tests/test_b.py::test_skip": "skipped", "tests/test_b.py::test_known": "skipped"})
        self.assertTrue(result["complete"], result["warnings"])

    def test_pytest_quiet_names_too_few_tests(self):
        result = self.c.parse_text(PYTEST_QUIET)
        self.assertEqual(result["runner"], "pytest")
        self.assertEqual(statuses(result), {"tests/test_a.py::test_bad": "failed"})
        self.assertFalse(result["complete"])

    def test_node_tap(self):
        result = self.c.parse_text(TAP)
        self.assertEqual(result["runner"], "tap")
        self.assertEqual(statuses(result), {
            "math > adds": "passed", "math > subtracts": "failed", "math > later": "skipped",
            "top level": "passed", "wish": "skipped"})
        self.assertTrue(result["complete"], result["warnings"])

    def test_tap_suite_failure_without_failing_child_is_kept(self):
        text = "TAP version 13\n# Subtest: s\n    # Subtest: t\n    ok 1 - t\n    1..1\nnot ok 1 - s\n1..1\n# tests 1\n"
        self.assertEqual(statuses(self.c.parse_text(text)), {"s > t": "passed", "s": "failed"})

    def test_jest_and_vitest_json(self):
        result = self.c.parse_text(json.dumps(JEST))
        self.assertEqual(result["runner"], "jest")
        self.assertEqual(statuses(result), {
            "a.test.js > sum adds": "passed", "a.test.js > sum carries": "failed", "a.test.js > later": "skipped",
            "deep/b.test.js > works": "passed", "broken.test.js (suite)": "failed"})
        self.assertTrue(result["complete"], result["warnings"])

    def test_run_py_json(self):
        record = {"collected": 2, "tests": [{"test": "m.C.test_a", "status": "passed"},
                                            {"test": "m.C.test_b", "status": "not-run", "reason": "x"}]}
        result = self.c.parse_text(json.dumps(record))
        self.assertEqual(result["runner"], "westack-run")
        self.assertEqual(statuses(result), {"m.C.test_a": "passed", "m.C.test_b": "skipped"})
        self.assertTrue(result["complete"])

    def test_flaky_duplicate_counts_as_failed(self):
        text = "test_a (m.C.test_a) ... FAIL\ntest_a (m.C.test_a) ... ok\n\nRan 2 tests in 0.1s\n"
        test = self.c.parse_text(text)["tests"][0]
        self.assertEqual((test["status"], test["occurrences"], test["flaky"]), ("failed", 2, True))

    def test_unrecognised_output(self):
        result = self.c.parse_text("hello world\n")
        self.assertEqual((result["runner"], result["tests"], result["complete"]), ("unknown", [], False))


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.c = load()

    def run_pair(self, before, after, renames=()):
        return self.c.diff(self.c.parse_text(before), self.c.parse_text(after), renames)

    def unit(self, **results):
        lines = ["%s (m.C.%s) ... %s" % (name, name, status) for name, status in results.items()]
        return "\n".join(lines) + "\n\nRan %d tests in 0.1s\n" % len(results)

    def test_new_preexisting_fixed_missing_added_and_skipped(self):
        before = self.unit(test_a="ok", test_b="FAIL", test_c="ok", test_d="FAIL", test_e="ok", test_f="ok")
        after = self.unit(test_a="FAIL", test_b="FAIL", test_c="ok", test_d="ok", test_g="FAIL", test_f="skipped 'x'")
        report = self.run_pair(before, after)
        self.assertEqual(report["verdict"], "new-failures")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["new_failures"], ["m.C.test_a", "m.C.test_g"])
        self.assertEqual(report["preexisting_failures"], ["m.C.test_b"])
        self.assertEqual(report["fixed"], ["m.C.test_d"])
        self.assertEqual(report["missing"], ["m.C.test_e"])
        self.assertEqual(report["added"], ["m.C.test_g"])
        self.assertEqual(report["newly_skipped"], ["m.C.test_f"])

    def test_zero_new_failures(self):
        before = self.unit(test_a="ok", test_b="FAIL")
        report = self.run_pair(before, self.unit(test_a="ok", test_b="FAIL"))
        self.assertEqual((report["verdict"], report["exit_code"]), ("no-new-failures", 0))
        self.assertEqual(report["preexisting_failures"], ["m.C.test_b"])

    def test_missing_test_is_inconclusive_until_mapped(self):
        before = "test_a (old_mod.C.test_a) ... ok\n\nRan 1 test in 0.1s\n"
        after = "test_a (new_mod.C.test_a) ... ok\n\nRan 1 test in 0.1s\n"
        report = self.run_pair(before, after)
        self.assertEqual((report["verdict"], report["exit_code"]), ("inconclusive", 2))
        self.assertIn("missing", " ".join(report["reasons"]))
        mapped = self.run_pair(before, after, [("old_mod.", "new_mod.")])
        self.assertEqual((mapped["verdict"], mapped["exit_code"]), ("no-new-failures", 0))
        self.assertEqual(mapped["renamed"], [{"from": "old_mod.C.test_a", "to": "new_mod.C.test_a"}])

    def test_incomplete_or_empty_after_run_is_inconclusive(self):
        before = self.c.parse_text(PYTEST_VERBOSE)
        after = self.c.parse_text(PYTEST_QUIET)
        self.assertEqual(self.c.diff(before, after, [])["verdict"], "inconclusive")
        empty = self.c.diff(before, self.c.parse_text("no tests ran\n"), [])
        self.assertEqual(empty["exit_code"], 2)

    def test_new_failure_wins_over_inconclusive(self):
        before = self.unit(test_a="ok", test_b="ok")
        report = self.run_pair(before, self.unit(test_a="FAIL"))
        self.assertEqual((report["verdict"], report["exit_code"]), ("new-failures", 1))
        self.assertEqual(report["missing"], ["m.C.test_b"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-checks-")
        self.base = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True,
                              text=True, timeout=60)

    def write(self, name, text):
        path = self.base / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def test_parse_then_diff_from_saved_files(self):
        before = self.write("before.txt", "test_a (m.C.test_a) ... ok\ntest_b (m.C.test_b) ... FAIL\n\nRan 2 tests in 0.1s\n")
        after = self.write("after.txt", "test_a (m.C.test_a) ... ok\ntest_b (m.C.test_b) ... ok\n\nRan 2 tests in 0.1s\n")
        parsed = self.cli("parse", before, "--output", self.base / "before.json")
        self.assertEqual(parsed.returncode, 0, parsed.stdout + parsed.stderr)
        stored = json.loads((self.base / "before.json").read_text(encoding="utf-8"))
        self.assertEqual(len(stored["source_sha256"]), 64)
        result = self.cli("diff", self.base / "before.json", after)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["fixed"], ["m.C.test_b"])
        self.assertIn("ran nothing", report["claim"])

    def test_output_is_never_replaced(self):
        before = self.write("before.txt", "test_a (m.C.test_a) ... ok\n\nRan 1 test in 0.1s\n")
        taken = self.write("taken.json", "{}")
        result = self.cli("parse", before, "--output", taken)
        self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
        self.assertEqual(taken.read_text(encoding="utf-8"), "{}")

    def test_usage_errors_exit_64(self):
        self.assertEqual(self.cli("diff", self.base / "only-one.txt").returncode, 64)
        self.assertEqual(self.cli("parse", self.base / "missing.txt").returncode, 64)

    def test_unrecognised_parse_exits_2(self):
        self.assertEqual(self.cli("parse", self.write("x.txt", "hello\n")).returncode, 2)

    def test_runs_nothing(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"subprocess", "socket", "urllib", "http", "multiprocessing"})


if __name__ == "__main__":
    unittest.main()
