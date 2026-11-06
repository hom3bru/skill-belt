"""Tests for westack-onboard's index governance: trust tiers, the quarantined policy file and the search-guidance
block. Temporary git repositories and a temporary config folder; each rule has an in-suite broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-onboard/tests
"""
import contextlib
import io
import json
import unittest
from unittest import mock

from test_codeindex import Fixture, broken, ci


class TierTests(Fixture):
    def setUp(self):
        super().setUp()
        self.git("remote", "add", "origin", "https://user:tok@GitHub.com/Org/Repo.git")

    def test_the_key_is_the_normalised_remote(self):
        self.assertEqual(ci.repo_key(self.repo), "github.com/org/repo")

    def test_unset_and_read_write_allow_everything(self):
        self.assertEqual(ci.tier_for(self.repo)["tier"], "unset")
        self.assertEqual(self.sync()[0], 0)
        ci.set_tier(self.repo, "read-write")
        self.assertEqual(self.sync("update")[0], 0)
        self.assertEqual(self.search("exponential backoff")[0], "pkg/retry.py")

    def test_read_only_refuses_build_and_update_but_allows_search(self):
        self.sync()
        ci.set_tier(self.repo, "read-only")
        for mode in ("build", "update"):
            with self.subTest(mode=mode), self.assertRaises(ci.PolicyRefused):
                self.sync(mode)
        base = ["--repo", str(self.repo), "--db", str(self.db)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ci.main(["search", *base, "backoff"]), 0)
            self.assertEqual(ci.main(["update", *base]), 77)

    def test_deny_refuses_build_and_search(self):
        self.sync()
        ci.set_tier(self.repo, "deny")
        with self.assertRaises(ci.PolicyRefused):
            self.sync()
        base = ["--repo", str(self.repo), "--db", str(self.db)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ci.main(["search", *base, "backoff"]), 77)
            self.assertEqual(ci.main(["callers", *base, "retry"]), 77)
        ci.set_tier(self.repo, "unset")
        self.assertEqual(ci.tier_for(self.repo)["tier"], "unset")

    def test_the_policy_matches_however_the_remote_is_spelled(self):
        ci.policy_path().parent.mkdir(parents=True, exist_ok=True)
        ci.policy_path().write_text(json.dumps({"format": ci.POLICY_FORMAT,
                                                "remotes": {"GitHub.com/Org/Repo": "deny"}}), encoding="utf-8")
        self.assertEqual(ci.tier_for(self.repo)["tier"], "deny")

    def test_the_control_a_copy_that_ignores_read_only_builds_anyway(self):
        b = broken('(t["tier"] == "read-only" and action in ("build", "update", "ping"))',
                   '(t["tier"] == "read-only" and False)', "codeindex_ignores_read_only")
        ci.set_tier(self.repo, "read-only")
        self.assertEqual(b.sync(self.repo, self.db, "build")[0], 0, "the broken copy writes a read-only index")

    def test_the_control_without_lower_case_the_spelled_tier_is_missed(self):
        b = broken("    return u.lower()\n", "    return u\n", "codeindex_case_sensitive")
        ci.policy_path().parent.mkdir(parents=True, exist_ok=True)
        ci.policy_path().write_text(json.dumps({"format": ci.POLICY_FORMAT, "remotes": {"github.com/org/repo": "deny"}}),
                                    encoding="utf-8")
        self.assertEqual(b.tier_for(self.repo)["tier"], "unset", "the broken key misses the deny")


class NormaliseTests(unittest.TestCase):
    def test_cases(self):
        cases = {"https://github.com/org/repo": "github.com/org/repo",
                 "https://github.com/org/repo/": "github.com/org/repo",
                 "http://x-token@gitlab.example/Group/Sub/Repo.git": "gitlab.example/group/sub/repo",
                 "ssh://git@github.com/Org/Repo.git": "github.com/org/repo",
                 "git@github.com:Org/Repo": "github.com/org/repo",
                 "git@host.example:2222/org/repo.git": "host.example:2222/org/repo"}
        for url, want in cases.items():
            with self.subTest(url=url):
                self.assertEqual(ci.normalise_remote(url), want)


