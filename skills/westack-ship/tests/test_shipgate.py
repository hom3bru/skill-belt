"""Tests for westack-ship's shipgate.py: the pre-delivery gate over saved git, forge and repository output.

Run from the repo root:  python -B -m unittest discover -s skills/westack-ship/tests -v
SHIPGATE_UNDER_TEST=<path> points the suite at another copy (a broken-copy control).
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("SHIPGATE_UNDER_TEST") or HERE.parent / "scripts" / "shipgate.py")


def load():
    spec = importlib.util.spec_from_file_location("westack_ship_shipgate_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sg = load()
OID = "a" * 40
OTHER = "b" * 40


def v2(branch="feature", oid=OID, upstream="origin/feature", ahead=0, behind=0, lines=()):
    """`git status --porcelain=v2 --branch --untracked-files=all` output."""
    out = ["# branch.oid " + oid, "# branch.head " + branch]
    if upstream:
        out += ["# branch.upstream " + upstream, "# branch.ab +%d -%d" % (ahead, behind)]
    return "\n".join(out + list(lines)) + "\n"


TRACKED = "1 .M N... 100644 100644 100644 %s %s src/app.py" % ("1" * 40, "1" * 40)
UNTRACKED = "? notes/scratch.txt"
CONFLICT = "u UU N... 100644 100644 100644 100644 %s %s %s src/merge.py" % ("1" * 40, "2" * 40, "3" * 40)
REMOTES = "origin\t/tmp/remote.git (fetch)\norigin\t/tmp/remote.git (push)\n"
CLEAN_RECEIPTS = {"format": "westack-checks-1", "kind": "diff", "verdict": "no-new-failures", "exit_code": 0,
                  "new_failures": [], "preexisting_failures": []}


def pr_obj(**fields):
    base = {"number": 7, "state": "OPEN", "isDraft": False, "headRefOid": OID, "baseRefName": "main",
            "autoMergeRequest": None}
    base.update(fields)
    return base


def modified(path, removed=(), added=(), start=1):
    lines = ["diff --git a/%s b/%s" % (path, path), "index 1111111..2222222 100644", "--- a/" + path, "+++ b/" + path,
             "@@ -%d,%d +%d,%d @@" % (start, 1 + len(removed), start, 1 + len(added)), " context"]
    lines += ["-" + r for r in removed] + ["+" + a for a in added]
    return "\n".join(lines) + "\n"


def new_file(path, added):
    lines = ["diff --git a/%s b/%s" % (path, path), "new file mode 100644", "index 0000000..3333333",
             "--- /dev/null", "+++ b/" + path, "@@ -0,0 +1,%d @@" % len(added)] + ["+" + a for a in added]
    return "\n".join(lines) + "\n"


def ids(report, level=None):
    return {f["id"] for f in report["findings"] if level is None or f["level"] == level}


def finding(report, fid):
    return next(f for f in report["findings"] if f["id"] == fid)


def repo_with(files):
    temp = tempfile.TemporaryDirectory(prefix="westack-shipgate-")
    root = pathlib.Path(temp.name)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8", newline="\n")
    return temp, root


EMPTY_REPO = tempfile.TemporaryDirectory(prefix="westack-shipgate-empty-")
CODE_DIFF = modified("src/app.py", ["x = 1"], ["x = 2"])


def full_push(**overrides):
    """Every input a push needs, all clean; override one at a time."""
    args = dict(status=v2(ahead=1), remotes=REMOTES, pr=[], rules={"feature": ["none"]}, repo=EMPTY_REPO.name,
                diff=CODE_DIFF, receipts=CLEAN_RECEIPTS, default_branch="main", grant=["push"])
    args.update(overrides)
    return sg.gate(**args)


class StatusTests(unittest.TestCase):
    def test_a_clean_branch_level_with_its_upstream_reads_pushed(self):
        report = sg.gate(v2())
        self.assertEqual(report["delivery_state"], "pushed")
        self.assertEqual((report["state"]["ahead"], report["state"]["behind"]), (0, 0))
        self.assertFalse(ids(report) & {"dirty-tree", "unpushed-commits", "behind-upstream"})

    def test_commits_ahead_of_the_upstream_are_unpushed(self):
        report = sg.gate(v2(ahead=2))
        self.assertIn("unpushed-commits", ids(report))
        self.assertIn("2", finding(report, "unpushed-commits")["message"])
        self.assertEqual(report["delivery_state"], "committed")

    def test_behind_the_upstream_blocks_a_push(self):
        report = sg.gate(v2(ahead=1, behind=3), grant=["push"])
        self.assertIn("behind-upstream", ids(report, "block"))
        self.assertEqual(report["steps"]["push"]["status"], "blocked")
        self.assertEqual(report["exit_code"], 1)

    def test_uncommitted_and_untracked_paths_need_a_decision_before_a_push(self):
        report = sg.gate(v2(lines=[TRACKED, UNTRACKED]), grant=["push"])
        dirty = finding(report, "dirty-tree")
        self.assertEqual(dirty["level"], "decide")
        self.assertIn("src/app.py", " ".join(dirty["evidence"]))
        self.assertIn("notes/scratch.txt", " ".join(dirty["evidence"]))
        self.assertIn("push", dirty["steps"])
        self.assertEqual(report["delivery_state"], "uncommitted")

    def test_a_detached_head_blocks_push_and_pr(self):
        report = sg.gate(v2(branch="(detached)", upstream=None), grant=["push", "pr"])
        self.assertIn("detached-head", ids(report, "block"))
        self.assertEqual(report["steps"]["push"]["status"], "blocked")
        self.assertEqual(report["steps"]["pr"]["status"], "blocked")

    def test_conflicts_block_every_step_and_readiness(self):
        report = sg.gate(v2(lines=[CONFLICT]), grant=["commit"])
        self.assertIn("conflicts", ids(report, "block"))
        self.assertEqual(report["steps"]["commit"]["status"], "blocked")
        self.assertEqual(report["readiness"]["verdict"], "not-ready")

    def test_porcelain_v1_reads_the_same(self):
        report = sg.gate("## feature...origin/feature [ahead 1, behind 2]\n M src/app.py\n?? notes/x.txt\n")
        self.assertEqual((report["state"]["branch"], report["state"]["upstream"]), ("feature", "origin/feature"))
        self.assertEqual((report["state"]["ahead"], report["state"]["behind"]), (1, 2))
        self.assertIn("dirty-tree", ids(report))

    def test_no_upstream_counts_the_saved_log_as_unpushed(self):
        report = sg.gate(v2(upstream=None), log="abc1234 first\ndef5678 second\n")
        self.assertIn("unpushed-commits", ids(report))
        self.assertIn("no-upstream", ids(report))
        self.assertEqual(report["delivery_state"], "committed")

    def test_on_the_default_branch_a_push_needs_a_decision(self):
        report = full_push(status=v2(branch="main", upstream="origin/main", ahead=1), rules={"main": ["none"]})
        self.assertIn("default-branch-target", ids(report, "decide"))
        self.assertEqual(report["steps"]["push"]["status"], "needs-decision")


class PullRequestTests(unittest.TestCase):
    def test_an_armed_auto_merge_blocks_a_push(self):
        report = full_push(pr=pr_obj(autoMergeRequest={"enabledAt": "2026-10-28T10:00:00Z", "mergeMethod": "SQUASH"}))
        self.assertIn("auto-merge-armed", ids(report, "block"))
        self.assertEqual(report["steps"]["push"]["status"], "blocked")
        self.assertEqual(report["pr"]["auto_merge"], "armed")
        self.assertEqual(report["exit_code"], 1)

    def test_an_unread_auto_merge_field_is_unknown_not_absent(self):
        pr = pr_obj()
        del pr["autoMergeRequest"]
        report = full_push(pr=pr)
        self.assertEqual(report["pr"]["auto_merge"], "unknown")
        self.assertIn("auto-merge-unknown", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")
        self.assertEqual(report["exit_code"], 2)

    def test_no_open_pr_means_nothing_to_arm(self):
        report = full_push(pr=[])
        self.assertEqual(report["pr"]["state"], "none")
        self.assertFalse(ids(report) & {"auto-merge-armed", "auto-merge-unknown", "merge-queue-unknown"})

    def test_a_push_with_no_pr_lookup_cannot_tell(self):
        report = full_push(pr=None)
        self.assertIn("pr-unknown", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")

    def test_a_merge_queue_entry_blocks_a_push(self):
        graphql = {"data": {"repository": {"pullRequest": pr_obj(mergeQueueEntry={"id": "MQE_1", "state": "QUEUED"})}}}
        report = full_push(pr=graphql)
        self.assertIn("merge-queued", ids(report, "block"))
        self.assertEqual(report["pr"]["merge_queue"], "queued")

    def test_graphql_errors_are_unknown(self):
        report = full_push(pr={"errors": [{"message": "Field 'mergeQueueEntry' doesn't exist"}], "data": None})
        self.assertIn("pr-unknown", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")

    def test_a_queue_field_missing_is_unknown_unless_the_base_rules_show_no_queue(self):
        unknown = full_push(pr=pr_obj())
        self.assertIn("merge-queue-unknown", ids(unknown, "unknown"))
        rules = {"feature": ["none"], "main": [[{"type": "pull_request", "parameters": {}}]]}
        known = full_push(pr=pr_obj(), rules=rules)
        self.assertNotIn("merge-queue-unknown", ids(known))
        self.assertEqual(known["pr"]["merge_queue"], "no")

    def test_a_merged_pr_is_reported_as_merged(self):
        report = sg.gate(v2(), pr=pr_obj(state="MERGED"))
        self.assertEqual(report["delivery_state"], "merged")
        self.assertIn("pr-not-open", ids(report))

    def test_a_pr_head_that_differs_from_local_blocks_merge(self):
        report = sg.gate(v2(), pr=pr_obj(headRefOid=OTHER), grant=["merge"])
        self.assertIn("pr-head-mismatch", ids(report, "block"))
        self.assertEqual(report["steps"]["merge"]["status"], "blocked")

    def test_a_draft_pr_blocks_merge(self):
        report = sg.gate(v2(), pr=pr_obj(isDraft=True), grant=["merge"])
        self.assertIn("pr-draft", ids(report, "block"))


class ReviewStateTests(unittest.TestCase):
    """SS-80: an unresolved review thread or an open change request blocks a merge; a thread list that was not read,
    or not read in full, is unknown and never reads as clean. The push step is unaffected."""

    @staticmethod
    def threads(*resolved, **page):
        body = {"nodes": [{"isResolved": r, "isOutdated": False, "path": "src/app.py"} for r in resolved]}
        body.update(page)
        return body

    @staticmethod
    def merge(module, **fields):
        return module.gate(v2(), pr=pr_obj(**fields), grant=["merge"])

    @staticmethod
    def broken(*edits):
        source = SCRIPT.read_text(encoding="utf-8")
        for old, new in edits:
            assert source.count(old) == 1, old
            source = source.replace(old, new)
        temp = tempfile.TemporaryDirectory(prefix="westack-shipgate-broken-")
        path = pathlib.Path(temp.name) / "shipgate_broken.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("westack_ship_shipgate_broken_" + str(abs(hash(edits))), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.temp = temp
        return module

    def check_blocker(self, module):
        report = self.merge(module, reviewThreads=self.threads(True, False))
        self.assertIn("review-threads-open", ids(report, "block"))
        self.assertEqual(report["steps"]["merge"]["status"], "blocked")
        self.assertEqual(finding(report, "review-threads-open")["evidence"], ["src/app.py"])

    def check_unknown(self, module):
        report = self.merge(module)  # the thread field is absent
        self.assertIn("review-threads-unknown", ids(report, "unknown"))
        self.assertNotIn("review-threads-open", ids(report))

    def test_an_unresolved_thread_blocks_the_merge(self):
        self.check_blocker(sg)

    def test_resolved_threads_and_an_approval_raise_nothing(self):
        report = self.merge(sg, reviewThreads=self.threads(True, True), reviewDecision="APPROVED")
        self.assertFalse(ids(report) & {"review-threads-open", "review-threads-unknown", "changes-requested"})

    def test_a_missing_thread_field_is_unknown_not_clean(self):
        self.check_unknown(sg)

    def test_an_open_change_request_blocks_the_merge(self):
        report = self.merge(sg, reviewThreads=self.threads(True), reviewDecision="CHANGES_REQUESTED")
        self.assertIn("changes-requested", ids(report, "block"))

    def test_a_partly_read_thread_list_is_unknown(self):
        report = self.merge(sg, reviewThreads=self.threads(True, pageInfo={"hasNextPage": True}))
        self.assertIn("review-threads-unknown", ids(report, "unknown"))
        junk = self.merge(sg, reviewThreads={"nodes": [{"body": "no isResolved field"}]})
        self.assertIn("review-threads-unknown", ids(junk, "unknown"))

    def test_a_graphql_response_is_read_the_same_way(self):
        graphql = {"data": {"repository": {"pullRequest": pr_obj(reviewThreads=self.threads(False))}}}
        report = sg.gate(v2(), pr=graphql, grant=["merge"])
        self.assertIn("review-threads-open", ids(report, "block"))

    def test_the_push_step_does_not_wait_on_review_threads(self):
        report = full_push(pr=pr_obj(mergeQueueEntry=None))
        self.assertEqual(report["steps"]["push"]["status"], "clear")
        self.assertNotIn("push", finding(sg.gate(v2(), pr=pr_obj(), grant=["merge"]), "review-threads-unknown")["steps"])

    def test_a_copy_that_ignores_unresolved_threads_fails_the_blocker_check(self):
        broken = self.broken(("if unresolved:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_blocker(broken)
        broken.temp.cleanup()

    def test_a_copy_that_reads_a_missing_field_as_clean_fails_the_unknown_check(self):
        broken = self.broken(("if not readable or partial:", "if False:"),
                             ('unresolved = [n for n in nodes if not n["isResolved"]]',
                              'unresolved = [n for n in (nodes or []) if not n["isResolved"]]'))
        self.assertEqual(self.merge(broken, reviewThreads=self.threads(True)).get("exit_code"), 2, "still runs")
        with self.assertRaises(AssertionError):
            self.check_unknown(broken)
        broken.temp.cleanup()


class ProtectionTests(unittest.TestCase):
    def test_rulesets_give_required_checks_and_the_queue(self):
        rules = [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "test"},
                                                                                          {"context": "lint"}]}},
                 {"type": "merge_queue", "parameters": {}}]
        report = sg.gate(v2(), rules={"main": [rules]})
        main = report["protection"]["main"]
        self.assertEqual(main["protected"], True)
        self.assertEqual(main["merge_queue"], True)
        self.assertEqual(main["required_checks"], ["lint", "test"])

    def test_classic_protection_on_the_target_needs_a_decision(self):
        classic = {"url": "https://api.github.com/repos/o/r/branches/main/protection",
                   "required_status_checks": {"contexts": ["ci/test"], "checks": [{"context": "ci/test"}]},
                   "required_pull_request_reviews": {"required_approving_review_count": 1}}
        report = full_push(status=v2(branch="main", upstream="origin/main", ahead=1), rules={"main": [classic]})
        self.assertIn("protected-target", ids(report, "decide"))
        self.assertEqual(report["protection"]["main"]["required_checks"], ["ci/test"])

    def test_a_plain_remote_has_no_protection_system(self):
        report = full_push()
        self.assertEqual(report["protection"]["feature"]["protected"], False)
        self.assertNotIn("protection-unknown", ids(report))

    def test_a_push_without_protection_input_cannot_tell(self):
        report = full_push(rules={})
        self.assertIn("protection-unknown", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")

    def test_an_api_error_is_unknown(self):
        report = full_push(rules={"feature": [{"message": "Not Found", "status": "404"}]})
        self.assertIn("protection-unknown", ids(report, "unknown"))

    def test_branch_not_protected_is_an_answer(self):
        report = full_push(rules={"feature": [{"message": "Branch not protected", "status": "404"}]})
        self.assertNotIn("protection-unknown", ids(report))
        self.assertEqual(report["protection"]["feature"]["protected"], False)


AUTO_MERGE_WORKFLOW = """name: auto-merge
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  merge:
    runs-on: ubuntu-latest
    steps:
      - run: gh pr merge --auto --squash "$PR_URL"
