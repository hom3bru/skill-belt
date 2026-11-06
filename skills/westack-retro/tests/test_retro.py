"""Tests for westack-retro's scripts/retro.py on a synthetic saved git log. Local files only; no git runs.

Run from the repo root:  python -B -m unittest discover -s skills/westack-retro/tests
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import retro  # noqa: E402

US = "\x1f"


def commit(sha, when, subject, files, email="me@example.test", name="Me", parents="p1", trailers=""):
    head = "@@" + US.join([sha * 40 if len(sha) == 1 else sha, name, email, when, parents, subject, trailers])
    return head + "\n" + "".join("%s\t%s\t%s\n" % f for f in files) + "\n"


LOG = "".join([
    commit("a", "2026-11-02T09:00:00-08:00", "feat(api): add export", [(120, 4, "src/api/export.py"), (40, 0, "tests/test_export.py")]),
    commit("b", "2026-11-02T09:30:00-08:00", "fix: export encoding", [(5, 2, "src/api/export.py")]),
    commit("c", "2026-11-02T11:00:00-08:00", "docs: readme", [(10, 1, "README.md")]),
    commit("d", "2026-11-03T22:10:00-08:00", "refactor: split module",
           [(3, 3, "src/api/f%d.py" % i) for i in range(25)], email="ana@example.test", name="Ana",
           trailers="Claude <noreply@anthropic.com>;Bo <bo@example.test>"),
    commit("e", "2026-11-03T22:20:00-08:00", "Merge branch x", [(1, 1, "src/api/export.py")], parents="p1 p2"),
    commit("f", "2026-10-20T10:00:00-08:00", "feat: old work", [(2000, 0, "src/old.py")]),
])


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = retro.main(argv)
    return code, out.getvalue()


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.m = retro.metrics(retro.parse_log(LOG), date(2026, 11, 1), None, "me@example.test")

    def test_window_and_merges(self):
        self.assertEqual((self.m["commits"], self.m["merge_commits"], self.m["contributors"]), (4, 1, 2))

    def test_lines_and_test_ratio(self):
        self.assertEqual((self.m["insertions"], self.m["deletions"]), (120 + 40 + 5 + 10 + 75, 4 + 2 + 1 + 75))
        self.assertEqual(self.m["test_insertions"], 40)
        self.assertEqual(self.m["test_ratio"], round(40 / 250, 3))

    def test_weighted_commits_cap_files_at_twenty(self):
        self.assertEqual(self.m["weighted_commits"], 2 + 1 + 1 + 20)

    def test_sessions_split_at_45_minutes(self):
        s = self.m["sessions"]
        # 09:00 and 09:30 form one 30-minute session; 11:00 alone; 22:10 alone (the merge at 22:20 is excluded)
        self.assertEqual((s["count"], s["medium"], s["micro"], s["active_minutes"]), (3, 1, 2, 30))

    def test_types_sizes_hours_focus(self):
        self.assertEqual(self.m["types"], {"feat": 1, "fix": 1, "docs": 1, "refactor": 1})
        self.assertEqual(self.m["fix_ratio"], 0.25)
        self.assertEqual(self.m["sizes"], {"small": 2, "medium": 2, "large": 0, "xl": 0})
        self.assertEqual((self.m["hours"], self.m["peak_hour"]), ({"09": 2, "11": 1, "22": 1}, "09"))
        self.assertEqual(self.m["focus"]["dir"], "src/")

    def test_hotspots_biggest_authors(self):
        self.assertEqual(self.m["hotspots"][0], {"file": "src/api/export.py", "changes": 2})
        self.assertEqual(self.m["biggest_commit"]["subject"], "feat(api): add export")
        self.assertEqual([a["email"] for a in self.m["authors"]], ["me@example.test", "ana@example.test"])

    def test_ai_coauthors_are_counted_apart_from_people(self):
        self.assertEqual((self.m["ai_assisted_commits"], self.m["human_coauthors"]), (1, {"Bo <bo@example.test>": 1}))

    def test_streaks(self):
        self.assertEqual(self.m["team_streak"], {"days": 2, "anchor": "2026-11-03"})
        self.assertEqual(self.m["you_streak"], {"days": 1, "anchor": "2026-11-02"})

    def test_until_and_an_empty_window(self):
        m = retro.metrics(retro.parse_log(LOG), date(2026, 11, 1), date(2026, 11, 3), None)
        self.assertEqual(m["commits"], 3)
        empty = retro.metrics(retro.parse_log(LOG), date(2026, 12, 1), None, None)
        self.assertEqual((empty["guard"], empty["commits"], empty["test_ratio"]), ("empty-window", 0, None))


class CompareDiscoverCliTests(unittest.TestCase):
    def test_compare(self):
        prev = retro.metrics(retro.parse_log(LOG), date(2026, 10, 15), date(2026, 11, 1), None)
        cur = retro.metrics(retro.parse_log(LOG), date(2026, 11, 1), None, None)
        c = retro.compare(prev, cur)
        self.assertEqual(c["metrics"]["commits"], {"previous": 1, "current": 4, "delta": 3})

    def test_discover_reads_cwd_from_recent_session_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, ".claude", "projects")
            (root / "p1").mkdir(parents=True)
            (root / "p1" / "s1.jsonl").write_text('{"type":"x"}\n{"cwd":"C:\\\\code\\\\app","msg":1}\n', encoding="utf-8")
            (root / "p1" / "s2.jsonl").write_text('{"cwd":"C:\\\\code\\\\app"}\n', encoding="utf-8")
            old = root / "p1" / "old.jsonl"
            old.write_text('{"cwd":"C:\\\\code\\\\gone"}\n', encoding="utf-8")
            past = time.time() - 40 * 86400
            os.utime(old, (past, past))
            r = retro.discover([str(root)], date.today().replace(day=1) if date.today().day > 1 else date.today())
        self.assertEqual([(x["cwd"], x["sessions"], x["tools"]) for x in r["repositories"]], [("C:\\code\\app", 2, ["claude"])])

    def test_discover_uses_the_nearest_host_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            for relative, expected in (("codex-cache/.claude/projects", "claude"),
                                       (".claude/cache/.codex/sessions", "codex")):
                with self.subTest(root=relative):
                    root = Path(tmp, relative)
                    root.mkdir(parents=True)
                    (root / "session.jsonl").write_text('{"cwd":"fixture"}\n', encoding="utf-8")
                    report = retro.discover([str(root)], date.today())
                    self.assertEqual(report["repositories"][0]["tools"], [expected])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp, "log.txt")
            log.write_text(LOG, encoding="utf-8")
            self.assertEqual(run(["metrics", str(log), "--since", "2026-11-01"])[0], 0)
            self.assertEqual(run(["metrics", str(log), "--since", "2027-01-01"])[0], 1)
            self.assertEqual(run(["metrics", str(log)])[0], 64)
            bad = Path(tmp, "bad.txt")
            bad.write_text("@@only|two\n", encoding="utf-8")
            self.assertEqual(run(["metrics", str(bad), "--since", "2026-11-01"])[0], 64)


if __name__ == "__main__":
    unittest.main()
