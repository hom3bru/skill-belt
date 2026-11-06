"""RT-1: a per-file coverage ledger. `diffscope.py coverage DIFF LEDGER` checks that every file of the saved diff carries
exactly one mark, reviewed or skipped with a concrete reason, so a file nobody looked at is a coverage failure and never
reads as clean.

The rules under test:
  - every file in the diff (added, deleted, renamed and binary ones too) needs a ledger entry;
  - a skip needs a concrete reason, and a vacuous one ("n/a", "skipped") is no reason, so the file stays unmarked;
  - one entry per file, an entry must name a file that is in the diff, and a stated change must match the diff's;
  - the report gives the total, reviewed, skipped and unmarked counts, and names every unmarked file;
  - exit 0 complete, 1 incomplete, 2 unreadable; the check looks at marks only and says it does not prove a review.

Run: python -B -m unittest discover -s skills/westack-review/tests -v
The script under test is loaded by path; WESTACK_REVIEW_DIFFSCOPE may point at another copy. Each rule also runs against a
deliberately broken copy of the script (one line of its source edited) and must be missed there, which shows the test can
see the rule.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("WESTACK_REVIEW_DIFFSCOPE")
                      or pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diffscope.py").resolve()


def load(path=SCRIPT):
    key = "westack_review_coverage_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


DIFF = """diff --git a/src/pager.py b/src/pager.py
index 1111111..2222222 100644
--- a/src/pager.py
+++ b/src/pager.py
@@ -1,2 +1,2 @@
 keep