"""
AUTO_PR_WORKFLOW = """name: auto-pr
on:
  push:
    branches-ignore: [main]
jobs:
  pr:
    runs-on: ubuntu-latest
    steps:
      - run: gh pr create --fill --base main
      - run: gh pr merge --auto --squash
"""
PUBLISH_ON_TAG = """name: release
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
"""
PLAIN_CI = """name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: python -m unittest -v
"""


class AutomationTests(unittest.TestCase):
    def scan(self, files, grant=("push",)):
        temp, root = repo_with(files)
        self.addCleanup(temp.cleanup)
        return full_push(repo=str(root), grant=list(grant))

    def test_a_workflow_that_arms_auto_merge_is_found_with_its_line(self):
        report = self.scan({".github/workflows/automerge.yml": AUTO_MERGE_WORKFLOW})
        found = finding(report, "auto-merge-config")
        self.assertEqual(found["level"], "decide")
        self.assertTrue(any(".github/workflows/automerge.yml:9" in e for e in found["evidence"]), found["evidence"])
        self.assertEqual(set(found["steps"]) & {"push", "pr"}, {"push", "pr"})

    def test_an_auto_pr_workflow_on_push_is_found(self):
        report = self.scan({".github/workflows/auto-pr.yml": AUTO_PR_WORKFLOW})
        self.assertIn("auto-merge-config", ids(report))
        self.assertEqual(report["steps"]["push"]["status"], "needs-decision")
        self.assertEqual(report["exit_code"], 1)

    def test_renovate_automerge_true_is_found_and_false_is_not(self):
        on = self.scan({"renovate.json": '{"extends": ["config:base"], "automerge": true}\n'})
        self.assertIn("auto-merge-config", ids(on))
        off = self.scan({"renovate.json": '{"extends": ["config:base"], "automerge": false}\n'})
        self.assertNotIn("auto-merge-config", ids(off))

    def test_a_merge_bot_config_is_found(self):
        report = self.scan({".mergify.yml": "pull_request_rules:\n  - name: go\n    conditions: [check-success=ci]\n"
                                            "    actions:\n      merge:\n        method: squash\n"})
        self.assertIn("auto-merge-config", ids(report))

    def test_a_tag_push_that_publishes_is_found(self):
        report = self.scan({".github/workflows/release.yml": PUBLISH_ON_TAG}, grant=("release",))
        found = finding(report, "publish-on-push")
        self.assertIn("release", found["steps"])
        self.assertTrue(any("release.yml:9" in e for e in found["evidence"]), found["evidence"])

    def test_an_ordinary_ci_workflow_is_not_flagged(self):
        report = self.scan({".github/workflows/ci.yml": PLAIN_CI})
        self.assertFalse(ids(report) & {"auto-merge-config", "publish-on-push"})
        self.assertEqual(report["automation"][0]["triggers"], ["pull_request", "push"])
        self.assertEqual(report["steps"]["push"]["status"], "clear")


class ReleaseTests(unittest.TestCase):
    def test_a_version_bump_without_a_changelog_entry_is_flagged(self):
        temp, root = repo_with({"CHANGELOG.md": "# Changelog\n", "VERSION": "1.4.0\n"})
        self.addCleanup(temp.cleanup)
        report = sg.gate(v2(), repo=str(root), diff=modified("VERSION", ["1.3.0"], ["1.4.0"]))
        self.assertIn("version-without-changelog", ids(report))
        self.assertEqual(report["release"]["new_versions"], ["1.4.0"])
        self.assertEqual(report["readiness"]["verdict"], "not-ready")

    def test_a_bump_with_its_changelog_entry_is_clean(self):
        diff = modified("VERSION", ["1.3.0"], ["1.4.0"]) + modified("CHANGELOG.md", [], ["## [1.4.0] - 2026-10-28",
                                                                                   "### Added", "- --max-length"])
        report = sg.gate(v2(), diff=diff, receipts=CLEAN_RECEIPTS)
        self.assertFalse(ids(report) & {"version-without-changelog", "changelog-missing-version", "version-mismatch"})
        self.assertEqual(report["readiness"]["verdict"], "ready")

    def test_a_changelog_that_names_another_version_is_flagged(self):
        diff = modified("package.json", ['  "version": "2.0.0",'], ['  "version": "2.1.0",']) + \
            modified("CHANGELOG.md", [], ["## 2.0.1", "- fix"])
        report = sg.gate(v2(), diff=diff)
        self.assertIn("changelog-missing-version", ids(report))

    def test_versions_that_disagree_across_files_are_flagged(self):
        diff = modified("pyproject.toml", ['version = "1.3.0"'], ['version = "1.4.0"']) + \
            modified("slugkit/__init__.py", ['__version__ = "1.3.0"'], ['__version__ = "1.3.1"']) + \
            modified("CHANGELOG.md", [], ["## [1.4.0] - 2026-10-28"])
        report = sg.gate(v2(), diff=diff)
        self.assertIn("version-mismatch", ids(report, "block"))
        self.assertEqual(report["release"]["new_versions"], ["1.3.1", "1.4.0"])

    def test_a_changelog_fragment_counts_as_the_entry(self):
        diff = modified("pyproject.toml", ['version = "1.3.0"'], ['version = "1.4.0"']) + \
            new_file("changelog.d/42.feature.md", ["Add --max-length."])
        report = sg.gate(v2(), diff=diff)
        self.assertNotIn("version-without-changelog", ids(report))
        self.assertTrue(report["release"]["changelog_changed"])

    def test_no_version_source_is_not_applicable(self):
        report = sg.gate(v2(), diff=modified("src/app.py", ["x = 1"], ["x = 2"]))
        self.assertEqual(report["release"]["new_versions"], [])
        self.assertFalse(ids(report) & {"version-without-changelog", "version-mismatch"})


class SecretTests(unittest.TestCase):
    TOKEN = "ghp_" + "Z9" * 18

    def test_a_token_in_the_diff_blocks_and_the_value_is_never_echoed(self):
        report = sg.gate(v2(), diff=modified("src/config.py", [], ["TOKEN = '%s'" % self.TOKEN], start=10),
                         grant=["commit"])
        found = finding(report, "secret-in-diff")
        self.assertEqual(found["level"], "block")
        self.assertTrue(any("src/config.py:11" in e and "github-token" in e for e in found["evidence"]),
                        found["evidence"])
        self.assertNotIn(self.TOKEN, json.dumps(report))
        self.assertEqual(report["steps"]["commit"]["status"], "blocked")

    def test_an_added_env_file_is_flagged(self):
        report = sg.gate(v2(), diff=new_file(".env", ["DEBUG=1"]))
        self.assertIn("secret-in-diff", ids(report))


class ReceiptTests(unittest.TestCase):
    def test_checks_diff_verdicts_map_to_readiness(self):
        ok = sg.gate(v2(), receipts=CLEAN_RECEIPTS)
        self.assertFalse(ids(ok) & {"receipts-failing", "receipts-inconclusive", "receipts-missing"})
        failing = sg.gate(v2(), receipts=dict(CLEAN_RECEIPTS, verdict="new-failures", exit_code=1,
                                              new_failures=["tests.test_x.T.test_y"]))
        self.assertIn("receipts-failing", ids(failing, "block"))
        self.assertIn("tests.test_x.T.test_y", " ".join(finding(failing, "receipts-failing")["evidence"]))
        unsure = sg.gate(v2(), receipts=dict(CLEAN_RECEIPTS, verdict="inconclusive", exit_code=2))
        self.assertIn("receipts-inconclusive", ids(unsure, "unknown"))

    def test_a_parse_with_zero_executed_tests_is_not_a_pass(self):
        parsed = {"format": "westack-checks-1", "kind": "parse", "complete": True,
                  "counts": {"parsed": 0, "passed": 0, "failed": 0, "skipped": 0}}
        report = sg.gate(v2(), receipts=parsed)
        self.assertIn("receipts-inconclusive", ids(report))

    def test_missing_receipts_leave_a_push_unknown(self):
        report = full_push(receipts=None)
        self.assertIn("receipts-missing", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")


class StepsAndExitTests(unittest.TestCase):
    def test_a_fully_checked_push_is_clear_and_exits_0(self):
        report = full_push()
        self.assertEqual(report["steps"]["push"]["status"], "clear", report["findings"])
        self.assertEqual(report["exit_code"], 0)

    def test_a_step_not_granted_is_never_reported_clear(self):
        report = full_push(grant=[])
        self.assertEqual(report["steps"]["push"]["status"], "not-granted")
        self.assertEqual(report["steps"]["push"]["preconditions"], "clear")
        self.assertFalse(report["steps"]["merge"]["granted"])

    def test_readiness_only_with_clean_receipts_exits_0(self):
        report = sg.gate(v2(), receipts=CLEAN_RECEIPTS, diff=CODE_DIFF)
        self.assertEqual((report["readiness"]["verdict"], report["exit_code"]), ("ready", 0))

    def test_readiness_without_a_diff_cannot_tell(self):
        report = sg.gate(v2(), receipts=CLEAN_RECEIPTS)
        self.assertIn("diff-unknown", ids(report, "unknown"))
        self.assertEqual((report["readiness"]["verdict"], report["exit_code"]), ("unknown", 2))

    def test_a_push_without_the_repository_read_cannot_tell(self):
        report = full_push(repo=None)
        self.assertIn("automation-unknown", ids(report, "unknown"))
        self.assertEqual(report["steps"]["push"]["status"], "cannot-tell")

    def test_the_report_says_it_ran_nothing(self):
        self.assertIn("ran nothing", sg.gate(v2())["claim"])


class CliTests(unittest.TestCase):
    def run_main(self, args):
        out = []
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("shipgate must not run commands")), \
                mock.patch.object(os, "system", side_effect=AssertionError("shipgate must not run commands")):
            code = sg.main(args, out=out.append)
        return code, "".join(out)

    def test_cli_reads_saved_files_and_runs_nothing(self):
        with tempfile.TemporaryDirectory(prefix="westack-shipgate-") as temp:
            temp = pathlib.Path(temp)
            (temp / "status.txt").write_text(v2(ahead=1), encoding="utf-8")
            (temp / "pr.json").write_text(json.dumps(pr_obj(autoMergeRequest={"enabledAt": "x"})), encoding="utf-8")
            code, text = self.run_main(["--status", str(temp / "status.txt"), "--pr", str(temp / "pr.json"),
                                        "--grant", "push", "--output", str(temp / "gate.json")])
            self.assertEqual(code, 1)
            self.assertIn("auto-merge-armed", text)
            self.assertEqual(json.loads((temp / "gate.json").read_text(encoding="utf-8"))["exit_code"], 1)
            again, _ = self.run_main(["--status", str(temp / "status.txt"), "--output", str(temp / "gate.json")])
            self.assertEqual(again, 64, "an existing output is never replaced")

    def test_none_markers_for_a_plain_remote(self):
        with tempfile.TemporaryDirectory(prefix="westack-shipgate-") as temp:
            temp = pathlib.Path(temp)
            (temp / "status.txt").write_text(v2(ahead=1), encoding="utf-8")
            (temp / "remotes.txt").write_text(REMOTES, encoding="utf-8")
            (temp / "receipts.json").write_text(json.dumps(CLEAN_RECEIPTS), encoding="utf-8")
            (temp / "diff.txt").write_text(CODE_DIFF, encoding="utf-8")
            (temp / "repo").mkdir()
            code, text = self.run_main(["--status", str(temp / "status.txt"), "--remotes", str(temp / "remotes.txt"),
                                        "--pr", "none", "--rules", "feature=none", "--receipts",
                                        str(temp / "receipts.json"), "--diff", str(temp / "diff.txt"), "--repo",
                                        str(temp / "repo"), "--default-branch", "main", "--grant", "push"])
            self.assertEqual(code, 0, text)

    def test_usage_errors_exit_64(self):
        with tempfile.TemporaryDirectory(prefix="westack-shipgate-") as temp:
            status = pathlib.Path(temp) / "status.txt"
            status.write_text(v2(), encoding="utf-8")
            self.assertEqual(self.run_main(["--status", str(pathlib.Path(temp) / "missing.txt")])[0], 64)
            self.assertEqual(self.run_main(["--status", str(status), "--grant", "deploy"])[0], 64)
            self.assertEqual(self.run_main(["--status", str(status), "--rules", "no-equals-sign"])[0], 64)
            self.assertEqual(self.run_main([])[0], 64)


if __name__ == "__main__":
    unittest.main()
