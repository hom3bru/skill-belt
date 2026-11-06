"""Tests for scripts/controls.py: write broken copies from a mutation spec (never running anything), and judge
saved test-runner outputs of a red run or of broken-copy controls against a green reference run.

Run: python -B -m unittest discover -s skills/westack-tdd/tests -v
The script under test is loaded by path; WESTACK_TDD_CONTROLS may point at another copy (broken-copy controls
run this same file against deliberately broken copies of controls.py). Real unittest outputs are produced by
running tiny suites in a temporary folder; pytest outputs are short literal transcripts.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("WESTACK_TDD_CONTROLS")
                      or pathlib.Path(__file__).resolve().parents[1] / "scripts" / "controls.py").resolve()
CORE = pathlib.Path(__file__).resolve().parents[2] / "westack"

PRICE = "def total(qty, unit):\n    if qty >= 10:\n        return round(qty * unit * 0.9, 2)\n    return qty * unit\n"
PRICE_TEST = ("import unittest\nfrom price import total\n\n\nclass Total(unittest.TestCase):\n"
              "    def test_bulk_discount(self):\n        self.assertEqual(total(10, 2.0), 18.0)\n\n"
              "    def test_small_order(self):\n        self.assertEqual(total(3, 2.0), 6.0)\n")


def run(*args, cwd=None):
    done = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          timeout=120, cwd=cwd)
    try:
        data = json.loads(done.stdout)
    except ValueError:
        data = None
    return done.returncode, data, done


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="westack-tdd-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "project"
        (self.root / "tests").mkdir(parents=True)
        (self.root / "price.py").write_text(PRICE, encoding="utf-8", newline="\n")
        (self.root / "tests" / "test_price.py").write_text(PRICE_TEST, encoding="utf-8", newline="\n")

    def spec(self, mutations, **extra):
        data = {"format": "westack-tdd-controls-1", "claim": "the price tests catch a broken discount",
                "root": "project", "command": "python -m unittest discover -s tests -v", "mutations": mutations}
        data.update(extra)
        path = self.tmp / "spec.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def two(self):
        return [{"id": "rate", "kind": "constant", "file": "price.py", "find": "0.9", "replace": "0.8"},
                {"id": "edge", "kind": "boundary", "file": "price.py", "find": "qty >= 10", "replace": "qty > 10"}]

    def assertRefused(self, code, data, *needles):
        """A refusal is a JSON report with status refused and exit 1; a crash also exits 1, so check both."""
        self.assertIsInstance(data, dict, "the script must answer with a JSON report, not crash")
        self.assertEqual((code, data.get("status")), (1, "refused"), data)
        for needle in needles:
            words = needle if isinstance(needle, tuple) else (needle,)
            self.assertTrue(any(all(w in e for w in words) for e in data["errors"]), (needle, data["errors"]))


class PlanTests(Workspace):
    def test_writes_one_copy_per_mutation_and_leaves_the_source_alone(self):
        before = sha(self.root / "price.py")
        code, data, done = run("plan", self.spec(self.two()), "--out", self.tmp / "controls")
        self.assertEqual(code, 0, done.stderr + done.stdout)
        self.assertEqual(sha(self.root / "price.py"), before)
        self.assertEqual([v["id"] for v in data["variants"]], ["rate", "edge"])
        for variant in data["variants"]:
            copy = pathlib.Path(variant["path"])
            self.assertTrue(copy.is_dir())
            self.assertFalse(copy.resolve().is_relative_to(self.root.resolve()))
            self.assertEqual(variant["original_sha256"], before)
            self.assertEqual(variant["mutated_sha256"], sha(copy / "price.py"))
            self.assertNotEqual(variant["mutated_sha256"], before)
            self.assertEqual((copy / "tests" / "test_price.py").read_text(encoding="utf-8"), PRICE_TEST)
        self.assertIn("0.8", (self.tmp / "controls" / "rate" / "price.py").read_text(encoding="utf-8"))
        self.assertIn("qty > 10", (self.tmp / "controls" / "edge" / "price.py").read_text(encoding="utf-8"))
        self.assertEqual(data["variants"][1]["line"], 2)
        self.assertEqual(json.loads((self.tmp / "controls" / "plan.json").read_text(encoding="utf-8")), data)

    def test_never_runs_the_command(self):
        command = "python -c \"open('RAN-MARKER', 'w').write('x')\""
        code, data, done = run("plan", self.spec(self.two(), command=command), "--out", self.tmp / "controls",
                               cwd=self.tmp)
        self.assertEqual(code, 0, done.stderr + done.stdout)
        self.assertEqual(data["command"], command)
        self.assertEqual(list(self.tmp.rglob("RAN-MARKER")), [])

    def test_refuses_a_mutation_whose_text_is_absent_and_writes_nothing(self):
        mutations = self.two()
        mutations[0]["find"] = "0.75"
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertRefused(code, data, ("rate", "not found"))
        self.assertFalse((self.tmp / "controls").exists())

    def test_refuses_an_ambiguous_find_unless_an_occurrence_is_named(self):
        (self.root / "price.py").write_text(PRICE + "\nLIMIT = 10\nOTHER = 10\n", encoding="utf-8", newline="\n")
        mutations = [{"id": "a", "kind": "constant", "file": "price.py", "find": "= 10\n", "replace": "= 11\n"},
                     {"id": "b", "kind": "boundary", "file": "price.py", "find": "qty >= 10", "replace": "qty > 10"}]
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "c1")
        self.assertRefused(code, data, "2 times")
        mutations[0]["occurrence"] = 2
        code, data, done = run("plan", self.spec(mutations), "--out", self.tmp / "c2")
        self.assertEqual(code, 0, done.stdout)
        text = (self.tmp / "c2" / "a" / "price.py").read_text(encoding="utf-8")
        self.assertIn("LIMIT = 10\nOTHER = 11\n", text)

    def test_needs_two_broken_copies_by_default(self):
        code, data, _ = run("plan", self.spec(self.two()[:1]), "--out", self.tmp / "c1")
        self.assertRefused(code, data, "at least 2")
        code, data, done = run("plan", self.spec(self.two()[:1]), "--out", self.tmp / "c2", "--min-variants", "1")
        self.assertEqual(code, 0, done.stdout)

    def test_refuses_two_mutations_that_make_the_same_copy(self):
        mutations = self.two()
        mutations[1] = dict(mutations[0], id="rate-again", kind="argument")
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertRefused(code, data, "identical")

    def test_refuses_a_no_op_mutation(self):
        mutations = self.two()
        mutations[0]["replace"] = mutations[0]["find"]
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertRefused(code, data, "changes nothing")

    def test_refuses_an_output_folder_inside_the_source_or_already_there(self):
        code, data, _ = run("plan", self.spec(self.two()), "--out", self.root / "controls")
        self.assertRefused(code, data, "inside")
        self.assertFalse((self.root / "controls").exists())
        (self.tmp / "taken").mkdir()
        code, data, _ = run("plan", self.spec(self.two()), "--out", self.tmp / "taken")
        self.assertRefused(code, data, "exists")

    def test_refuses_a_file_outside_the_root(self):
        (self.tmp / "outside.py").write_text("X = 1\n", encoding="utf-8")
        mutations = self.two()
        mutations[0] = {"id": "escape", "kind": "constant", "file": "../outside.py", "find": "1", "replace": "2"}
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertRefused(code, data, "outside the root")

    def test_explains_a_line_ending_mismatch(self):
        (self.root / "price.py").write_bytes(PRICE.replace("\n", "\r\n").encode("utf-8"))
        mutations = self.two()
        mutations[0] = {"id": "both", "kind": "branch", "file": "price.py",
                        "find": "if qty >= 10:\n        return", "replace": "if qty < 10:\n        return"}
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertRefused(code, data, "CRLF")

    def test_warns_on_a_single_kind_and_on_mutating_a_test(self):
        mutations = [{"id": "rate", "kind": "constant", "file": "price.py", "find": "0.9", "replace": "0.8"},
                     {"id": "expect", "kind": "constant", "file": "tests/test_price.py", "find": "18.0",
                      "replace": "17.0"}]
        code, data, done = run("plan", self.spec(mutations), "--out", self.tmp / "controls")
        self.assertEqual(code, 0, done.stdout)
        joined = " ".join(data["warnings"])
        self.assertIn("one kind", joined)
        self.assertIn("test file", joined)

    def test_skips_version_control_and_caches_and_guards_the_copy_size(self):
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref: x\n", encoding="utf-8")
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "price.cpython-314.pyc").write_bytes(b"\0")
        code, data, done = run("plan", self.spec(self.two()), "--out", self.tmp / "c1")
        self.assertEqual(code, 0, done.stdout)
        self.assertFalse((self.tmp / "c1" / "rate" / ".git").exists())
        self.assertFalse((self.tmp / "c1" / "rate" / "__pycache__").exists())
        code, data, _ = run("plan", self.spec(self.two()), "--out", self.tmp / "c2", "--max-files", "1")
        self.assertRefused(code, data, ("files", "max"))
        self.assertFalse((self.tmp / "c2").exists())

    def test_rejects_an_unknown_kind_and_a_bad_spec(self):
        mutations = self.two()
        mutations[0]["kind"] = "vibes"
        code, data, _ = run("plan", self.spec(mutations), "--out", self.tmp / "c1")
        self.assertRefused(code, data, "kind")
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, data, _ = run("plan", bad, "--out", self.tmp / "c2")
        self.assertEqual(code, 64)


class RunOutputs(unittest.TestCase):
    """Real `python -m unittest -v` outputs: a green reference, an assertion failure, an error-only failure,
    an import failure, a run with one test missing, and a run that executes nothing."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="westack-tdd-runs-"))
        cls.out = {}
        variants = {
            "green": PRICE,
            "assertion": PRICE.replace("0.9", "0.8"),
            "error": PRICE.replace("return round(qty * unit * 0.9, 2)", "return None.real"),
            "import": PRICE.replace("def total", "def totl"),
        }
        for name, source in variants.items():
            folder = cls.tmp / name
            (folder / "tests").mkdir(parents=True)
            (folder / "price.py").write_text(source, encoding="utf-8", newline="\n")
            (folder / "tests" / "test_price.py").write_text(PRICE_TEST, encoding="utf-8", newline="\n")
            cls.out[name] = cls.capture(folder, name)
        folder = cls.tmp / "fewer"
        (folder / "tests").mkdir(parents=True)
        (folder / "price.py").write_text(PRICE.replace("0.9", "0.8"), encoding="utf-8", newline="\n")
        (folder / "tests" / "test_price.py").write_text(PRICE_TEST.split("    def test_small_order")[0],
                                                        encoding="utf-8", newline="\n")
        cls.out["fewer"] = cls.capture(folder, "fewer")
        empty = cls.tmp / "empty"
        (empty / "tests").mkdir(parents=True)
        cls.out["empty"] = cls.capture(empty, "empty")
        cls.out["pytest-green"] = cls.text("pytest-green", "tests/test_price.py::test_bulk PASSED\n"
                                           "tests/test_price.py::test_small PASSED\n"
                                           "============ 2 passed in 0.01s ============\n")
        cls.out["pytest-failed"] = cls.text("pytest-failed", "tests/test_price.py::test_bulk FAILED\n"
                                            "tests/test_price.py::test_small PASSED\n"
                                            "======= 1 failed, 1 passed in 0.02s =======\n")
        cls.out["pytest-error"] = cls.text("pytest-error", "tests/test_price.py::test_bulk ERROR\n"
                                           "tests/test_price.py::test_small PASSED\n"
                                           "======= 1 passed, 1 error in 0.02s =======\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def capture(cls, folder, name):
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                              cwd=folder, capture_output=True, text=True, timeout=120)
        return cls.text(name, done.stderr + done.stdout)

    @classmethod
    def text(cls, name, body):
        path = cls.tmp / (name + ".txt")
        path.write_text(body, encoding="utf-8")
        return path

    def judge(self, reference, *runs, extra=()):
        args = ["judge", "--core", CORE, "--reference", self.out[reference]]
        for label in runs:
            args += ["--run", label + "=" + str(self.out[label])]
        code, data, done = run(*args, *extra)
        self.assertIsInstance(data, dict, "judge must answer with a JSON report, not crash: " + done.stderr[-800:])
        return code, data, done

    def outcome(self, data, label):
        return next(r["outcome"] for r in data["runs"] if r["label"] == label)


