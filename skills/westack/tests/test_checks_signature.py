"""EV-40: a failure is pre-existing only if its name and its normalised failure text both match the baseline's.

A test that fails in both runs with different text is `changed_failures`: unattributed, never pre-existing and never
new, so the diff exits 2 (cannot tell) unless there is also a genuinely new failure (exit 1). A failure whose text
one side did not capture is matched by name alone and listed under `name_only`, so the gap is visible. Timestamps,
addresses, durations, temporary paths and line numbers are normalised away so unstable noise does not hide a real
match.

Inputs are synthetic samples of each runner's output. Each rule also runs against a deliberately broken copy of
checks.py (one line of its source edited) and must give the wrong answer there.
"""
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import test_westack as fixtures

SCRIPT = fixtures.ROOT / "scripts" / "checks.py"


def load(path=SCRIPT):
    key = "westack_checks_sig_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def unittest_run(message, passing="test_ok"):
    return """\
%s (pkg.test_mod.Cls.%s) ... ok
test_bad (pkg.test_mod.Cls.test_bad) ... FAIL

======================================================================
FAIL: test_bad (pkg.test_mod.Cls.test_bad)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/work/pkg/test_mod.py", line 12, in test_bad
    self.assertEqual(price(3), 9)
%s

----------------------------------------------------------------------
Ran 2 tests in 0.004s

FAILED (failures=1)
""" % (passing, passing, message)


def pytest_run(message):
    return """\
tests/test_a.py::test_ok PASSED                                          [ 50%]
tests/test_a.py::test_bad FAILED                                         [100%]

=========================== short test summary info ============================
FAILED tests/test_a.py::test_bad - @@
========================= 1 failed, 1 passed in 0.12s ==========================
""".replace("@@", message)


def tap_run(message):
    return """\
TAP version 13
# Subtest: adds
ok 1 - adds
# Subtest: subtracts
not ok 2 - subtracts
  ---
  duration_ms: 0.4
  error: '%s'
  code: 'ERR_ASSERTION'
  ...
1..2
# tests 2
# pass 1
# fail 1
""" % message


def jest_run(message):
    return json.dumps({"numTotalTests": 2, "numPassedTests": 1, "numFailedTests": 1, "testResults": [{
        "name": "/repo/a.test.js", "status": "failed", "assertionResults": [
            {"fullName": "adds", "status": "passed", "failureMessages": []},
            {"fullName": "subtracts", "status": "failed",
             "failureMessages": ["Error: expect(received).toBe(expected)\n\n%s\n\n    at Object.<anonymous> "
                                 "(/repo/a.test.js:9:20)" % message]}]}]})


RUNNERS = {"unittest": unittest_run, "pytest": pytest_run, "tap": tap_run, "jest": jest_run}


