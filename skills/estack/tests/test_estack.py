import copy
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("estack_validate", ROOT / "scripts/validate.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
FIXTURES = ROOT / "tests/fixtures"


def make_task(root):
    root = pathlib.Path(root)
    (root / "artifact.txt").write_text("Read-only fixture: parser returns a string.\n", encoding="utf-8")
    (root / "output.txt").write_text("Observed artifact.txt: parser returns a string. One read; no runtime check.\n", encoding="utf-8")
    patch = v.digest(root / "artifact.txt")
    evidence = dict(id="e1", claim_id="a1", type="source", revision="fixture-v1",
                    patch_id=patch, scope_id="local-read-v1", artifact="artifact.txt",
                    artifact_sha256=patch, operation="read artifact.txt", environment="synthetic local fixture",
                    raw_output="output.txt", raw_sha256=v.digest(root / "output.txt"),
                    recorded_at="2026-10-26T00:00:00Z", status="passed", collected=1, executed=1,
                    passed=1, failed=0, skipped=0, exit_code=0, expected_exit=0,
                    negative_control=None, coverage="one source observation", limitations=["No runtime behavior checked"])
    return dict(schema_version=1, id="example-task", mode="investigate", size="tiny",
                goal="Describe the parser contract from the fixture", non_goals=["No source edits or publication"],
                scope_id="local-read-v1", revision="fixture-v1", patch_id=patch, author_id="fixture-author",
                authority=dict(allowed_actions=["read", "local-write"], forbidden_actions=["push","pr","merge","deploy","egress","credential-access","policy-edit","install"],
                               allowed_paths=["src/parser"]),
                host=dict(name="synthetic", version="fixture-1", capabilities=[
                    dict(name="denied-path-enforcement", availability="unsupported", evidence="No host sandbox in this fixture")]),
                requirements=[], work_units=[], acceptance=[dict(id="a1", claim="Parser returns a string", required=True,
                    requires_runtime=False, requires_negative_control=False, evidence_ids=["e1"], status="passed")],
                actions=[], evidence=[evidence], findings=[], reviews=[], lessons=[], docs=[],
                history=[dict(id="h1", **{"from":"framed","to":"inspected"}, scope_id="local-read-v1", patch_id=patch),
                         dict(id="h2", **{"from":"inspected","to":"delivered"}, scope_id="local-read-v1", patch_id=patch)],
                state="delivered", completion="complete", verification="source-audited",
                independent_review_required=False, delivery="local", next_safe_action="Report source-audited result", blockers=[])


class EstackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="estack-fixture-")
        self.root = pathlib.Path(self.temp.name)
        self.task = make_task(self.root)
        self.context = {k:self.task[k] for k in ("revision","scope_id","patch_id")}

    def tearDown(self):
        self.temp.cleanup()

    def errors(self, task=None, previous=None):
        return v.check_task(task or self.task, self.root, self.context, previous)

    def reject(self, text):
        errors = self.errors()
        self.assertTrue(any(text in error for error in errors), errors)

    def node(self, source, label):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Installed Node required; no installation fallback")
        env = dict(os.environ, ESTACK_FIXTURE=str(source.resolve()))
        result = subprocess.run([node, "--test", "--test-reporter=tap", str(FIXTURES / "add.test.cjs")],
                                env=env, capture_output=True, text=True, timeout=30)
        target = os.environ.get("ESTACK_TEST_ARTIFACTS")
        if target:
            output = pathlib.Path(target)
            output.mkdir(parents=True, exist_ok=True)
            (output / (label + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
            (output / (label + ".source.cjs")).write_bytes(source.read_bytes())
            (output / (label + ".json")).write_text(json.dumps({
                "command":[node, "--test", "--test-reporter=tap", str(FIXTURES / "add.test.cjs")],
                "source_sha256":v.digest(source), "exit_code":result.returncode,
                "raw_output_sha256":v.digest(output / (label + ".txt")),
                "environment":"native Node " + subprocess.check_output([node,"--version"],text=True).strip(),
                "claim":"deterministic fixture only; runner and candidate share author context"
            },indent=2),encoding="utf-8")
        return result

    def test_E01_requirement_origins(self):
        self.task["requirements"] = [
            dict(id="r1",text="Offline",origin="user",status="active",supersedes=None),
            dict(id="r2",text="No cloud storage",origin="user",status="active",supersedes=None),
            dict(id="r3",text="Use simple local HTML",origin="assumption",status="active",supersedes=None)]
        self.assertEqual(self.errors(), [])
        self.task["requirements"][2]["origin"] = "user-inferred"
        self.reject("value outside enum")

    def test_E02_superseded_intent(self):
        self.task["requirements"] = [
            dict(id="r1",text="SQLite",origin="user",status="active",supersedes=None),
            dict(id="r2",text="JSON; no database",origin="user",status="active",supersedes="r1")]
        self.reject("still active")
        self.task["requirements"][0]["status"] = "superseded"
        self.assertEqual(self.errors(), [])

    def test_E03_tiny_real_fixture(self):
        good = self.node(FIXTURES / "add.good.cjs", "E03-good")
        self.assertEqual(good.returncode, 0, good.stdout)
        self.assertRegex(good.stdout, r"# pass 2")
        self.assertEqual(self.task["size"], "tiny")
        # This check does not measure an agent's interview or scope choices.

    def test_E04_red_green_negative_control(self):
        bad = self.node(FIXTURES / "add.bad.cjs", "E04-red")
        good = self.node(FIXTURES / "add.good.cjs", "E04-green")
        control = self.root / "control.cjs"
        control.write_bytes((FIXTURES / "add.bad.cjs").read_bytes())
        broken = self.node(control, "E04-broken-control")
        self.assertNotEqual(bad.returncode, 0)
        self.assertRegex(bad.stdout, r"# fail 2")
        self.assertEqual(good.returncode, 0)
        self.assertRegex(good.stdout, r"# pass 2")
        self.assertNotEqual(broken.returncode, 0)
        self.assertRegex(broken.stdout, r"# fail 2")
        (self.root / "good.cjs").write_bytes((FIXTURES / "add.good.cjs").read_bytes())
        (self.root / "bad.cjs").write_bytes(control.read_bytes())
        (self.root / "green.txt").write_text(good.stdout + good.stderr, encoding="utf-8")
        (self.root / "broken.txt").write_text(broken.stdout + broken.stderr, encoding="utf-8")
        patch = v.digest(self.root / "good.cjs")
        e = self.task["evidence"][0]
        e.update(type="unit", patch_id=patch, artifact="good.cjs", artifact_sha256=patch,
                 raw_output="green.txt", raw_sha256=v.digest(self.root / "green.txt"),
                 operation="native Node --test --test-reporter=tap; add.test.cjs against good.cjs",
                 collected=2, executed=2, passed=2, failed=0, negative_control="broken",
                 coverage="positive operands and mixed signs", limitations=["Synthetic fixture; no model trial"])
        control_e = copy.deepcopy(e)
        control_e.update(id="broken", status="failed", artifact="bad.cjs",
                         artifact_sha256=v.digest(self.root / "bad.cjs"), raw_output="broken.txt",
                         raw_sha256=v.digest(self.root / "broken.txt"), passed=0, failed=2,
                         exit_code=broken.returncode, negative_control=None,
                         operation="native Node --test --test-reporter=tap; add.test.cjs against restored bad.cjs")
        self.task["evidence"].append(control_e)
        self.task.update(mode="repair", state="verified", history=[], patch_id=patch,
                         verification="runtime-tested", goal="Correct addition in synthetic fixture")
        self.context["patch_id"] = patch
        self.task["acceptance"][0].update(claim="add sums numbers", requires_runtime=True,
                                          requires_negative_control=True)
        self.assertEqual(self.errors(), [])

    def test_E05_dependency_integration(self):
        self.task["work_units"] = [
            dict(id="parser",goal="Change return shape",depends_on=[],allowed_paths=["parser.py"],status="done"),
            dict(id="normalizer",goal="Adapt consumer",depends_on=["parser"],allowed_paths=["normalizer.py"],status="done"),
            dict(id="cli",goal="Exercise path",depends_on=["normalizer"],allowed_paths=["cli.py"],status="done")]
        self.assertEqual(self.errors(), [])
        (self.root / "parser.py").write_text("def parse(value):\n    return {'text': value}\n")
        (self.root / "normalizer.py").write_text("from parser import parse\ndef normalize(v):\n    return parse(v).strip()\n")
        (self.root / "cli.py").write_text("from normalizer import normalize\nprint(normalize(' OK '))\n")
        command = [sys.executable,"-B",str(self.root / "cli.py")]
        broken = subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(broken.returncode,0)
        (self.root / "normalizer.py").write_text("from parser import parse\ndef normalize(v):\n    return parse(v)['text'].strip()\n")
        good = subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual((good.returncode,good.stdout.strip()),(0,"OK"))
        self.task["work_units"][0]["depends_on"]=["cli"]
        self.reject("cycle")

    def test_E06_constant_verifier_rejected(self):
        labels = [True,False]
        constant = lambda source: True
        behavior = lambda source: self.node(source, "E06-" + source.stem).returncode == 0
        sources = [FIXTURES / "add.good.cjs",FIXTURES / "add.bad.cjs"]
        self.assertNotEqual([constant(s) for s in sources], labels)
        self.assertEqual([behavior(s) for s in sources], labels)
        self.task["independent_review_required"]=True
        self.reject("independent review unavailable")

    def test_E07_untrusted_lesson_no_authority(self):
        fixture=v.read_json(FIXTURES / "adversarial-data.json")
        sentinel=self.root / "policy.txt"
        sentinel.write_text("unchanged")
        before=v.digest(sentinel)
        self.task["lessons"]=[dict(id="l1",source="fixture",scope_id=self.task["scope_id"],
            revision=self.task["revision"],expires_at="2099-01-01T00:00:00Z",
            text=fixture["lesson"],status="proposed")]
        self.assertEqual(self.errors(),[])
        self.task["actions"]=[self.action(kind="egress",target="https://example.invalid/collect")]
        self.reject("forbidden")
        self.assertEqual(v.digest(sentinel),before)

    def test_E08_stale_lesson(self):
        lesson=dict(id="l1",source="commit A parseAmount",scope_id=self.task["scope_id"],revision="commit-A",
                    expires_at="2099-01-01T00:00:00Z",text="old schema",status="revalidated")
        self.task["lessons"]=[lesson]
        self.reject("stale lesson")
        lesson["status"]="stale"
        self.assertEqual(self.errors(),[])

    def test_E09_denied_isolation_stays_denied(self):
        denied=self.action()
        denied.update(decision="denied",outcome="denied")
        self.task["actions"]=[denied]
        previous=copy.deepcopy(self.task)
        self.task["actions"][0].update(decision="approved",outcome="not-applied")
        errors=self.errors(previous=previous)
        self.assertTrue(any("denied action" in e for e in errors),errors)

    def test_E10_zero_tests(self):
        e=self.task["evidence"][0]
        e.update(type="unit",collected=0,executed=0,passed=0)
        self.reject("zero executed")

    def test_E11_stale_receipt(self):
        self.task["evidence"][0]["revision"]="another-revision"
        self.reject("stale receipt")
        self.task["evidence"][0]["revision"]=self.task["revision"]
        (self.root / "artifact.txt").write_text("changed")
        self.reject("changed artifact")

    def test_E12_diagnostic_is_not_sandbox(self):
        self.assertFalse(v.scope_path("src/payments/a.py",["src/parser"]))
        self.assertTrue(v.scope_path("src/parser/a.py",["src/parser"]))
        self.assertRaises(ValueError,v.safe_path,self.root,"../payments/a.py")
        caps=v.read_json(ROOT / "hosts/capabilities.json")
        self.assertFalse(caps["package_enforces_paths"])
        self.assertEqual(caps["qualification"],"not-run")
        # No attempt to write across an actual host-denied boundary.

    def test_E13_docs_mismatch(self):
        doc=dict(id="d1",source="frozen official pair",target_version="1.x",observed_version="2.x",
                 retrieved_at="2026-10-25T00:00:00Z",revalidate_after="2099-01-01T00:00:00Z",status="current")
        self.task["docs"]=[doc]
        self.reject("documentation")
        self.assertEqual(v.freshness(doc),"mismatch")
        doc.update(observed_version="1.x",revalidate_after="2020-01-01T00:00:00Z")
        self.assertEqual(v.freshness(doc),"stale")

    def test_E14_finish_cannot_push(self):
        self.task["actions"]=[self.action(kind="push",target="remote")]
        self.reject("forbidden")
        self.task["actions"]=[]
        self.assertEqual(self.errors(),[])

    def test_E15_missing_capability_not_invented(self):
        self.task["host"]["capabilities"]=[
            dict(name=name,availability="unsupported",evidence="fixture has none") for name in ("subagents","hooks")]
        self.task["independent_review_required"]=True
        self.reject("independent review unavailable")
        self.task.update(completion="partial",state="partial",verification="unverified",history=[],
                         blockers=["Independent reviewer unavailable"])
        self.assertEqual(self.errors(),[])

    def test_E16_stale_approval(self):
        action=self.action()
        action["decision"]="pending"
        response=dict(action,decision="approved")
        self.assertTrue(v.approval_matches(action,response,self.task["scope_id"]))
        self.assertFalse(v.approval_matches(action,response,"new-scope"))
        response["occurrence"]="older-pause"
        self.assertFalse(v.approval_matches(action,response,self.task["scope_id"]))
        response=dict(action,decision="approved",kind="deploy")
        self.assertFalse(v.approval_matches(action,response,self.task["scope_id"]))

    def test_E17_readiness_is_not_merged(self):
        self.task["delivery"]="merged"
        self.reject("delivery state lacks")
        self.task["actions"]=[self.action(kind="merge",target="remote")]
        self.reject("forbidden")

    def test_E18_marker_is_not_evidence(self):
        marker=v.read_json(FIXTURES / "adversarial-data.json")["worker_marker"]
        self.assertEqual(marker,"COMPLETE")
        self.task["evidence"]=[]
        self.reject("lacks passing evidence")

    def test_E19_caller_flags_not_proof(self):
        self.task["evidence"][0]["executed"]=True
        self.reject("expected integer")
        self.task["evidence"][0]["executed"]=1
        self.task["confidence"]=0.99
        self.reject("unknown key confidence")

    def test_E20_synthetic_credentials_unused(self):
        sentinel=self.root / "synthetic-deploy-credential.txt"
        sentinel.write_text("ESTACK_TEST_ONLY_NOT_A_REAL_SECRET")
        before=v.digest(sentinel)
        self.assertEqual(self.errors(),[])
        self.task["actions"]=[self.action(kind="credential-access",target=sentinel.name)]
        self.reject("forbidden")
        self.assertEqual(v.digest(sentinel),before)

    def action(self,kind="local-write",target="src/parser/a.py"):
        return dict(id="act-1",kind=kind,target=target,target_hash="a"*64,
                    scope_id=self.task["scope_id"],occurrence="pause-1",decision="approved",
                    outcome="not-applied",evidence_ids=[])

    def test_valid_source_audit_and_cli(self):
        self.assertEqual(self.errors(),[])
        path=self.root / "task.json"
        path.write_text(json.dumps(self.task),encoding="utf-8")
        command=[sys.executable,str(ROOT / "scripts/validate.py"),"task",str(path),"--root",str(self.root),
                 "--revision",self.task["revision"],"--scope",self.task["scope_id"],"--patch",self.task["patch_id"]]
        result=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertIn("consistency-only",result.stdout)

    def test_missing_host_observed_context(self):
        errors=v.check_task(self.task,self.root)
        self.assertTrue(any("host-observed" in e for e in errors))

    def test_malformed_records_and_duplicate_keys(self):
        self.task.pop("goal")
        self.reject("missing goal")
        path=self.root / "malformed.json"
        path.write_text('{"x":1,"x":2}')
        self.assertRaises(ValueError,v.read_json,path)
        path.write_text('{"x":NaN}')
        self.assertRaises(ValueError,v.read_json,path)

    def test_stale_output_and_missing_output(self):
        (self.root / "output.txt").write_text("forged/mismatched")
        self.reject("changed raw_output")
        (self.root / "output.txt").unlink()
        self.reject("missing or changed raw_output")

    def test_source_read_cannot_certify_runtime(self):
        self.task["acceptance"][0]["requires_runtime"]=True
        self.reject("source evidence is not runtime")

    def test_negative_control_required(self):
        self.task["acceptance"][0]["requires_negative_control"]=True
        self.reject("negative control")

    def test_uncertain_already_applied_reconciliation(self):
        action=self.action()
        action["outcome"]="uncertain"
        self.assertEqual(v.reconcile(action,"unknown"),"inspect-without-replay")
        self.assertEqual(v.reconcile(action,"applied"),"do-not-replay")
        self.assertEqual(v.reconcile(action,"not-applied"),"refresh-authority-before-retry")
        self.task["actions"]=[action]
        self.reject("uncertain mutation")
        previous=copy.deepcopy(self.task)
        action["outcome"]="applied"
        errors=self.errors(previous=previous)
        self.assertTrue(any("reconciled without evidence" in e for e in errors))
        # Reconciliation must describe this action; the acceptance receipt e1
        # refers to a different claim and cannot stand in for that observation.
        observation=copy.deepcopy(self.task["evidence"][0])
        observation.update(id="action-observed",claim_id=action["id"],
                           operation="Synthetic target inspection for the interrupted action")
        self.task["evidence"].append(observation)
        action["evidence_ids"]=["action-observed"]
        self.assertEqual(self.errors(previous=previous),[])
        self.assertEqual(v.reconcile(action,"unknown"),"do-not-replay")

    def test_denied_not_bypassed_by_observation(self):
        action=self.action()
        action.update(decision="denied",outcome="denied")
        self.assertEqual(v.reconcile(action,"not-applied"),"stop-denied")
        self.assertEqual(v.reconcile(action,"applied"),"stop-denied")

    def test_adversarial_event_replay_and_history(self):
        previous=copy.deepcopy(self.task)
        self.task["history"].append(copy.deepcopy(self.task["history"][-1]))
        self.reject("duplicate IDs")
        self.task=copy.deepcopy(previous)
        self.task["history"]=[]
        self.assertTrue(any("rewritten" in e for e in self.errors(previous=previous)))

    def test_changed_action_identity(self):
        self.task["actions"]=[self.action()]
        previous=copy.deepcopy(self.task)
        self.task["actions"][0]["target"]="src/parser/b.py"
        self.assertTrue(any("identity changed" in e for e in self.errors(previous=previous)))

    def test_applied_action_cannot_revert_for_retry(self):
        action=self.action()
        action["outcome"]="applied"
        self.task["actions"]=[action]
        previous=copy.deepcopy(self.task)
        action["outcome"]="not-applied"
        self.assertTrue(any("terminal action" in e for e in self.errors(previous=previous)))

    def test_illegal_transition_and_expanded_scope(self):
        self.task["history"][0]["to"]="deployed"
        self.reject("illegal state transition")
        self.task["actions"]=[self.action(target="src/payments/a.py")]
        self.reject("out-of-scope")

    def test_path_aliases_and_absolute_paths(self):
        for value in ("../a","a/../b","C:/secret","C:\\secret","/tmp/a","a//b","a/./b"):
            with self.subTest(path=value):
                self.assertRaises(ValueError,v.safe_path,self.root,value)
        # A Windows temporary root can use an 8.3 alias while safe_path returns
        # its resolved long name. Verify the file's identity across both names.
        self.assertTrue(v.safe_path(self.root,"artifact.txt").samefile(self.root / "artifact.txt"))

    def test_zero_test_discovery_rejected(self):
        result=subprocess.run([sys.executable,str(ROOT / "tests/run.py"),"--pattern","test_absent_*.py"],
                              capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertIn("zero tests",result.stdout)

    def test_review_cannot_impersonate_independence(self):
        self.task["reviews"]=[dict(id="rev1",author_id=self.task["author_id"],reviewer_id=self.task["author_id"],
            context_id="same-context",patch_id=self.task["patch_id"],kind="independent",
            status="completed",evidence_ids=["e1"],finding_ids=[])]
        self.reject("self-review labeled independent")

    def test_fixed_finding_needs_actual_receipt(self):
        self.task["findings"]=[dict(id="f1",claim="consumer broken",location="cli.py:1",
            consequence="CLI fails",evidence_ids=["e1"],severity="high",severity_rationale="required path",
            correction="adapt consumer",adjudication="fixed",rationale="change made",verification_ids=[])]
        self.reject("fixed finding lacks")

    def test_package_links_and_single_entrypoint(self):
        self.assertEqual(v.check_package(ROOT),[])
        copied=self.root / "package"
        shutil.copytree(ROOT,copied,ignore=shutil.ignore_patterns("__pycache__"))
        (copied / "references/verify.md").unlink()
        self.assertTrue(any("broken/escaping" in e for e in v.check_package(copied)))

