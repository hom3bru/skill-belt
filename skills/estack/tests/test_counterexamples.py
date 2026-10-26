import copy
import pathlib
import tempfile
import unittest
import test_estack as fixtures


class CounterexampleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="estack-counterexample-")
        self.root=pathlib.Path(self.temp.name)
        self.task=fixtures.make_task(self.root)
        self.context={k:self.task[k] for k in ("revision","scope_id","patch_id")}

    def tearDown(self):
        self.temp.cleanup()

    def test_receipt_for_other_claim_cannot_certify_acceptance(self):
        self.task["evidence"][0]["claim_id"]="unrelated-claim"
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("claim" in e for e in errors),errors)

    def test_all_optional_unrun_criteria_cannot_complete(self):
        self.task["acceptance"][0].update(required=False,status="not-run",evidence_ids=[])
        self.task["evidence"]=[]
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("required acceptance" in e for e in errors),errors)

    def test_unrun_review_evidence_cannot_satisfy_independence(self):
        unrun=copy.deepcopy(self.task["evidence"][0])
        unrun.update(id="review-e",claim_id="rev1",status="not-run",collected=0,executed=0,passed=0,
                     artifact=None,artifact_sha256=None,raw_output=None,raw_sha256=None,exit_code=None)
        self.task["evidence"].append(unrun)
        self.task["reviews"]=[dict(id="rev1",author_id=self.task["author_id"],reviewer_id="other-person",
            context_id="fresh-context",patch_id=self.task["patch_id"],kind="independent",
            status="completed",evidence_ids=["review-e"],finding_ids=[])]
        self.task["independent_review_required"]=True
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("review" in e for e in errors),errors)

    def test_fixed_finding_cannot_use_old_patch_evidence(self):
        stale=copy.deepcopy(self.task["evidence"][0])
        stale.update(id="old-e",claim_id="f1",revision="old-revision")
        self.task["evidence"].append(stale)
        self.task["findings"]=[dict(id="f1",claim="consumer broken",location="cli.py:1",
            consequence="CLI fails",evidence_ids=["e1"],severity="high",severity_rationale="required path",
            correction="adapt consumer",adjudication="fixed",rationale="updated",verification_ids=["old-e"])]
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("finding" in e for e in errors),errors)

    def test_pending_action_cannot_be_reported_applied(self):
        self.task["actions"]=[dict(id="pending",kind="local-write",target="src/parser/a.py",
            target_hash="a"*64,scope_id=self.task["scope_id"],occurrence="pause-1",
            decision="pending",outcome="applied",evidence_ids=[])]
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("applied action" in e for e in errors),errors)

    def test_unrelated_old_runtime_receipt_cannot_upgrade_source_audit(self):
        old=copy.deepcopy(self.task["evidence"][0])
        old.update(id="old-runtime",claim_id="old-claim",type="unit",revision="old-revision")
        self.task["evidence"].append(old)
        self.task["verification"]="runtime-tested"
        errors=fixtures.v.check_task(self.task,self.root,self.context)
        self.assertTrue(any("runtime-tested" in e for e in errors),errors)