class JudgeTests(RunOutputs):
    def test_the_fixtures_are_what_they_claim(self):
        self.assertIn("OK", self.out["green"].read_text(encoding="utf-8"))
        self.assertIn("FAIL: test_bulk_discount", self.out["assertion"].read_text(encoding="utf-8"))
        self.assertIn("ERROR: test_bulk_discount", self.out["error"].read_text(encoding="utf-8"))
        self.assertIn("_FailedTest", self.out["import"].read_text(encoding="utf-8"))
        self.assertIn("Ran 0 tests", self.out["empty"].read_text(encoding="utf-8"))

    def test_an_assertion_failure_is_a_kill(self):
        code, data, done = self.judge("green", "assertion", extra=["--min-kills", "1"])
        self.assertEqual(code, 0, done.stdout + done.stderr)
        self.assertEqual(self.outcome(data, "assertion"), "killed")
        self.assertEqual(data["verdict"], "supported")
        failed = next(r for r in data["runs"] if r["label"] == "assertion")["failed_tests"]
        self.assertEqual(len(failed), 1)
        self.assertIn("test_bulk_discount", failed[0])

    def test_two_kills_are_needed_by_default(self):
        code, data, _ = self.judge("green", "assertion")
        self.assertEqual(code, 2)
        self.assertEqual(data["verdict"], "inconclusive")
        self.assertTrue(any("2" in r for r in data["reasons"]), data)

    def test_a_copy_that_passes_is_a_survivor_and_a_gap(self):
        code, data, _ = self.judge("green", "assertion", "green", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)  # the same file named twice is refused before judging
        self.assertTrue(any("twice" in r for r in data["reasons"]), data)
        survivor = self.tmp / "survivor.txt"
        survivor.write_bytes(self.out["green"].read_bytes())
        code, data, _ = run("judge", "--core", CORE, "--reference", self.out["green"],
                            "--run", "assertion=" + str(self.out["assertion"]), "--run", "survivor=" + str(survivor))
        self.assertEqual(code, 1)
        self.assertEqual(data["verdict"], "gap")
        self.assertEqual(self.outcome(data, "survivor"), "survived")

    def test_an_error_only_failure_is_reported_apart_and_can_be_excluded(self):
        code, data, _ = self.judge("green", "assertion", "error")
        self.assertEqual(code, 0)
        self.assertEqual(self.outcome(data, "error"), "killed-by-error")
        code, data, _ = self.judge("green", "assertion", "error", extra=["--assertion-only"])
        self.assertEqual(code, 2)
        self.assertEqual(data["verdict"], "inconclusive")

    def test_an_import_failure_is_blocked_not_a_kill(self):
        code, data, _ = self.judge("green", "import", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(self.outcome(data, "import"), "blocked")
        self.assertEqual(data["verdict"], "inconclusive")

    def test_a_different_selection_is_blocked(self):
        code, data, _ = self.judge("green", "fewer", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(self.outcome(data, "fewer"), "blocked")
        reason = next(r for r in data["runs"] if r["label"] == "fewer")["reason"]
        self.assertIn("selection", reason)

    def test_zero_executed_is_never_a_kill(self):
        code, data, _ = self.judge("green", "empty", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(self.outcome(data, "empty"), "blocked")

    def test_the_reference_must_be_a_green_run(self):
        code, data, _ = self.judge("assertion", "error", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(data["verdict"], "no-reference")
        code, data, _ = self.judge("empty", "assertion", extra=["--min-kills", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(data["verdict"], "no-reference")

    def test_pytest_failed_is_a_kill_and_error_is_apart(self):
        code, data, _ = self.judge("pytest-green", "pytest-failed", "pytest-error")
        self.assertEqual(code, 0)
        self.assertEqual(self.outcome(data, "pytest-failed"), "killed")
        self.assertEqual(self.outcome(data, "pytest-error"), "killed-by-error")

    def test_without_the_core_parser_it_is_blocked(self):
        empty = self.tmp / "no-core"
        empty.mkdir(exist_ok=True)
        code, data, _ = run("judge", "--core", empty, "--reference", self.out["green"],
                            "--run", "assertion=" + str(self.out["assertion"]))
        self.assertEqual(code, 2)
        self.assertEqual(data["verdict"], "blocked")
        self.assertIn("checks.py", " ".join(data["reasons"]))


if __name__ == "__main__":
    unittest.main()
