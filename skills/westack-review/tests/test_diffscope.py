"""Tests for scripts/diffscope.py: parse a saved unified diff, summarise it, and check that each finding's
location is on a changed line (introduced) or names the changed line that introduced it.

Run: python -B -m unittest discover -s skills/westack-review/tests -v
The script under test is loaded by path; WESTACK_REVIEW_DIFFSCOPE may point at another copy (broken-copy
controls run this same file against a deliberately broken copy).
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("WESTACK_REVIEW_DIFFSCOPE")
                      or pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diffscope.py").resolve()


def load():
    key = "westack_review_diffscope_" + hashlib.sha256(str(SCRIPT).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


MODIFIED = """diff --git a/src/pager.py b/src/pager.py
index 1111111..2222222 100644
--- a/src/pager.py
+++ b/src/pager.py
@@ -10,7 +10,9 @@ def page_count(total, size):

 def page_slice(items, page, size=None):
     size = clamp_page_size(size)
-    return items[(page - 1) * size:(page - 1) * size + size]
+    start = (page - 1) * size
+    end = start + size
+    return items[start:end - 1]


 def other():
"""

NEW_AND_DELETED = """diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+# New
+text
diff --git a/old.txt b/old.txt
deleted file mode 100644
index 4444444..0000000
--- a/old.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-gone one
-gone two
"""

RENAME_AND_BINARY = """diff --git a/lib/a.py b/lib/b.py
similarity index 100%
rename from lib/a.py
rename to lib/b.py
diff --git a/img/logo.png b/img/logo.png
index 5555555..6666666 100644
Binary files a/img/logo.png and b/img/logo.png differ
"""

# Content lines that look like headers must stay content: the hunk counts decide.
HEADER_LOOKALIKES = """diff --git a/notes.txt b/notes.txt
index 7777777..8888888 100644
--- a/notes.txt
+++ b/notes.txt
@@ -1,3 +1,3 @@
 keep
--- a/ removed line that starts with two dashes
+++ b/ added line that starts with two pluses
 tail
"""

QUOTED = """diff --git "a/caf\\303\\251 menu.txt" "b/caf\\303\\251 menu.txt"
index 9999999..aaaaaaa 100644
--- "a/caf\\303\\251 menu.txt"
+++ "b/caf\\303\\251 menu.txt"
@@ -1 +1 @@
-old
+new
"""

PLAIN_UNIFIED = """--- a/x.c\t2026-10-01 10:00:00
+++ b/x.c\t2026-10-02 10:00:00
@@ -5,2 +5,3 @@
 int a;
+int b;
 int c;
"""

STAT_ONLY = """ src/pager.py | 4 +++-
 1 file changed, 3 insertions(+), 1 deletion(-)