-old
+new
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,1 @@
+# New
diff --git a/old.txt b/old.txt
deleted file mode 100644
index 4444444..0000000
--- a/old.txt
+++ /dev/null
@@ -1,1 +0,0 @@
-gone
diff --git a/lib/a.py b/lib/b.py
similarity index 100%
rename from lib/a.py
rename to lib/b.py
diff --git a/img/logo.png b/img/logo.png
index 5555555..6666666 100644
Binary files a/img/logo.png and b/img/logo.png differ
"""

FULL = [
    {"file": "src/pager.py", "change": "modified", "state": "reviewed"},
    {"file": "docs/new.md", "change": "added", "state": "reviewed"},
    {"file": "old.txt", "change": "deleted", "state": "reviewed"},
    {"file": "lib/b.py", "change": "renamed", "state": "reviewed"},
    {"file": "img/logo.png", "change": "binary", "state": "skipped", "reason": "binary asset; only its size changed"},
]
WITHOUT_OLD = [e for e in FULL if e["file"] != "old.txt"]


def entry(name, **fields):
    return dict(next(e for e in FULL if e["file"] == name), **fields)


class Coverage(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.files = self.m.parse(DIFF)

    def report(self, ledger):
        return self.m.coverage(self.files, ledger)

    def test_a_full_ledger_is_complete_and_counted(self):
        report = self.report(FULL)
        self.assertEqual(report["status"], "complete", report)
        self.assertEqual(report["totals"], {"files": 5, "reviewed": 4, "skipped": 1, "unmarked": 0})
        self.assertEqual(report["unmarked"], [])
        self.assertEqual(report["skipped"], [{"file": "img/logo.png", "reason": "binary asset; only its size changed"}])

    def test_a_file_with_neither_mark_is_a_coverage_failure_and_is_named(self):
        report = self.report(WITHOUT_OLD)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["unmarked"], ["old.txt"])
        self.assertEqual(report["totals"], {"files": 5, "reviewed": 3, "skipped": 1, "unmarked": 1})

    def test_an_empty_ledger_leaves_every_file_unmarked(self):
        report = self.report([])
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["totals"]["unmarked"], 5)

    def test_a_skip_needs_a_concrete_reason(self):
        for reason in (None, "", "   ", "n/a", "Skipped", "irrelevant", "TODO"):
            with self.subTest(reason=reason):
                skip = {k: v for k, v in entry("old.txt", state="skipped", reason=reason).items() if v is not None}
                report = self.report([e for e in FULL if e["file"] != "old.txt"] + [skip])
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["unmarked"], ["old.txt"], "a skip with no real reason is not a mark")
                self.assertTrue(any(p["entry"] == "old.txt" and "reason" in p["problem"] for p in report["problems"]))

    def test_a_concrete_reason_marks_the_file_skipped(self):
        skip = entry("old.txt", state="skipped", reason="removed file with no callers left in the repository")
        report = self.report(WITHOUT_OLD + [skip])
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["totals"]["skipped"], 2)

    def test_one_entry_per_file(self):
        report = self.report(FULL + [entry("src/pager.py", state="skipped", reason="generated output")])
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(any(p["entry"] == "src/pager.py" and "duplicate" in p["problem"] for p in report["problems"]))
        self.assertEqual(report["totals"]["files"], 5)

    def test_an_entry_for_a_file_not_in_the_diff_is_listed_and_fails(self):
        report = self.report(FULL + [{"file": "src/ghost.py", "state": "reviewed"}])
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["extra"], ["src/ghost.py"])
        self.assertEqual(report["totals"]["reviewed"], 4)

    def test_a_change_that_disagrees_with_the_diff_is_a_problem(self):
        report = self.report([entry("docs/new.md", change="modified")] + [e for e in FULL if e["file"] != "docs/new.md"])
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(any(p["entry"] == "docs/new.md" and "change" in p["problem"] for p in report["problems"]))

    def test_paths_match_across_separators_prefixes_and_a_rename_old_path(self):
        ledger = [dict(e) for e in FULL]
        ledger[0]["file"] = "./src\\pager.py"
        ledger[1]["file"] = "b/docs/new.md"
        ledger[3]["file"] = "lib/a.py"
        report = self.report(ledger)
        self.assertEqual(report["status"], "complete", report)

    def test_a_bad_state_or_a_nameless_entry_is_a_problem(self):
        report = self.report(WITHOUT_OLD + [{"file": "old.txt", "state": "looked-fine"}, {"state": "reviewed"}, "old.txt"])
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["unmarked"], ["old.txt"])
        self.assertEqual(len(report["problems"]), 3)

    def test_an_object_with_a_files_list_is_accepted_and_anything_else_is_refused(self):
        self.assertEqual(self.report({"files": FULL})["status"], "complete")
        for bad in ("src/pager.py", 7, {"files": "all"}, None):
            with self.subTest(bad=bad), self.assertRaises(self.m.DiffError):
                self.report(bad)

    def test_the_report_says_it_checks_marks_and_not_the_review(self):
        text = json.dumps(self.report(FULL)).lower()
        self.assertIn("not show", text)
        self.assertNotIn("approved", text)
        self.assertNotIn("all clear", text)


class CoverageCli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), "coverage", *args],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_exit_codes_and_the_diff_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "d.diff").write_bytes(DIFF.encode("utf-8"))
            (tmp / "empty.diff").write_text("", encoding="utf-8")
            (tmp / "full.json").write_text(json.dumps(FULL), encoding="utf-8")
            (tmp / "short.json").write_text(json.dumps(WITHOUT_OLD), encoding="utf-8")
            (tmp / "bad.json").write_text("not json", encoding="utf-8")
            ok = self.run_cli(str(tmp / "d.diff"), str(tmp / "full.json"))
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            body = json.loads(ok.stdout)
            self.assertEqual((body["mode"], body["status"]), ("coverage", "complete"))
            self.assertEqual(body["diff_sha256"], hashlib.sha256(DIFF.encode("utf-8")).hexdigest())
            short = self.run_cli(str(tmp / "d.diff"), str(tmp / "short.json"))
            self.assertEqual(short.returncode, 1)
            self.assertEqual(json.loads(short.stdout)["unmarked"], ["old.txt"])
            self.assertEqual(self.run_cli(str(tmp / "d.diff"), str(tmp / "bad.json")).returncode, 2)
            self.assertEqual(self.run_cli(str(tmp / "d.diff"), str(tmp / "missing.json")).returncode, 2)
            self.assertEqual(self.run_cli(str(tmp / "empty.diff"), str(tmp / "full.json")).returncode, 2)
            self.assertEqual(self.run_cli(str(tmp / "d.diff")).returncode, 64)


class BrokenCopies(unittest.TestCase):
    """Each copy has one rule edited out of the script's source and must accept the ledger the rule exists to refuse."""

    def broken(self, tmp, pattern, replacement):
        source = SCRIPT.read_text(encoding="utf-8")
        edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
        self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
        self.assertNotEqual(edited, source)
        target = pathlib.Path(tmp) / "diffscope_broken.py"
        target.write_text(edited, encoding="utf-8")
        return load(target)

    def status(self, module, ledger):
        return module.coverage(module.parse(DIFF), ledger)["status"]

    def test_a_check_that_counts_only_the_files_with_entries_passes_a_ledger_missing_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^    unmarked = .*$", "    unmarked = []")
            self.assertEqual(self.status(broken, WITHOUT_OLD), "complete")
        self.assertEqual(self.status(load(), WITHOUT_OLD), "incomplete")

    def test_without_the_vacuous_reason_list_an_empty_excuse_passes(self):
        skip = entry("old.txt", state="skipped", reason="n/a")
        ledger = WITHOUT_OLD + [skip]
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^VACUOUS_REASONS = .*$", "VACUOUS_REASONS = ()")
            self.assertEqual(self.status(broken, ledger), "complete")
        self.assertEqual(self.status(load(), ledger), "incomplete")

    def test_without_the_duplicate_rule_a_second_mark_passes(self):
        ledger = FULL + [entry("src/pager.py", state="skipped", reason="generated output")]
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^        if position in marked:$", "        if False:")
            self.assertEqual(self.status(broken, ledger), "complete")
        self.assertEqual(self.status(load(), ledger), "incomplete")

    def test_without_the_not_in_diff_rule_a_ghost_entry_passes(self):
        ledger = FULL + [{"file": "src/ghost.py", "state": "reviewed"}]
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^            extra\.append\(.*$", "            pass")
            self.assertEqual(self.status(broken, ledger), "complete")
        self.assertEqual(self.status(load(), ledger), "incomplete")

    def test_without_the_change_rule_a_mismatched_change_passes(self):
        ledger = [entry("docs/new.md", change="modified")] + [e for e in FULL if e["file"] != "docs/new.md"]
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^        if change and change != diff_file\[\"status\"\]:$", "        if False:")
            self.assertEqual(self.status(broken, ledger), "complete")
        self.assertEqual(self.status(load(), ledger), "incomplete")


class Discipline(unittest.TestCase):
    def test_the_script_still_reads_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import subprocess", "os.system", "eval(", "exec(", "urllib", "socket", "shutil.rmtree"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