class QuarantineTests(Fixture):
    def test_a_corrupt_policy_is_moved_aside_and_fails_closed(self):
        ci.policy_path().parent.mkdir(parents=True, exist_ok=True)
        ci.policy_path().write_text("{not json", encoding="utf-8")
        t = ci.tier_for(self.repo)
        self.assertEqual(t["tier"], "read-only")
        self.assertFalse(ci.policy_path().exists())
        self.assertEqual(len(list(ci.policy_path().parent.glob("index-policy.json.corrupt-*"))), 1)
        with self.assertRaises(ci.PolicyRefused):
            self.sync()
        self.assertEqual(ci.tier_for(self.repo)["tier"], "read-only", "still closed on the next run")
        ci.set_tier(self.repo, "read-write")
        self.assertEqual(self.sync()[0], 0, "a new policy opens it again")
        verdict = ci.doctor(self.repo, self.db, ci.config())
        self.assertIn("policy", [c["check"] for c in verdict["checks"] if c["level"] == "WARN"])

    def test_a_policy_with_an_unknown_tier_is_corrupt_too(self):
        ci.policy_path().parent.mkdir(parents=True, exist_ok=True)
        ci.policy_path().write_text(json.dumps({"format": ci.POLICY_FORMAT, "remotes": {"x": "everyone"}}),
                                    encoding="utf-8")
        self.assertEqual(ci.tier_for(self.repo)["tier"], "read-only")

    def test_the_control_without_fail_closed_a_corrupt_file_opens_everything(self):
        b = broken('"fail_closed": bool(quarantined)', '"fail_closed": False', "codeindex_fail_open")
        ci.policy_path().parent.mkdir(parents=True, exist_ok=True)
        ci.policy_path().write_text("{not json", encoding="utf-8")
        b.tier_for(self.repo)
        self.assertEqual(b.tier_for(self.repo)["tier"], "unset", "the broken copy opens up on the second run")


class GuidanceTests(Fixture):
    def setUp(self):
        super().setUp()
        self.write("AGENTS.md", "# Agent rules\n\nBe careful.\n")
        self.commit("agents")
        self.sync()

    def agents(self):
        return (self.repo / "AGENTS.md").read_text(encoding="utf-8")

    def test_a_passing_round_trip_writes_the_block_once(self):
        r = ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        self.assertEqual((r["ping"]["passed"], r["ping"]["tries"], r["action"], r["written"]), (True, 1, "write", True))
        self.assertEqual(self.agents().count(ci.GUIDE_START), 1)
        self.assertTrue(self.agents().startswith("# Agent rules\n\nBe careful.\n\n" + ci.GUIDE_START))
        again = ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        self.assertEqual((again["action"], again["written"]), ("unchanged", False))
        self.assertEqual(self.search("westackping"), [], "the ping page is gone from the index")

    def test_a_dry_run_changes_nothing(self):
        r = ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md")
        self.assertEqual((r["action"], r["written"]), ("write", False))
        self.assertNotIn(ci.GUIDE_START, self.agents())

    def test_a_failing_round_trip_removes_the_block(self):
        ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        with mock.patch.object(ci, "search", lambda *a, **k: {"results": []}):
            r = ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        self.assertEqual((r["ping"]["passed"], r["ping"]["tries"], r["action"]), (False, 3, "remove"))
        self.assertEqual(self.agents(), "# Agent rules\n\nBe careful.\n", "the file is back as it was")

    def test_a_read_only_tier_fails_the_ping_and_removes_the_block(self):
        ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        ci.set_tier(self.repo, "read-only")
        r = ci.guidance(self.repo, self.db, ci.config(), "AGENTS.md", write=True)
        self.assertEqual((r["ping"]["passed"], r["action"]), (False, "remove"))
        self.assertIn("read-only", r["ping"]["reason"])

    def test_only_the_instruction_files(self):
        for bad in ("README.md", "../AGENTS.md", "docs/CLAUDE.md/../../x"):
            with self.subTest(file=bad), self.assertRaises(ci.UsageError):
                ci.guidance(self.repo, self.db, ci.config(), bad)

    def test_the_control_a_copy_that_writes_regardless_keeps_a_false_block(self):
        b = broken('    if result["passed"]:\n', "    if True:\n", "codeindex_always_guide")
        with mock.patch.object(b, "search", lambda *a, **k: {"results": []}):
            r = b.guidance(self.repo, self.db, b.config(), "AGENTS.md", write=True)
        self.assertFalse(r["ping"]["passed"])
        self.assertIn(ci.GUIDE_START, self.agents(), "the broken copy writes the block though the ping failed")


if __name__ == "__main__":
    unittest.main()