"""


class Parse(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_modified_file_lines(self):
        files = self.m.parse(MODIFIED)
        self.assertEqual(len(files), 1)
        f = files[0]
        self.assertEqual((f["old_path"], f["new_path"], f["status"]), ("src/pager.py", "src/pager.py", "modified"))
        self.assertEqual(sorted(f["added"]), [13, 14, 15])
        self.assertEqual(sorted(f["removed"]), [13])
        self.assertIn(12, f["context_new"])
        self.assertEqual(f["hunks"], [{"old_start": 10, "old_len": 7, "new_start": 10, "new_len": 9}])

    def test_new_and_deleted_files(self):
        files = {f["new_path"] or f["old_path"]: f for f in self.m.parse(NEW_AND_DELETED)}
        self.assertEqual(files["docs/new.md"]["status"], "added")
        self.assertIsNone(files["docs/new.md"]["old_path"])
        self.assertEqual(sorted(files["docs/new.md"]["added"]), [1, 2])
        self.assertEqual(files["old.txt"]["status"], "deleted")
        self.assertIsNone(files["old.txt"]["new_path"])
        self.assertEqual(sorted(files["old.txt"]["removed"]), [1, 2])

    def test_rename_and_binary(self):
        files = self.m.parse(RENAME_AND_BINARY)
        self.assertEqual([(f["old_path"], f["new_path"], f["status"]) for f in files],
                         [("lib/a.py", "lib/b.py", "renamed"), ("img/logo.png", "img/logo.png", "binary")])
        self.assertEqual(files[0]["added"], [])

    def test_header_lookalikes_inside_a_hunk_are_content(self):
        files = self.m.parse(HEADER_LOOKALIKES)
        self.assertEqual(len(files), 1)
        self.assertEqual(sorted(files[0]["removed"]), [2])
        self.assertEqual(sorted(files[0]["added"]), [2])

    def test_quoted_path_with_octal_escapes(self):
        files = self.m.parse(QUOTED)
        self.assertEqual(files[0]["new_path"], "café menu.txt")

    def test_plain_unified_diff_without_git_header(self):
        files = self.m.parse(PLAIN_UNIFIED)
        self.assertEqual(files[0]["new_path"], "x.c")
        self.assertEqual(sorted(files[0]["added"]), [6])

    def test_decode_utf16_with_bom_and_crlf(self):
        data = MODIFIED.replace("\n", "\r\n").encode("utf-16")
        files = self.m.parse(self.m.decode(data))
        self.assertEqual(sorted(files[0]["added"]), [13, 14, 15])

    def test_not_a_diff_is_refused(self):
        with self.assertRaises(self.m.DiffError):
            self.m.parse(STAT_ONLY)
        with self.assertRaises(self.m.DiffError):
            self.m.parse("")

    def test_truncated_hunk_is_refused(self):
        with self.assertRaises(self.m.DiffError):
            self.m.parse(MODIFIED.rsplit("\n", 4)[0] + "\n")


class Locate(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.files = self.m.parse(MODIFIED + NEW_AND_DELETED + RENAME_AND_BINARY)

    def test_kinds(self):
        loc = lambda *a: self.m.locate(self.files, *a)
        self.assertEqual(loc("src/pager.py", 15, "new"), "added")
        self.assertEqual(loc("src/pager.py", 12, "new"), "context")
        self.assertEqual(loc("src/pager.py", 3, "new"), "unchanged")
        self.assertEqual(loc("src/pager.py", 13, "old"), "removed")
        self.assertEqual(loc("src/other.py", 1, "new"), "file-not-in-diff")
        self.assertEqual(loc("img/logo.png", 1, "new"), "binary")
        self.assertEqual(loc("old.txt", 1, "old"), "removed")
        self.assertEqual(loc("lib/b.py", 4, "new"), "unchanged")

    def test_path_normalisation(self):
        self.assertEqual(self.m.locate(self.files, "./src\\pager.py", 15, "new"), "added")
        self.assertEqual(self.m.locate(self.files, "b/src/pager.py", 15, "new"), "added")


class Check(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.files = self.m.parse(MODIFIED)

    def verdicts(self, findings):
        return {r["id"]: r["verdict"] for r in self.m.check(self.files, findings)["findings"]}

    def test_verdicts(self):
        got = self.verdicts([
            {"id": "F1", "file": "src/pager.py", "line": 15},
            {"id": "F2", "file": "src/pager.py", "line": 13, "side": "old"},
            {"id": "F3", "file": "src/api.py", "line": 40,
             "introduced_at": {"file": "src/pager.py", "line": 15}},
            {"id": "F4", "file": "src/pager.py", "line": 3},
            {"id": "F5", "file": "src/ghost.py", "line": 9},
            {"id": "F6", "file": "src/pager.py"},
            {"id": "F7", "file": "src/api.py", "line": 40,
             "introduced_at": {"file": "src/pager.py", "line": 3}},
        ])
        self.assertEqual(got, {"F1": "in-diff", "F2": "in-diff", "F3": "affected-elsewhere",
                               "F4": "not-introduced", "F5": "not-located", "F6": "not-located",
                               "F7": "not-introduced"})

    def test_counts_and_status(self):
        report = self.m.check(self.files, [{"id": "F1", "file": "src/pager.py", "line": 15}])
        self.assertEqual(report["status"], "located")
        report = self.m.check(self.files, [{"id": "F1", "file": "src/pager.py", "line": 15},
                                           {"id": "F2", "file": "src/pager.py", "line": 3}])
        self.assertEqual(report["status"], "needs-provenance")
        self.assertEqual(report["counts"], {"in-diff": 1, "affected-elsewhere": 0, "not-introduced": 1,
                                            "not-located": 0})

    def test_duplicate_ids_refused(self):
        with self.assertRaises(self.m.DiffError):
            self.m.check(self.files, [{"id": "F1", "file": "a", "line": 1}, {"id": "F1", "file": "b", "line": 2}])


class Summary(unittest.TestCase):
    def test_summary_fields(self):
        m = load()
        data = MODIFIED.encode()
        s = m.summarise(m.parse(MODIFIED), data, base="abc123", head="def456")
        self.assertEqual(s["diff_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual((s["base"], s["head"]), ("abc123", "def456"))
        self.assertEqual(s["totals"], {"files": 1, "added": 3, "removed": 1})
        entry = s["files"][0]
        self.assertEqual(entry["added_ranges"], [[13, 15]])
        self.assertEqual(entry["removed_ranges"], [[13, 13]])
        self.assertEqual(s["removed_behaviour_sites"], [{"file": "src/pager.py", "old_lines": [[13, 13]]}])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), *args], capture_output=True, text=True,
                              env=env, timeout=120)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "d.diff").write_text(MODIFIED, encoding="utf-8")
            (tmp / "stat.txt").write_text(STAT_ONLY, encoding="utf-8")
            (tmp / "empty.diff").write_text("", encoding="utf-8")
            (tmp / "good.json").write_text(json.dumps([{"id": "F1", "file": "src/pager.py", "line": 15}]))
            (tmp / "mixed.json").write_text(json.dumps({"findings": [
                {"id": "F1", "file": "src/pager.py", "line": 15}, {"id": "F2", "file": "src/x.py", "line": 1}]}))
            (tmp / "bad.json").write_text("not json")
            ok = self.run_cli("summary", str(tmp / "d.diff"), "--base", "abc")
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(json.loads(ok.stdout)["totals"]["added"], 3)
            self.assertEqual(self.run_cli("summary", str(tmp / "stat.txt")).returncode, 2)
            self.assertEqual(self.run_cli("summary", str(tmp / "empty.diff")).returncode, 2)
            self.assertEqual(self.run_cli("check", str(tmp / "d.diff"), str(tmp / "good.json")).returncode, 0)
            mixed = self.run_cli("check", str(tmp / "d.diff"), str(tmp / "mixed.json"))
            self.assertEqual(mixed.returncode, 1)
            self.assertEqual(json.loads(mixed.stdout)["counts"]["not-located"], 1)
            self.assertEqual(self.run_cli("check", str(tmp / "d.diff"), str(tmp / "bad.json")).returncode, 2)
            self.assertEqual(self.run_cli("nonsense").returncode, 64)


class Discipline(unittest.TestCase):
    def test_reads_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import subprocess", "os.system", "eval(", "exec(", "urllib", "socket", "shutil.rmtree"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
