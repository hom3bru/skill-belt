"""Tests for westack-ship's scripts/modernize.py on temporary git repositories: a stale branch replayed onto a moved
base on a new branch, the range-diff recorded and parsed, the modernize, rework and close rules, and the push rules.
The tests run git to build the fixtures; the helper reads saved output only. Each rule has a broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-ship/tests
"""
import copy
import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "modernize.py"
GIT = shutil.which("git")


def load(path=SCRIPT, name="westack_modernize_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


md = load()


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        return load(path, name)


APP = "".join(f"line {i}\n" for i in range(1, 13))


@unittest.skipUnless(GIT, "git is not on PATH")
class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        for k, v in (("user.email", "t@example.test"), ("user.name", "Test"), ("core.autocrlf", "false")):
            self.git("config", k, v)
        self.write("app.py", APP)
        self.base0 = self.commit("base")
        self.git("switch", "-q", "-c", "feature")
        self.write("app.py", APP.replace("line 6\n", "line 6 changed by the feature\n"))
        self.commit("feature: change line 6")
        self.write("feature.py", "def feature():\n    return 1\n")
        self.old_head = self.commit("feature: add feature.py")
        self.git("switch", "-q", "main")

    def git(self, *args, check=True):
        return subprocess.run([GIT, "-C", str(self.root), *args], check=check, capture_output=True, text=True).stdout

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD").strip()

    def replay(self):
        """Replay feature onto main on a new branch; the original is never touched. Returns the range-diff, or ""
        when every patch was already upstream (git cannot range-diff an empty range); self.rebase_log keeps the
        rebase's own messages."""
        self.git("switch", "-q", "-c", "modernize/feature", "feature")
        rebase = subprocess.run([GIT, "-C", str(self.root), "rebase", "main"], check=True, capture_output=True, text=True)
        self.rebase_log = rebase.stdout + rebase.stderr
        new_count = int(self.git("rev-list", "--count", "main..modernize/feature"))
        out = self.git("range-diff", f"{self.base0}..{self.old_head}", "main..modernize/feature") if new_count else ""
        self.git("switch", "-q", "main")
        return out

    def record(self, rangediff, **over):
        rec = {"format": md.FORMAT, "branch": "feature", "base": "main", "old_head": self.old_head,
               "merge_base": self.base0,
               "merges_in_range": int(self.git("rev-list", "--merges", "--count", f"{self.base0}..{self.old_head}")),
               "new_branch": "modernize/feature",
               "range_diff": {"sha256": hashlib.sha256(rangediff.encode()).hexdigest(),
                              "pairs": md.parse_rangediff(rangediff)},
               "explained": {}, "tests_after": {"command": "python -m pytest -q", "exit": 0},
               "disposition": "modernize", "reason": "the feature is still wanted and applies to today's base"}
        rec.update(over)
        return rec


class ReplayTests(Repo):
    def test_a_clean_replay_onto_a_moved_base(self):
        self.write("README.md", "# moved on\n")
        self.commit("main: unrelated work")
        out = self.replay()
        self.assertEqual(self.git("rev-parse", "feature").strip(), self.old_head, "the original branch is untouched")
        pairs = md.parse_rangediff(out)
        self.assertEqual([(p["old"], p["status"], p["new"]) for p in pairs], [(1, "same", 1), (2, "same", 2)])
        self.assertEqual(md.check(self.record(out)), [])

    def test_a_changed_patch_must_be_explained(self):
        self.write("app.py", APP.replace("line 4\n", "line 4 moved on main\n"))
        self.commit("main: edit near the feature")
        out = self.replay()
        pairs = md.parse_rangediff(out)
        self.assertEqual([p["status"] for p in pairs], ["changed", "same"])
        rec = self.record(out)
        self.assertIn("old patch 1 (feature: change line 6) is changed", " | ".join(md.check(rec)))
        rec["explained"] = {"1": "context only: main edited line 4 beside the feature's line 6"}
        self.assertEqual(md.check(rec), [])

    def test_the_control_without_the_explanation_rule_accepts_an_unexplained_change(self):
        b = broken('                if p.get("status") in ("changed", "dropped"):\n', "                if False:\n",
                   "modernize_no_explain")
        self.write("app.py", APP.replace("line 4\n", "line 4 moved on main\n"))
        self.commit("main: edit near the feature")
        rec = self.record(self.replay())
        self.assertEqual(b.check(rec), [], "the broken copy lets a changed patch through unexplained")

    def test_already_upstream_is_a_close(self):
        self.git("cherry-pick", self.old_head + "~1", self.old_head)
        out = self.replay()
        self.assertEqual(out, "", "nothing is left to replay, so there is no range to diff")
        self.assertEqual(self.git("rev-parse", "modernize/feature"), self.git("rev-parse", "main"),
                         "the replay is the base itself: every patch was already upstream")
        # git usually says "skipped previously applied commit" for each, but one gate run on 2026-11-04 printed nothing
        # and still dropped both, so the empty replay is the evidence, not the warning.
        self.assertIn(self.rebase_log.count("skipped previously applied commit"), (0, 2))
        close = self.record(out, disposition="close", reason="both patches are already on main",
                            superseded_by=self.git("rev-parse", "main").strip(), range_diff=None,
                            evidence="rebase: 2 x skipped previously applied commit; main..modernize/feature is empty")
        self.assertEqual(md.check(close), [])
        self.assertIn("close names what superseded it", " | ".join(md.check(dict(close, superseded_by=""))))
        self.assertIn("closing a PR is the owner's decision", " | ".join(md.check(dict(close, closed=True))))

    def test_merges_in_the_range_refuse_a_modernize(self):
        self.write("README.md", "# moved on\n")
        self.commit("main: unrelated work")
        self.git("switch", "-q", "feature")
        self.git("merge", "-q", "--no-edit", "main")
        self.old_head = self.git("rev-parse", "HEAD").strip()
        self.git("switch", "-q", "main")
        rec = self.record("1:  abc1234 = 1:  def5678 feature: change line 6\n")
        self.assertEqual(rec["merges_in_range"], 1)
        self.assertIn("the range holds merge commits", " | ".join(md.check(rec)))
        rework = dict(rec, disposition="rework", next_change="redo the feature as one commit on today's main")
        self.assertEqual(md.check(rework), [])

    def test_the_control_without_the_merge_rule_replays_a_merge(self):
        b = broken('        elif rec["merges_in_range"] > 0:\n', "        elif False:\n", "modernize_ignores_merges")
        rec = self.record("1:  abc1234 = 1:  def5678 x\n", merges_in_range=2)
        self.assertEqual(b.check(rec), [], "the broken copy replays over merge commits")

    def test_the_original_branch_is_never_the_replay(self):
        rec = self.record("1:  abc1234 = 1:  def5678 x\n", new_branch="feature")
        self.assertIn("new_branch: replay onto a new branch", " | ".join(md.check(rec)))
        b = broken('or rec.get("new_branch") == rec.get("branch"):', ":", "modernize_same_branch")
        self.assertEqual(b.check(rec), [], "the broken copy rewrites the original branch")


class PushTests(Repo):
    def push(self, **over):
        p = {"branch": "feature", "grant": {"by": "the user", "said": "push the modernized feature branch", "branch": "feature"},
             "command": f"git push --force-with-lease=feature:{self.old_head} origin modernize/feature:feature"}
        p.update(over)
        return p

    def test_a_push_needs_a_grant_and_a_pinned_lease(self):
        rec = self.record("1:  abc1234 = 1:  def5678 x\n", push=self.push())
        self.assertEqual(md.check(rec), [])
        no_grant = self.record("1:  abc1234 = 1:  def5678 x\n", push=self.push(grant={}))
        self.assertIn("push: a grant with who and their words", " | ".join(md.check(no_grant)))
        forced = self.record("1:  abc1234 = 1:  def5678 x\n", push=self.push(command="git push --force origin HEAD:feature"))
        self.assertIn("never --force", " | ".join(md.check(forced)))
        bare = self.record("1:  abc1234 = 1:  def5678 x\n", push=self.push(command="git push --force-with-lease origin HEAD:feature"))
        self.assertIn("never --force", " | ".join(md.check(bare)))

    def test_rework_and_close_push_nothing_and_failing_tests_block_the_push(self):
        rework = self.record("", disposition="rework", next_change="x", push=self.push())
        self.assertIn("rework pushes nothing", md.check(rework))
        red = self.record("1:  abc1234 = 1:  def5678 x\n", tests_after={"command": "pytest", "exit": 1}, push=self.push())
        self.assertIn("the replayed branch fails its tests: no push", md.check(red))

    def test_the_control_without_the_lease_rule_takes_a_bare_force(self):
        b = broken('        if re.search(r"(?<![\\w-])(--force|-f)(?![\\w-])", command) or lease not in command:\n',
                   "        if False:\n", "modernize_any_force")
        forced = self.record("1:  abc1234 = 1:  def5678 x\n", push=self.push(command="git push --force origin HEAD:feature"))
        self.assertEqual(b.check(forced), [], "the broken copy force-pushes over whatever is there")

    def test_the_control_letting_close_push(self):
        b = broken("        if push:\n            errors.append(f\"{disposition} pushes nothing\")\n", "", "modernize_close_pushes")
        close = self.record("", disposition="close", reason="r", superseded_by="abc", push=self.push())
        self.assertNotIn("close pushes nothing", b.check(close))
        self.assertIn("close pushes nothing", md.check(close))


class CliTests(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "rd.txt")
            p.write_text("1:  abc1234 ! 1:  def5678 subject one\n-:  ------- > 2:  0123abc new one\n", encoding="utf-8")
            self.assertEqual(md.main(["rangediff", str(p)]), 0)
            self.assertEqual([x["status"] for x in md.parse_rangediff(p.read_text())], ["changed", "added"])
            self.assertEqual(md.main(["check", str(p)]), 64)
        self.assertEqual(md.main([]), 64)


if __name__ == "__main__":
    unittest.main()