class SignatureDiff(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def diff(self, before, after, module=None):
        m = module or self.m
        return m.diff(m.parse_text(before), m.parse_text(after))

    def test_the_same_failure_text_is_pre_existing_for_every_runner(self):
        for name, make in RUNNERS.items():
            with self.subTest(runner=name):
                report = self.diff(make("AssertionError: 6 != 9"), make("AssertionError: 6 != 9"))
                self.assertEqual(len(report["preexisting_failures"]), 1, report)
                self.assertEqual((report["changed_failures"], report["new_failures"], report["name_only"]), ([], [], []))
                self.assertEqual((report["verdict"], report["exit_code"]), ("no-new-failures", 0))

    def test_a_changed_message_is_unattributed_not_pre_existing_and_not_new_for_every_runner(self):
        for name, make in RUNNERS.items():
            with self.subTest(runner=name):
                report = self.diff(make("AssertionError: 6 != 9"), make("AssertionError: 6 != 8"))
                self.assertEqual(report["preexisting_failures"], [], report)
                self.assertEqual(report["new_failures"], [])
                self.assertEqual(len(report["changed_failures"]), 1)
                entry = report["changed_failures"][0]
                self.assertIn("9", entry["before"])
                self.assertIn("8", entry["after"])
                self.assertEqual((report["verdict"], report["exit_code"]), ("inconclusive", 2))
                self.assertTrue(any("different failure text" in r for r in report["reasons"]), report["reasons"])

    def test_a_genuinely_new_failure_still_exits_1_beside_a_changed_one(self):
        before = unittest_run("AssertionError: 6 != 9")
        after = unittest_run("AssertionError: 6 != 8").replace(
            "test_ok (pkg.test_mod.Cls.test_ok) ... ok", "test_ok (pkg.test_mod.Cls.test_ok) ... FAIL")
        report = self.diff(before, after)
        self.assertEqual(report["new_failures"], ["pkg.test_mod.Cls.test_ok"])
        self.assertEqual(len(report["changed_failures"]), 1)
        self.assertEqual(report["exit_code"], 1)

    def test_unstable_noise_is_normalised_away(self):
        one = "AssertionError: <Cart object at 0x7f1c2a> took 0.31s at 2026-10-29 10:11:12.123 in /tmp/tmpab12cd34/x.py line 12"
        two = "AssertionError: <Cart object at 0x7ffd90> took 0.45s at 2026-10-30 08:00:01.999 in /tmp/tmpzz99yy88/x.py line 14"
        for name in ("unittest", "pytest"):
            with self.subTest(runner=name):
                report = self.diff(RUNNERS[name](one), RUNNERS[name](two))
                self.assertEqual(len(report["preexisting_failures"]), 1, report)
                self.assertEqual(report["changed_failures"], [])

    def test_text_one_side_did_not_capture_is_matched_by_name_and_listed(self):
        before = self.m.parse_text(unittest_run("AssertionError: 6 != 9"))
        for test in before["tests"]:
            test.pop("signature", None)
        after = self.m.parse_text(unittest_run("AssertionError: 6 != 8"))
        report = self.m.diff(before, after)
        self.assertEqual(report["preexisting_failures"], ["pkg.test_mod.Cls.test_bad"])
        self.assertEqual(report["name_only"], ["pkg.test_mod.Cls.test_bad"])
        self.assertEqual(report["changed_failures"], [])
        self.assertEqual(report["exit_code"], 0)

    def test_a_pytest_message_cut_at_the_terminal_width_still_matches(self):
        full = pytest_run("AssertionError: assert price(3) == 9 where price = <function price at 0x1>")
        cut = pytest_run("AssertionError: assert price(3) == 9 where pri...")
        report = self.diff(full, cut)
        self.assertEqual(len(report["preexisting_failures"]), 1, report)

    def test_signatures_are_saved_in_the_parse_result_and_reused_from_it(self):
        parsed = self.m.parse_text(unittest_run("AssertionError: 6 != 9"))
        bad = next(t for t in parsed["tests"] if t["name"].endswith("test_bad"))
        self.assertIn("6 != 9", bad["signature"])
        self.assertNotIn("0x", bad["signature"])
        passing = next(t for t in parsed["tests"] if t["name"].endswith("test_ok"))
        self.assertNotIn("signature", passing)
        with tempfile.TemporaryDirectory() as tmp:
            saved = pathlib.Path(tmp) / "before.json"
            saved.write_text(json.dumps(parsed), encoding="utf-8")
            raw = pathlib.Path(tmp) / "after.txt"
            raw.write_text(unittest_run("AssertionError: 6 != 8"), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), "diff", str(saved), str(raw)],
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertEqual(len(json.loads(run.stdout)["changed_failures"]), 1)


class BrokenCopies(unittest.TestCase):
    """One rule edited out of checks.py: the copy must give the wrong answer on the input the rule exists for."""

    def broken(self, tmp, pattern, replacement):
        source = SCRIPT.read_text(encoding="utf-8")
        edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
        self.assertEqual(count, 1, "the line to break is not in checks.py: " + pattern)
        self.assertNotEqual(edited, source)
        target = pathlib.Path(tmp) / "checks_broken.py"
        target.write_text(edited, encoding="utf-8")
        return load(target)

    def test_a_name_only_comparison_reads_a_changed_message_as_pre_existing(self):
        before, after = unittest_run("AssertionError: 6 != 9"), unittest_run("AssertionError: 6 != 8")
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^COMPARE_SIGNATURES = True$", "COMPARE_SIGNATURES = False")
            report = broken.diff(broken.parse_text(before), broken.parse_text(after))
            self.assertEqual(len(report["preexisting_failures"]), 1)
            self.assertEqual(report["exit_code"], 0)
        good = load()
        self.assertEqual(good.diff(good.parse_text(before), good.parse_text(after))["exit_code"], 2)

    def test_without_normalisation_noise_reads_as_a_changed_failure(self):
        one = "AssertionError: took 0.31s at 0x7f1c2a"
        two = "AssertionError: took 0.45s at 0x7ffd90"
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^NORMALISE = True$", "NORMALISE = False")
            report = broken.diff(broken.parse_text(unittest_run(one)), broken.parse_text(unittest_run(two)))
            self.assertEqual(len(report["changed_failures"]), 1)
        good = load()
        self.assertEqual(good.diff(good.parse_text(unittest_run(one)), good.parse_text(unittest_run(two)))["exit_code"], 0)

    def test_a_parser_that_captures_no_text_reads_every_changed_message_as_pre_existing(self):
        before, after = pytest_run("assert 1 == 2"), pytest_run("assert 1 == 3")
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^CAPTURE_TEXT = True$", "CAPTURE_TEXT = False")
            report = broken.diff(broken.parse_text(before), broken.parse_text(after))
            self.assertEqual(report["changed_failures"], [])
            self.assertEqual(report["name_only"], ["tests/test_a.py::test_bad"])
        good = load()
        self.assertEqual(len(good.diff(good.parse_text(before), good.parse_text(after))["changed_failures"]), 1)


if __name__ == "__main__":
    unittest.main()
