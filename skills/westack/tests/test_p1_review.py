"""P1 adoption, review/verify group: the helper behaviour behind four items.

  CM-29  the package check: a skill's name equals its folder name (an error); advisory text lints (warnings)
  EV-38  validate.py receipt --patch-before: a check that edits the observed paths while it runs voids its receipt
  EV-45  results are derived from the receipts: the validator recomputes status and refuses a stored pass flag
  CM-43  a check with no target or malformed input is never a pass

Each behaviour is asserted by one function that runs twice: on the shipped scripts (must hold) and on a copy of the
scripts with exactly that mechanism removed (the same assertion must fail there). A mutation that matches nothing
fails the test, so a control can never pass by accident.
"""
import copy
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_round2 as r2
import test_westack as fixtures

ROOT = fixtures.ROOT
SCRIPTS = ROOT / "scripts"


def broken_core(base, mutations):
    """A copy of the core scripts and contracts under `base`, each (file, old, new) applied exactly once."""
    target = pathlib.Path(base) / "westack"
    shutil.copytree(SCRIPTS, target / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "contracts", target / "contracts")
    for name, old, new in mutations:
        path = target / "scripts" / name
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError("mutation target occurs %d times in %s: %r" % (text.count(old), name, old))
        path.write_bytes(text.replace(old, new).encode("utf-8"))
    return target / "scripts"


def load_validate(scripts):
    spec = importlib.util.spec_from_file_location("westack_validate_" + str(abs(hash(str(scripts)))),
                                                  pathlib.Path(scripts) / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script, *args):
    return subprocess.run([sys.executable, "-B", str(script), *map(str, args)], capture_output=True, text=True,
                          timeout=60)


