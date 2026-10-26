"""Adversarial consistency regressions; all receipt fields are synthetic inputs.

These tests challenge record relationships, not whether a claimed operation was
actually run. They execute only authored local helpers and fixture code.
"""
import copy
import hashlib
import os
import pathlib
import shutil
import tempfile
import unittest

import test_estack as fixtures


v = fixtures.v


class FrankenmineRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="estack-frankenmine-regression-")
        self.root = pathlib.Path(self.temp.name)
        self.task = fixtures.make_task(self.root)
        self.context = {key: self.task[key] for key in ("revision", "scope_id", "patch_id")}

    def tearDown(self):
        self.temp.cleanup()

    def errors(self, task=None, previous=None):
        return v.check_task(self.task if task is None else task, self.root, self.context, previous)

    def action(self, **changes):
        result = dict(id="act-1", kind="local-write", target="src/parser/a.py",
                      target_hash="a" * 64, scope_id=self.task["scope_id"],
                      occurrence="pause-1", decision="approved", outcome="not-applied",
                      evidence_ids=[])
        result.update(changes)
        return result

    def with_control(self):
        positive = self.task["evidence"][0]
        positive.update(type="unit", negative_control="broken-path",
                        limitations=["Synthetic validator fields; no product execution asserted"])
        self.task["acceptance"][0].update(requires_runtime=True, requires_negative_control=True)
        control = copy.deepcopy(positive)
        control.update(id="broken-path", status="failed", passed=0, failed=1,
                       exit_code=1, negative_control=None,
                       operation="Authored validator input representing a broken-path rejection")
        self.task["evidence"].append(control)
        return control

    def test_current_claim_bound_runtime_negative_control_is_valid(self):
        self.with_control()
        self.assertFalse(self.errors(), self.errors())

    def test_stale_negative_control_cannot_certify_current_acceptance(self):
        control = self.with_control()
        control.update(revision="old-revision", scope_id="old-scope", patch_id="f" * 64)
        self.assertTrue(self.errors(), "A negative control from another context was accepted")

    def test_wrong_claim_negative_control_cannot_certify_acceptance(self):
        self.with_control()["claim_id"] = "unrelated-claim"
        self.assertTrue(self.errors(), "A failure for an unrelated claim certified acceptance")

    def test_source_negative_control_cannot_certify_runtime_mechanism(self):
        self.with_control()["type"] = "source"
        self.assertTrue(self.errors(), "A source observation certified runtime control detection")

    def test_infrastructure_exit_without_failed_case_is_not_control_detection(self):
        control = self.with_control()
        control.update(passed=1, failed=0, exit_code=1,
                       coverage="One positive case passed; process failed afterward",
                       limitations=["Unexpected process exit; no failed mechanism assertion"])
        self.assertTrue(self.errors(), "An exit failure with no failed case certified control detection")

    def reconciled_action(self, **receipt_changes):
        previous = copy.deepcopy(self.task)
        previous.update(completion="partial", state="partial", history=[], verification="unverified",
                        blockers=["Mutation outcome still uncertain"])
        previous["actions"] = [self.action(outcome="uncertain")]
        current = copy.deepcopy(previous)
        current["actions"][0].update(outcome="applied", evidence_ids=["action-observation"])
        observation = copy.deepcopy(current["evidence"][0])
        observation.update(id="action-observation", claim_id="act-1",
                           operation="Synthetic source observation of the action outcome",
                           limitations=["Validator fixture; does not authenticate an observer"])
        observation.update(receipt_changes)
        current["evidence"].append(observation)
        return current, previous

    def test_current_passing_action_claim_can_reconcile_uncertainty(self):
        current, previous = self.reconciled_action()
        self.assertFalse(self.errors(current, previous), self.errors(current, previous))

    def test_unrelated_claim_cannot_reconcile_uncertain_action(self):
        current, previous = self.reconciled_action(claim_id="a1")
        self.assertTrue(self.errors(current, previous), "Unrelated acceptance evidence reconciled an action")

    def test_failed_observation_cannot_reconcile_uncertain_action(self):
        current, previous = self.reconciled_action(status="failed", passed=0, failed=1, exit_code=1)
        self.assertTrue(self.errors(current, previous), "A failed observation reconciled an action")

    def test_stale_observation_cannot_reconcile_uncertain_action(self):
        current, previous = self.reconciled_action(revision="old-revision", scope_id="old-scope", patch_id="f" * 64)
        self.assertTrue(self.errors(current, previous), "Stale action evidence reconciled an action")

    def test_unrun_observation_cannot_reconcile_uncertain_action(self):
        current, previous = self.reconciled_action(status="not-run", collected=0, executed=0,
            passed=0, failed=0, skipped=0, exit_code=None, raw_output=None, raw_sha256=None,
            artifact=None, artifact_sha256=None)
        self.assertTrue(self.errors(current, previous), "Unexecuted evidence reconciled an action")

    def test_new_id_cannot_replay_same_denied_action_occurrence(self):
        denied = self.action(decision="denied", outcome="denied")
        self.task["actions"] = [denied]
        previous = copy.deepcopy(self.task)
        self.task["actions"].append(self.action(id="new-id-for-same-occurrence"))
        self.assertTrue(self.errors(previous=previous), "Renaming an action bypassed a preserved denial")

    def test_applied_current_scope_action_still_needs_allowed_kind(self):
        self.task["actions"] = [self.action(kind="commit", target="local-tree", outcome="applied")]
        self.assertNotIn("commit", self.task["authority"]["allowed_actions"])
        self.assertNotIn("commit", self.task["authority"]["forbidden_actions"])
        self.assertTrue(self.errors(), "An applied current-scope action bypassed the allowed kinds")

    def test_historical_applied_action_survives_changed_current_scope(self):
        self.task["actions"] = [self.action(kind="commit", target="historical-local-tree",
            scope_id="previous-authorized-scope", outcome="applied")]
        self.assertFalse(self.errors(), self.errors())

    def test_historical_applied_local_write_survives_narrower_current_paths(self):
        self.task.update(state="partial", completion="partial", verification="unverified", history=[])
        self.task["actions"] = [self.action(outcome="applied")]
        previous = copy.deepcopy(self.task)
        self.task["scope_id"] = "new-narrower-scope"
        self.task["authority"]["allowed_paths"] = ["src/new-scope"]
        self.task["acceptance"][0].update(status="not-run", evidence_ids=[])
        self.context["scope_id"] = self.task["scope_id"]
        self.assertFalse(self.errors(previous=previous), self.errors(previous=previous))

    def unfinished_work(self, status):
        self.task["work_units"] = [dict(id="unfinished", goal="Required remaining work",
            depends_on=[], allowed_paths=["src/parser"], status=status)]
        self.assertTrue(self.errors(), "Complete task retained a " + status + " work unit")

    def test_complete_task_cannot_keep_planned_work(self):
        self.unfinished_work("planned")

    def test_complete_task_cannot_keep_active_work(self):
        self.unfinished_work("active")

    def test_complete_task_cannot_keep_blocked_work(self):
        self.unfinished_work("blocked")

    def test_requirement_cannot_supersede_itself(self):
        self.task["requirements"] = [dict(id="r1", text="Circular requirement", origin="user",
                                             status="superseded", supersedes="r1")]
        self.assertTrue(self.errors(), "Self-supersession was accepted")

    def test_requirement_supersession_cannot_form_multinode_cycle(self):
        self.task["requirements"] = [
            dict(id="r1", text="First", origin="user", status="superseded", supersedes="r3"),
            dict(id="r2", text="Second", origin="user", status="superseded", supersedes="r1"),
            dict(id="r3", text="Third", origin="user", status="superseded", supersedes="r2")]
        self.assertTrue(self.errors(), "Circular supersession chain was accepted")

    def test_linear_requirement_supersession_remains_valid(self):
        self.task["requirements"] = [
            dict(id="r1", text="First", origin="user", status="superseded", supersedes=None),
            dict(id="r2", text="Replacement", origin="user", status="active", supersedes="r1")]
        self.assertFalse(self.errors(), self.errors())

    def test_json_overflow_is_rejected_before_schema_checks(self):
        path = self.root / "overflow.json"
        path.write_text('{"number":1e308}', encoding="utf-8")
        self.assertEqual(v.read_json(path)["number"], 1e308)
        path.write_text('{"number":1e999}', encoding="utf-8")
        with self.assertRaises(ValueError):
            v.read_json(path)

    def test_json_and_digest_reads_are_bounded(self):
        limit = getattr(v, "LIMIT", 8 * 1024 * 1024)
        path = self.root / "oversize.json"
        path.write_bytes(b'{"text":"' + b"x" * (limit + 1) + b'"}')
        with self.assertRaises(ValueError):
            v.read_json(path)
        # Artifact hashes must still cover large files; only record parsing has
        # a byte cap. The implementation streams evidence in bounded chunks.
        self.assertEqual(v.digest(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_read_helpers_reject_directory_inputs(self):
        for helper in (v.read_json, v.digest):
            with self.subTest(helper=helper.__name__):
                with self.assertRaises((OSError, ValueError)):
                    helper(self.root)

    def test_package_rejects_directory_junction_before_external_traversal(self):
        copied = self.root / "copied-package"
        shutil.copytree(fixtures.ROOT, copied,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        outside = self.root / "outside-package"
        outside.mkdir()
        sentinel = outside / "external.txt"
        sentinel.write_text("Authored sibling sentinel; never package this file", encoding="utf-8")
        link = copied / "external-link"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            self.assertTrue(v.check_package(copied), "Package checker accepted an external directory link")
            self.assertTrue(sentinel.is_file())
        finally:
            # Remove only the link itself, then normal TemporaryDirectory
            # cleanup may safely remove the remaining authored fixture tree.
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()


if __name__ == "__main__":
    unittest.main()