class Controlled(unittest.TestCase):
    """Base: a temp folder, and `control(mutations, check)` = the check passes on the shipped scripts and fails
    on the broken copy."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-p1-review-")
        self.base = pathlib.Path(self.temp.name)
        self.counter = 0

    def tearDown(self):
        self.temp.cleanup()

    def broken(self, mutations):
        self.counter += 1
        return broken_core(self.base / ("broken%d" % self.counter), mutations)

    def control(self, mutations, check):
        check(SCRIPTS)
        # built, and so verified (each target found exactly once), before the assertion is armed: broken_core reports a
        # missing target as an AssertionError, which inside assertRaises would count as the copy being caught
        copy = self.broken(mutations)
        with self.assertRaises(AssertionError, msg="the broken copy was not caught"):
            check(copy)


class ControlHelperTests(Controlled):
    """`Controlled.control` is what every control in this file rests on. A copy that cannot be built (a mutation target
    that is not in the file) is a failed control, never a caught one."""

    def test_a_mutation_target_that_is_missing_fails_the_control(self):
        with self.assertRaises(AssertionError) as raised:
            self.control([("validate.py", "a line that is nowhere in this file\n", "pass\n")], lambda scripts: None)
        self.assertIn("occurs 0 times", str(raised.exception))

    def test_a_copy_that_is_built_but_not_caught_fails_the_control(self):
        with self.assertRaises(AssertionError) as raised:
            self.control([("skillmeta.py", "MAX_STEPS = 10", "MAX_STEPS = 1000")], lambda scripts: None)
        self.assertIn("the broken copy was not caught", str(raised.exception))


# ---------------------------------------------------------------------------------------------------- CM-29
SKILL = "---\nname: %s\ndescription: A skill.\nmetadata:\n  stack: westack\n  version: 1.0.0-alpha.1\n" \
        "  requires_core: \">=1.0.0-alpha.0 <2\"\n---\n# Skill\n\n%s\n"


class PackageCheckTests(Controlled):
    def package(self, folder, name, body="Do the work.", wrap=None):
        target = self.base / "pkg" / folder
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_bytes((SKILL % (name, body)).encode("utf-8"))
        return target

    def check_name(self, scripts):
        validate = load_validate(scripts)
        mismatch = run(pathlib.Path(scripts) / "validate.py", "package", self.package("some-folder", "westack-review"))
        self.assertEqual(mismatch.returncode, 1, mismatch.stdout)
        errors = json.loads(mismatch.stdout)["errors"]
        self.assertTrue(any("folder" in e and "westack-review" in e and "some-folder" in e for e in errors), errors)
        same = run(pathlib.Path(scripts) / "validate.py", "package", self.package("westack-review", "westack-review"))
        self.assertEqual((same.returncode, json.loads(same.stdout)["errors"]), (0, []), same.stdout)
        self.assertEqual(validate.check_package(self.package("westack-tdd", "westack-tdd")), [])

    def test_a_name_that_differs_from_its_folder_is_an_error_and_a_matching_one_is_not(self):
        self.control([("skillmeta.py", "    elif name != root.name:", "    elif False:")], self.check_name)

    def warnings_of(self, scripts, body):
        folder = "westack-lint"
        result = run(pathlib.Path(scripts) / "validate.py", "package", self.package(folder, folder, body))
        report = json.loads(result.stdout)
        return result.returncode, report

    def check_step_one(self, scripts):
        code, report = self.warnings_of(scripts, "## Step 1\nA.\n\n## Step 2\nB.\n\n## Step 1\nC again.\n")
        self.assertEqual((code, report["errors"]), (0, []), "a lint is a warning, never an error")
        self.assertTrue(any("Step 1" in w for w in report["warnings"]), report)
        code, report = self.warnings_of(scripts, "## Step 1\nA.\n\n## Step 2\nB.\n")
        self.assertEqual((code, report["warnings"]), (0, []), report)

    def test_repeated_step_one_blocks_warn(self):
        self.control([("skillmeta.py", "len(STEP_ONE.findall(text)) > 1", "False")], self.check_step_one)

    def check_numbering(self, scripts):
        body = "\n".join("## Step %d\nDo %d.\n" % (n, n) for n in range(1, 14))
        code, report = self.warnings_of(scripts, body)
        self.assertEqual((code, report["errors"]), (0, []))
        self.assertTrue(any("steps" in w.lower() and "13" in w for w in report["warnings"]), report)
        _, fine = self.warnings_of(scripts, "\n".join("## Step %d\nDo %d.\n" % (n, n) for n in range(1, 6)))
        self.assertEqual(fine["warnings"], [])

    def test_over_numbered_steps_warn(self):
        self.control([("skillmeta.py", "MAX_STEPS = 10", "MAX_STEPS = 1000")], self.check_numbering)

    def check_paths(self, scripts):
        code, report = self.warnings_of(scripts, "Open C:" + "\\Users\\Someone\\notes.txt and /home/alice/project/x.\n")
        self.assertEqual((code, report["errors"]), (0, []))
        hits = [w for w in report["warnings"] if "machine path" in w]
        self.assertEqual(len(hits), 1, report)
        _, fine = self.warnings_of(scripts, "Open `<project>/notes.txt` and ~/.config/tool.\n")
        self.assertEqual(fine["warnings"], [])

    def test_hard_coded_machine_paths_warn(self):
        self.control([("skillmeta.py", "found = MACHINE_PATH.search(text)", "found = None")], self.check_paths)

    def test_every_shipped_package_still_passes_and_lints_are_listed_not_raised(self):
        for folder in ["westack", *sorted(p.name for p in (ROOT.parent).glob("westack-*"))]:
            with self.subTest(skill=folder):
                result = run(SCRIPTS / "validate.py", "package", ROOT.parent / folder)
                report = json.loads(result.stdout)
                self.assertEqual((result.returncode, report["errors"]), (0, []), result.stdout)
                self.assertIsInstance(report["warnings"], list)


# ---------------------------------------------------------------------------------------------------- EV-38
class ReceiptFingerprintTests(r2.Workspace):
    """validate.py receipt --patch-before: the observed paths are fingerprinted before the check and again when the
    receipt is written; a difference voids the receipt."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.init().returncode, 0)
        self.scratch = tempfile.TemporaryDirectory(prefix="westack-p1-ev38-")
        self.addCleanup(self.scratch.cleanup)

    def before(self):
        return r2.out(r2.cli("fingerprint", "--repo", self.repo, "--path", "src", "--root", self.ev))["patch"]

    def refresh(self, n):
        return r2.cli("refresh", self.path(n), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")

    def receipt_with(self, scripts, n, rid, *extra):
        raw = self.raw(rid + ".txt", "# pass 1\n# fail 0\n")
        return run(pathlib.Path(scripts) / "validate.py", "receipt", self.path(n), "--root", self.ev, "--repo", self.repo,
                   "--id", rid, "--claim", "a1", "--type", "unit", "--operation", "node --test test/add.test.js",
                   "--environment", "node 24", "--raw", raw, "--artifact", self.repo / "src/add.js", "--passed", 1,
                   "--failed", 0, "--exit", 0, "--expected-exit", 0, *extra)

    def check_void(self, scripts):
        before = self.before()
        (self.repo / "src/add.js").write_bytes(b"module.exports=(a,b)=>a-b; // edited by the check\n")
        refreshed = self.refresh(1)  # the record now binds the edited state, so only --patch-before can see the edit
        self.assertEqual(refreshed.returncode, 0, refreshed.stdout)
        void = self.receipt_with(scripts, 2, "void", "--patch-before", before)
        self.assertEqual(void.returncode, 1, void.stdout)
        self.assertIn("void", void.stdout)
        self.assertFalse(self.path(3).exists(), "a void receipt writes nothing")
        # the control for the control: without the flag the same receipt is written, which is the gap
        silent = self.receipt_with(scripts, 2, "silent")
        self.assertEqual(silent.returncode, 0, silent.stdout)
        # restore the original bytes in a fresh copy of the folder state for the next assertion
        (self.repo / "src/add.js").write_bytes(b"module.exports=(a,b)=>a+b;\n")

    def test_an_edit_during_the_check_voids_the_receipt(self):
        self.check_void(SCRIPTS)

    def test_a_broken_copy_that_ignores_the_flag_writes_the_receipt(self):
        broken = broken_core(self.scratch.name, [("record.py", '    if before is not None and before != observed["patch"]:',
                                                  "    if False:")])
        with self.assertRaises(AssertionError):
            self.check_void(broken)

    def test_an_edit_that_is_restored_passes_and_the_limit_is_recorded(self):
        before = self.before()
        (self.repo / "src/add.js").write_bytes(b"module.exports=(a,b)=>a*b;\n")
        (self.repo / "src/add.js").write_bytes(b"module.exports=(a,b)=>a+b;\n")
        result = self.receipt_with(SCRIPTS, 1, "restored", "--patch-before", before)
        self.assertEqual(result.returncode, 0, result.stdout)
        receipt = r2.v.read_json(self.path(2))["evidence"][0]
        text = " ".join(receipt["limitations"])
        self.assertIn(before, text)
        self.assertRegex(text, r"(?i)endpoint")
        self.assertRegex(text, r"(?i)restored")

    def test_a_receipt_that_ran_without_a_before_fingerprint_says_so(self):
        result = self.receipt_with(SCRIPTS, 1, "plain")
        self.assertEqual(result.returncode, 0, result.stdout)
        notes = json.loads(result.stdout)["notes"]
        self.assertTrue(any("--patch-before" in n for n in notes), notes)

    def test_a_malformed_before_fingerprint_is_refused(self):
        result = self.receipt_with(SCRIPTS, 1, "bad", "--patch-before", "not-a-hash")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("--patch-before", result.stdout)
        self.assertFalse(self.path(2).exists())

    def test_a_receipt_that_ran_nothing_needs_no_before_fingerprint(self):
        result = run(SCRIPTS / "validate.py", "receipt", self.path(1), "--root", self.ev, "--repo", self.repo,
                     "--id", "blocked", "--claim", "a1", "--type", "unit", "--operation", "node --test", "--environment", "none",
                     "--status", "blocked", "--limitation", "node is not installed")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([n for n in json.loads(result.stdout)["notes"] if "--patch-before" in n], [])


# ---------------------------------------------------------------------------------------------------- EV-45
class DeriveFromReceiptsTests(Controlled):
    """The task validator recomputes what a record claims from its receipts: a stored pass flag, a saved aggregate
    or a doctored count is a cache that must agree with the evidence, never the authority."""

    def setUp(self):
        super().setUp()
        self.root = self.base / "ev"
        self.root.mkdir()
        self.task = fixtures.make_task(self.root)
        self.context = {k: self.task[k] for k in ("revision", "scope_id", "patch_id")}

    def errors(self, validate, task):
        return validate.check_task(task, self.root, self.context)

    def runtime_task(self):
        task = copy.deepcopy(self.task)
        task["evidence"][0].update(type="unit", exit_code=0, expected_exit=0)
        task.update(mode="investigate", verification="runtime-tested")
        task["acceptance"][0]["requires_runtime"] = True
        return task

    def check_stored_pass_over_a_failed_receipt(self, scripts):
        validate = load_validate(scripts)
        self.assertEqual(self.errors(validate, self.task), [])
        task = copy.deepcopy(self.task)
        task["evidence"][0].update(status="failed", passed=0, failed=1, exit_code=1)
        self.assertTrue(any("passing acceptance lacks passing evidence" in e for e in self.errors(validate, task)),
                        self.errors(validate, task))

    def test_acceptance_that_says_passed_over_a_failed_receipt_is_flagged(self):
        self.control([("record.py", 'if not refs or not all(e["status"] == "passed" for e in refs):',
                       'if False:')], self.check_stored_pass_over_a_failed_receipt)

    def check_doctored_counts(self, scripts):
        validate = load_validate(scripts)
        task = copy.deepcopy(self.task)
        task["evidence"][0].update(executed=2, collected=2, passed=1, failed=1)  # status still says passed
        found = self.errors(validate, task)
        self.assertTrue(any("passing status contradicts failures/exit" in e for e in found), found)
        task = copy.deepcopy(self.task)
        task["evidence"][0].update(status="failed", failed=0, passed=1)  # edited so the failure is gone
        found = self.errors(validate, task)
        self.assertTrue(any("failure status has no observed failure" in e for e in found), found)

    def test_counts_edited_to_match_a_flag_are_flagged(self):
        self.control([("evidence.py", 'if evidence["failed"] or evidence["exit_code"] != evidence["expected_exit"]:',
                       'if False:')], self.check_doctored_counts)

    def check_stored_verification(self, scripts):
        validate = load_validate(scripts)
        task = copy.deepcopy(self.task)
        task["verification"] = "runtime-tested"  # source evidence only: a stored claim the receipts do not back
        self.assertTrue(any("runtime-tested claim lacks runtime evidence" in e for e in self.errors(validate, task)),
                        self.errors(validate, task))

    def test_a_stored_verification_the_receipts_do_not_back_is_flagged(self):
        self.control([("record.py", 'errors.append("runtime-tested claim lacks runtime evidence")', "pass")],
                     self.check_stored_verification)

    def check_stored_completion(self, scripts):
        validate = load_validate(scripts)
        task = copy.deepcopy(self.task)
        task["acceptance"][0]["status"] = "not-run"  # the criterion is open; the record still says complete
        self.assertEqual(task["completion"], "complete")
        self.assertTrue(any("required acceptance incomplete or empty" in e for e in self.errors(validate, task)),
                        self.errors(validate, task))

    def test_a_stored_completion_the_criteria_do_not_back_is_flagged(self):
        self.control([("record.py", 'errors.append("required acceptance incomplete or empty")', "pass")],
                     self.check_stored_completion)


# ---------------------------------------------------------------------------------------------------- CM-43
class NothingToCheckIsNeverAPassTests(Controlled):
    def files(self):
        folder = self.base / "inputs"
        folder.mkdir(exist_ok=True)
        (folder / "empty.txt").write_bytes(b"")
        (folder / "garbage.txt").write_bytes(b"hello, this is not runner output\n")
        (folder / "empty.json").write_bytes(b"")
        (folder / "malformed.json").write_bytes(b"{not json")
        return folder

    def check_checks_cannot_tell(self, scripts):
        folder, checks = self.files(), pathlib.Path(scripts) / "checks.py"
        for name in ("empty.txt", "garbage.txt"):
            parsed = run(checks, "parse", folder / name)
            self.assertEqual(parsed.returncode, 2, name + ": " + parsed.stdout)
            self.assertEqual(json.loads(parsed.stdout)["tests"], [])
        compared = run(checks, "diff", folder / "empty.txt", folder / "empty.txt")
        self.assertEqual(compared.returncode, 2, compared.stdout)
        self.assertEqual(json.loads(compared.stdout)["verdict"], "inconclusive")

    def test_checks_py_exits_2_for_empty_and_unrecognised_output(self):
        self.control([("checks.py", 'return 0 if result["runner"] != "unknown" and result["tests"] else 2',
                       "return 0")], self.check_checks_cannot_tell)

    def test_validate_py_never_passes_empty_or_malformed_input(self):
        folder = self.files()
        for name in ("empty.json", "malformed.json"):
            result = run(SCRIPTS / "validate.py", "task", folder / name, "--root", folder)
            report = json.loads(result.stdout)
            self.assertEqual((result.returncode, report["status"]), (1, "failed"), result.stdout)
            self.assertTrue(any("malformed/unreadable input" in e for e in report["errors"]), report)
        self.assertEqual(run(SCRIPTS / "validate.py", "package", folder / "no-such-folder").returncode, 1)


if __name__ == "__main__":
    unittest.main()
