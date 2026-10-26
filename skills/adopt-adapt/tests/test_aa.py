import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aa.py"
spec = importlib.util.spec_from_file_location("aa", SCRIPT)
aa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aa)
ROOT = SCRIPT.parents[1]


def fixture(root, two_recipients=False):
    donor = root / "donor.txt"
    donor.write_text("A documented bounded retry uses a stable request ID.\n", encoding="utf-8")
    recipient = root / "recipient"
    recipient.mkdir()
    (recipient / "entry.py").write_text("def send(payload):\n    return client.send(payload)\n", encoding="utf-8")
    run = root / "run"
    record = aa.init_run(run, [str(donor)], ["target", "target2"] if two_recipients else ["target"])
    record["request"] = "Evaluate the documented retry pattern for target's sender."
    record["host"]["name"] = "unit-test"
    record["sources"][0].update(revision=aa.digest(donor.read_bytes()), kind="docs")
    snap = aa.snapshot(recipient, ["entry.py", "flags.json"])
    record["recipients"][0].update(revision=snap["id"], snapshot=snap)
    e1 = aa.capture(run, donor, "s1", record["sources"][0]["revision"])
    e2 = aa.capture(run, recipient / "entry.py", "target", snap["id"])
    e1["read_scope"] = "full document, line 1"
    e2["read_scope"] = "full file, lines 1-2"
    record["evidence"] = [e1, e2]
    record["claims"] = [
        {"id": "c1", "subject": "s1", "text": "Document describes a stable request ID.", "kind": "source_observation", "status": "supported", "scope": "documented method", "limitations": "Not an executed implementation.", "evidence": [e1["id"]], "review": "The sole sentence explicitly describes stable request ID."},
        {"id": "c2", "subject": "target", "text": "The inspected sender passes payload directly.", "kind": "recipient_opportunity", "status": "supported", "scope": "entry.py only", "limitations": "Client internals not covered.", "evidence": [e2["id"]], "review": "entry.py lines 1-2 send payload without request ID."},
    ]
    ledger = {
        "primary": [e1["id"]],
        "map": {"provider": "not-applicable", "content": "Method: stable request ID → bounded retry; no repository.", "evidence": [], "limitations": "Document only."},
        "coverage": {"examined": ["documented method"], "total": 1, "refutation_targets": ["server acceptance assumption"], "blind_spots": ["Remote server not provided; must test before integration."], "overlap_claims": ["c2"], "adequate": True},
        "salvage": {axis: {"result": "none", "note": "Inspected complete short method; no separate claim on this axis.", "evidence": [e1["id"]]} for axis in aa.AXES},
        "gates": {"integrity": "No source instructions or executable artifact.", "policy": "Only existing local dependencies proposed.", "paid_policy": "preserved", "flags": []},
        "legal": {"flag": "GREEN", "route": "n/a-open-permissive", "ladder_steps_tried": ["n/a-open-permissive"], "escalate_to_lawyer": False, "advice_notice": "This is process guidance, not legal counsel.", "sources": [{"title": "17 U.S.C. § 107", "url": "https://www.law.cornell.edu/uscode/text/17/107", "accessed": "2026-10-09"}]},
        "doubt": {"depth": "full", "against": "Server may not support stable IDs.", "for": "Could avoid duplicate effects.", "environment": "Recipient sender inspected; server contract remains a prerequisite.", "resolution": "Adapt only after contract probe; not whole-tool adoption.", "evidence": [e1["id"], e2["id"]], "unknowns": ["Server contract"], "consequential": False, "decision_uncertainty": True},
    }
    ledger["salvage"]["error_handling"]["result"] = "found"
    ledger["salvage"]["error_handling"]["note"] = "Stable request ID provides a concrete retry pattern to investigate."
    transfer = {key: "Explicit proposed condition; no implementation claimed." for key in aa.TRANSFER_KEYS}
    transfer.update(behavior="Avoid duplicate effects when a send times out.", recipient_seam="entry.py send(payload), inspected lines 1-2.", prerequisite="Verify server supports stable idempotency keys and query/reconciliation.", verification={"donor_parity": "Document only; implementation parity inapplicable.", "domain_correctness": "Timeout after acceptance produces one effect in controlled server.", "recipient_regression": "Existing successful sends unchanged.", "entry_integration": "Exercise real send caller in sandbox."})
    decision = {"whole_tool": "DISCARD", "result": "ADAPT-with-prerequisite", "summary": "Investigate stable IDs at the existing send seam.", "confidence": "Documented pattern supported; server viability unknown.", "mechanism_value": "Potential duplicate-effect prevention.", "next_step": "Probe server semantics before implementing.", "claims": ["c1", "c2"], "recipient_claims": ["c2"], "inventory": {k: {"state": "unknown", "scope": "Only inspected entry.py; other behavior unknown."} for k in ("implemented", "wired", "tested", "observed")}, "score": {"rubric": "generic", "components": [2, 2, 1, 2], "penalty": -1, "total": 6, "rationale": "Method fit with unresolved server semantics."}, "transfer": transfer}
    record["items"][0].update(state="READY", transitions=["QUEUED", "RESEARCHING", "READY"], ledger=ledger, decision=decision)
    if two_recipients:
        record["recipients"][1].update(revision=snap["id"], snapshot=snap)
        e3 = aa.capture(run, recipient / "entry.py", "target2", snap["id"])
        e3["read_scope"] = "full file, lines 1-2"
        record["evidence"].append(e3)
        record["claims"].append({"id": "c3", "subject": "target2", "text": "Second recipient sender passes payload directly.", "kind": "recipient_opportunity", "status": "supported", "scope": "entry.py only", "limitations": "Client internals not covered.", "evidence": [e3["id"]], "review": "entry.py lines 1-2 send payload without request ID."})
        d2 = copy.deepcopy(decision)
        d2.update(result="DISCARD", claims=["c1", "c3"], recipient_claims=["c3"], score=None, score_reason="Second recipient: not scored.")
        d2.pop("transfer"); d2.pop("inventory")
        record["items"][1].update(state="READY", transitions=["QUEUED", "RESEARCHING", "READY"], ledger=copy.deepcopy(ledger), decision=d2)
        record["items"][1]["ledger"]["coverage"]["overlap_claims"] = ["c3"]
        record["items"][1]["ledger"]["doubt"]["evidence"] = [e1["id"], e3["id"]]
    return run, record


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    _DEFAULT = object()

    def assert_bad(self, record=_DEFAULT, contains=None):
        # R3 fix: v2 used None as the default, so assert_bad(None) silently tested the valid fixture.
        errors = aa.validate(self.record if record is RecordTests._DEFAULT else record, self.run)
        self.assertTrue(errors)
        if contains:
            self.assertIn(contains, " ".join(errors))

    def test_complete_supported_record(self):
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        self.assertLess(output.index("aa:ledger:q1"), output.index("aa:verdict:q1"))
        self.assertTrue(aa.check_output(self.record, self.run, output))

    def test_malformed_inputs_report_errors(self):
        for bad in (None, [], "record", 1, {}, {"schema_version": 1}):
            with self.subTest(bad=bad): self.assert_bad(bad)

    def test_wrong_nested_types_report_errors(self):
        for key in ("sources", "recipients", "claims", "evidence", "items", "host"):
            record = copy.deepcopy(self.record); record[key] = None
            with self.subTest(key=key): self.assert_bad(record)

    def test_empty_evidence_not_verified(self):
        self.record["claims"][0]["evidence"] = []
        self.assert_bad(contains="references")

    def test_dangling_evidence_rejected(self):
        self.record["claims"][0]["evidence"] = ["invented"]
        self.assert_bad(contains="unknown references")

    def test_real_wrong_subject_receipt_rejected(self):
        self.record["claims"][0]["evidence"] = [self.record["evidence"][1]["id"]]
        self.assert_bad(contains="another subject")

    def test_modified_capture_rejected(self):
        (self.run / self.record["evidence"][0]["path"]).write_bytes(b"changed")
        self.assert_bad(contains="byte/hash")

    def test_wrong_revision_rejected(self):
        self.record["evidence"][0]["revision"] = "other"
        self.assert_bad(contains="revision mismatch")

    def test_unread_receipt_rejected(self):
        self.record["evidence"][0]["read_scope"] = "unread"
        self.assert_bad(contains="unread")

    def test_semantic_truth_is_not_claimed(self):
        self.record["claims"][0]["text"] = "This method proves every network request can never fail."
        # Intentional boundary probe: a hash checker cannot judge arbitrary prose entailment.
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.assertIn("semantic review remains necessary", aa.render(self.record, self.run))

    def test_missing_axis_rejected(self):
        del self.record["items"][0]["ledger"]["salvage"]["performance"]
        self.assert_bad(contains="five salvage")

    def test_incomplete_map_rejected(self):
        self.record["items"][0]["ledger"]["map"]["provider"] = "incomplete"
        self.assert_bad(contains="BLOCKED")

    def test_repo_requires_map(self):
        self.record["sources"][0]["kind"] = "repo"
        self.assert_bad(contains="architecture map")

    def test_map_ladder_providers_render(self):
        self.record["sources"][0]["kind"] = "repo"
        mapping = self.record["items"][0]["ledger"]["map"]
        mapping["evidence"] = [self.record["evidence"][0]["id"]]
        for provider in ("codewiki", "deepwiki", "self-synthesized"):
            mapping["provider"] = provider
            self.assertIn(provider, aa.render(self.record, self.run))

    def test_missing_gap_support_rejected(self):
        self.record["items"][0]["decision"]["recipient_claims"] = []
        self.assert_bad(contains="recipient support")

    def test_dead_helper_not_already_covered(self):
        decision = self.record["items"][0]["decision"]
        decision["result"] = "ALREADY-COVERED"
        decision["inventory"]["implemented"]["state"] = "present"
        decision["inventory"]["wired"]["state"] = "absent"
        self.assert_bad(contains="unwired")
        decision["inventory"]["wired"]["state"] = "present"
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_changed_untracked_configuration_detected(self):
        (self.root / "recipient" / "flags.json").write_text('{"enabled":true}', encoding="utf-8")
        self.assert_bad(contains="stale")
        self.assertEqual(aa.validate(self.record, self.run, live=False), [])

    def test_same_files_different_root_changes_identity(self):
        other = self.root / "other"; other.mkdir()
        (other / "entry.py").write_bytes((self.root / "recipient" / "entry.py").read_bytes())
        self.assertNotEqual(aa.snapshot(other, ["entry.py", "flags.json"])["id"], self.record["recipients"][0]["revision"])

    def test_paid_whole_free_part_supported(self):
        gates = self.record["items"][0]["ledger"]["gates"]
        gates["flags"] = [{"code": "PAID-ELEMENT", "scope": "whole", "status": "blocked", "resolution": "Discard paid service; free documented local pattern only."}]
        self.assertEqual(aa.validate(self.record, self.run), [])
        gates["flags"][0]["scope"] = "both"
        self.assert_bad(contains="paid mechanism")

    def test_profile_capture_not_informational(self):
        self.record["items"][0]["ledger"]["gates"]["flags"] = [{"code": "PROFILE-CAPTURE", "scope": "mechanism", "status": "unresolved", "resolution": "No consent."}]
        self.assert_bad(contains="blocks transfer")

    def test_wrong_score_and_boolean_component_rejected(self):
        s = self.record["items"][0]["decision"]["score"]
        s["total"] = 10; self.assert_bad(contains="total mismatch")
        s["total"] = 6; s["components"][0] = True; self.assert_bad(contains="component")

    def test_score_extremes_and_doubt_routes(self):
        for rubric, components in (("generic", [3, 3, 2, 2]), ("eddie", [3, 3, 2, 2]), ("tooling", [3, 2, 3, 2])):
            self.assertEqual(aa.score(rubric, components, 0), 10)
            self.assertEqual(aa.score(rubric, [0, 0, 0, 0], -2), -2)
        self.assertEqual(aa.doubt_depth("ADOPT", 10), "full")
        self.assertEqual(aa.doubt_depth("DISCARD", 1), "light")
        self.assertEqual(aa.doubt_depth("DISCARD", 1, live=True), "full")
        self.assertEqual(aa.doubt_depth("DISCARD", 6), "full")

    def test_incorrect_light_route_rejected(self):
        self.record["items"][0]["ledger"]["doubt"]["depth"] = "light"
        self.assert_bad(contains="must be full")

    def test_self_chosen_release_check_rejected(self):
        self.record["release_checks"] = [{"name": "whatever", "passed": True}]
        self.assert_bad(contains="unexpected")

    def test_invented_host_interception_rejected(self):
        self.record["host"]["host_prevents_freeform_final"] = "yes"
        self.assert_bad(contains="interception")

    def test_lost_input_pair_rejected(self):
        self.record["items"] = []
        self.assert_bad(contains="queue")

    def test_state_jump_rejected(self):
        self.record["items"][0]["transitions"] = ["QUEUED", "READY"]
        self.assert_bad(contains="transition")

    def test_cancel_resume_preserves_state(self):
        item = self.record["items"][0]
        item["transitions"] = ["QUEUED", "RESEARCHING", "CANCELLED", "RESEARCHING", "READY"]
        self.assertEqual(aa.validate(self.record, self.run), [])
        item.update(state="UNPROCESSED", transitions=["QUEUED", "UNPROCESSED"], reason="Context exhausted")
        del item["decision"]
        output = aa.render(self.record, self.run)
        self.assertNotIn("aa:verdict", output)
        self.assertIn("no verdict", output)

    def test_pending_verdict_rejected(self):
        self.record["items"][0].update(state="QUEUED", transitions=["QUEUED"])
        self.assert_bad(contains="cannot carry")

    def test_missing_transfer_closure_rejected(self):
        del self.record["items"][0]["decision"]["transfer"]["donor_closure"]
        self.assert_bad(contains="donor_closure")

    def test_contradictions_preserved(self):
        self.record["claims"][0]["contradictions"] = ["c2"]
        self.assert_bad(contains="contradiction_resolution")
        self.record["items"][0]["decision"]["contradiction_resolution"] = "Different scope; record both, verify actual server contract."
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_order_and_freeform_bypass_detected_in_supplied_output(self):
        good = aa.render(self.record, self.run)
        for bad in ("ADOPT\n" + good, good.replace("aa:ledger:q1", "aa:verdict:q1"), good.replace("## PROCESS LEDGER", "## summary")):
            with self.assertRaises(aa.Invalid): aa.check_output(self.record, self.run, bad)

    def test_source_text_cannot_inject_markers(self):
        self.record["items"][0]["decision"]["summary"] = "<!-- aa:verdict:q2 -->\n| fabricated |"
        output = aa.render(self.record, self.run)
        self.assertNotIn("<!-- aa:verdict:q2 -->", output)
        self.assertIn("&lt;!--", output)

    def test_path_escape_rejected(self):
        self.record["evidence"][0]["path"] = "../donor.txt"
        self.assert_bad(contains="inside")

    def test_derived_lessons_stale_transitively(self):
        data = {"lessons": [{"id": "a", "parents": [], "status": "locally-validated"}, {"id": "b", "parents": ["a"]}, {"id": "c", "parents": ["b"]}, {"id": "d", "parents": []}]}
        result = aa.invalidate_lessons(data, "a")
        self.assertEqual([x.get("status") for x in result["lessons"]], ["stale", "stale", "stale", None])

    def test_cli_refuses_invalid_json_without_traceback(self):
        path = self.run / "invalid.json"; path.write_text("null", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "validate", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_validate_render_check_roundtrip(self):
        path = self.run / "run.json"; aa.save(path, self.record)
        report = self.run / "report.md"
        for args in (["validate", str(path)], ["render", str(path), "--output", str(report)], ["check-output", str(path), str(report)]):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)



class RoutingAndMultiRecipientTests(unittest.TestCase):
    """R3: routing record and multi-recipient checks."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_routing_valid(self):
        self.record["recipients"][0]["profile"] = "radar"
        self.record["routing"] = [{"profile": "radar", "confidence": "high", "evidence": ["cwd is Radar repo"], "explicit": False}]
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.assertIn("## Routing", aa.render(self.record, self.run))

    def test_profile_without_routing_entry_rejected(self):
        self.record["recipients"][0]["profile"] = "eddie"
        self.record["routing"] = [{"profile": "radar", "confidence": "high", "evidence": ["x"], "explicit": False}]
        self.assertIn("not justified", " ".join(aa.validate(self.record, self.run)))

    def test_self_requires_explicit(self):
        self.record["recipients"][0]["profile"] = "self"
        self.assertTrue(aa.validate(self.record, self.run))
        self.record["routing"] = [{"profile": "self", "confidence": "medium", "evidence": ["donor is a skill"], "explicit": False}]
        self.assertIn("explicit", " ".join(aa.validate(self.record, self.run)))
        self.record["routing"][0]["explicit"] = True
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_bad_confidence_and_empty_evidence(self):
        self.record["routing"] = [{"profile": "radar", "confidence": "sure", "evidence": ["x"], "explicit": False}]
        self.assertTrue(aa.validate(self.record, self.run))
        self.record["routing"] = [{"profile": "radar", "confidence": "low", "evidence": [], "explicit": False}]
        self.assertTrue(aa.validate(self.record, self.run))

    def test_recipient_claim_bleed_rejected(self):
        bad = copy.deepcopy(self.record)
        bad["claims"][1]["subject"] = "s1"
        self.assertTrue(aa.validate(bad, self.run))

    def test_multi_recipient_shared_ledger_and_conflict_summary(self):
        multi = self.root / "multi"; multi.mkdir()
        run, rec = fixture(multi, two_recipients=True)
        self.assertEqual(aa.validate(rec, run), [])
        out = aa.render(rec, run)
        self.assertIn("## Cross-recipient summary", out)
        self.assertIn("CONFLICT", out)
        diverged = copy.deepcopy(rec)
        extra = aa.capture(run, self.root / "multi" / "donor.txt", "s1", rec["sources"][0]["revision"])
        extra["id"] = extra["id"][:-1] + ("x" if extra["id"][-1] != "x" else "y"); extra["read_scope"] = "full document, line 1"
        diverged["evidence"].append(extra)
        diverged["items"][1]["ledger"]["primary"] = [extra["id"]]
        self.assertIn("share one donor evidence ledger", " ".join(aa.validate(diverged, run)))
        bleed = copy.deepcopy(rec)
        bleed["items"][1]["decision"]["recipient_claims"] = ["c2"]
        self.assertTrue(aa.validate(bleed, run))

    def test_single_recipient_has_no_cross_summary(self):
        self.assertNotIn("Cross-recipient summary", aa.render(self.record, self.run))


class R5Tests(unittest.TestCase):
    """R5: donor-risk audit, RE ladder, hook intake (references/re-verification.md, due-diligence.md, hook-intake.md)."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)
        self.ledger = self.record["items"][0]["ledger"]

    def tearDown(self):
        self.temp.cleanup()

    def err(self):
        return " ".join(aa.validate(self.record, self.run))

    def re_claim(self, **kw):
        c = {"id": "re1", "claim": "Recovered jump table matches decoded bytes", "status": "pass", "scope": "unit",
             "provenance": {"tool": "ghidra", "version": "12.1.4", "sha256": "a" * 64, "options": "-noanalysis -readOnly", "label": "observed"},
             "assertions": 3, "negative_controls": 1, "verified": True, "legal_posture": "GREEN own fixture", "oracle_kind": "independent-decode",
             "run_counts": {"total": 3, "skipped": 0, "failed": 0}, "method": "other", "method_reason": "Scoped jump-table analysis",
             "output": "Recovered jump table from owned synthetic fixture", "baseline": "Fixture source and binary revision A",
             "contribution": "Decode comparison only", "distribution": "Owned fixture and report only",
             "method_checks": {"scoped_acceptance": {"status": "pass", "evidence": "Independent byte decode and planted wrong destination rejected"}}}
        # R7 full records bind pass labels to a real owned run; structural failures remain unchanged.
        from test_evidence_workflow import attach_execution
        attach_execution(self.run, self.record, c, counts=kw.get("run_counts"))
        c.update(kw)
        return c

    def hook(self, **kw):
        h = {"id": "h1", "content_sha256": "b" * 64, "approved_sha256": "b" * 64, "approved_by": "user", "output_schema": "strict",
             "env": "allowlist", "approval_log": "visible-named", "on_error": "ask",
             "files": [{"path": "hooks/x.sh", "sha256": "d" * 64}], "approved_files": {"hooks/x.sh": "d" * 64}, "decision_log": "durable"}
        h.update(kw)
        return h

    def test_valid_re_claim_and_risk_render(self):
        self.ledger["re_claims"] = [self.re_claim()]
        self.ledger["donor_risks"] = [{"code": "ENV-LEAK", "evidence": "oracles.mjs:233", "status": "absent", "scope": "mechanism"}]
        self.assertEqual(aa.validate(self.record, self.run), [])
        out = aa.render(self.record, self.run)
        self.assertIn("RE re1: pass", out)
        self.assertIn("DONOR RISK ENV-LEAK", out)
        self.assertLess(out.index("DONOR RISK"), out.index("aa:verdict:q1"))

    def test_re_status_must_come_from_ladder(self):
        self.ledger["re_claims"] = [self.re_claim(status="verified-ish", verified=False)]
        self.assertIn("RE ladder", self.err())

    def test_verified_needs_assertion_and_negative_control(self):
        self.ledger["re_claims"] = [self.re_claim(negative_controls=0)]
        self.assertIn("negative control", self.err())
        self.ledger["re_claims"] = [self.re_claim(assertions=0, negative_controls=1)]
        self.assertIn("assertion", self.err())

    def test_bounded_run_not_campaign_pass(self):
        self.ledger["re_claims"] = [self.re_claim(scope="bounded", reported_as="campaign-pass")]
        self.assertIn("campaign pass", self.err())

    def test_re_claim_needs_provenance(self):
        c = self.re_claim(); del c["provenance"]["sha256"]
        self.ledger["re_claims"] = [c]
        self.assertIn("provenance", self.err())
        self.ledger["re_claims"] = [self.re_claim(provenance={"tool": "ilspy", "version": "9", "sha256": "z" * 64, "options": "x", "label": "observed"})]
        self.assertIn("64 lowercase hex", self.err())

    def test_decompiler_output_is_inferred(self):
        c = self.re_claim(); c["provenance"]["decompiler"] = True
        self.ledger["re_claims"] = [c]
        self.assertIn("inferred", self.err())
        c["provenance"]["label"] = "inferred"
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_unknown_status_cannot_be_verified(self):
        self.ledger["re_claims"] = [self.re_claim(status="unknown")]
        self.assertIn("status pass", self.err())

    def test_agent_donor_requires_risk_audit(self):
        self.record["sources"][0]["kind"] = "skill"
        self.assertIn("donor_risks", self.err())
        self.ledger["donor_risks"] = []
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_risk_codes_and_evidence_checked(self):
        self.ledger["donor_risks"] = [{"code": "MADE-UP", "evidence": "x.py:1", "status": "present", "scope": "mechanism"}]
        self.assertIn("unknown donor risk code", self.err())
        self.ledger["donor_risks"] = [{"code": "FAIL-OPEN-GUARD", "evidence": "somewhere", "status": "present", "scope": "mechanism"}]
        self.assertIn("file:line", self.err())

    def test_every_new_risk_class_recognised(self):
        for code in ("FAIL-OPEN-GUARD", "RUNNER-MISCOUNT", "NO-ASSERT-VERIFIED", "SILENT-SKIP-PASS", "HARDCODED-CLAIM", "HOOK-AUTO-ANSWER",
                     "HOOK-APPROVAL-UNLOGGED", "ENV-LEAK", "UNPINNED-SESSION-INSTALL", "INSTRUCTION-TRUNCATION", "OVERRIDE-FILE",
                     "COMMENT-SUPPRESSION", "CLIENT-CONFIG-WRITE", "UNBOUNDED-STOP-HOOK", "TAG-PINNED-ACTIONS", "HAND-PATH-FILTERS",
                     "PUBLISH-NO-HASH", "NO-TEST-TIMEOUT"):
            with self.subTest(code=code):
                self.ledger["donor_risks"] = [{"code": code, "evidence": "f.py:1", "status": "absent", "scope": "whole"}]
                self.assertEqual(aa.validate(self.record, self.run), [])

    def test_present_risk_forces_prerequisite(self):
        self.ledger["donor_risks"] = [{"code": "HOOK-AUTO-ANSWER", "evidence": "question-preference-hook.ts:1", "status": "present", "scope": "mechanism"}]
        self.assertEqual(aa.validate(self.record, self.run), [])  # fixture is already ADAPT-with-prerequisite
        self.record["items"][0]["decision"]["result"] = "ADAPT"
        self.record["items"][0]["decision"]["transfer"].pop("prerequisite", None)
        self.assertIn("present donor risk", self.err())

    def test_hook_intake_valid(self):
        self.ledger["hooks"] = [self.hook()]
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_hook_edit_revokes_approval(self):
        self.ledger["hooks"] = [self.hook(content_sha256="c" * 64)]
        self.assertIn("approval revoked", self.err())

    def test_hook_project_config_cannot_approve(self):
        self.ledger["hooks"] = [self.hook(approved_by="project")]
        self.assertIn("never project config", self.err())

    def test_hook_policy_fields(self):
        for kw, msg in ((dict(output_schema="lenient"), "strict"), (dict(env="full"), "allowlist"), (dict(approval_log="none"), "visibly"),
                        (dict(on_error="allow"), "fail open"), (dict(auto_answer=True), "auto-answer"), (dict(event="Stop", max_iterations=0), "iteration cap")):
            with self.subTest(kw=kw):
                self.ledger["hooks"] = [self.hook(**kw)]
                self.assertIn(msg, self.err())

    def test_trigger_evals_cover_r5(self):
        data = json.loads((ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8"))
        text = " ".join(x["query"].lower() for x in data if x["should_trigger"])
        for needle in ("decompil", "hook", "verify script"):
            self.assertIn(needle, text)


    # R5.1 checks
    def test_verified_needs_oracle_kind(self):
        c = self.re_claim(); del c["oracle_kind"]
        self.ledger["re_claims"] = [c]
        self.assertIn("oracle_kind", self.err())

    def test_weak_oracle_cannot_verify(self):
        for kind in ("recompile-only", "self-roundtrip", "fallback"):
            with self.subTest(kind=kind):
                self.ledger["re_claims"] = [self.re_claim(oracle_kind=kind)]
                self.assertIn("cannot make a claim verified", self.err())
        self.ledger["re_claims"] = [self.re_claim(oracle_kind="recompile-only", verified=False, status="unknown")]
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_zero_tests_not_pass(self):
        self.ledger["re_claims"] = [self.re_claim(run_counts={"total": 0, "skipped": 0, "failed": 0})]
        self.assertIn("zero tests", self.err())

    def test_skips_need_allowlist(self):
        self.ledger["re_claims"] = [self.re_claim(run_counts={"total": 5, "skipped": 2, "failed": 0})]
        self.assertIn("allow-listed reason", self.err())
        self.ledger["re_claims"] = [self.re_claim(run_counts={"total": 5, "skipped": 2, "failed": 0}, skip_allowlist=["no GPU: device limit", "win: no Vulkan"])]
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_failed_or_inconsistent_counts(self):
        self.ledger["re_claims"] = [self.re_claim(run_counts={"total": 5, "skipped": 0, "failed": 1})]
        self.assertIn("failed tests", self.err())
        self.ledger["re_claims"] = [self.re_claim(run_counts={"total": 1, "skipped": 1, "failed": 1})]
        self.assertIn("inconsistent", self.err())

    def test_r51_risk_codes_recognised(self):
        for code in ("AUTO-EXEC", "INSTRUCTION-TAMPER", "AGENT-ADDRESSED-TEXT", "DONOR-STEERED-MAP", "ERROR-BODY-SUCCESS",
                     "SELF-ATTESTED-EVIDENCE", "CONTINUE-ON-ERROR", "UNRUN-SUITE", "ABSENT-METRIC-PASS", "RATCHET-LOWERED"):
            with self.subTest(code=code):
                self.ledger["donor_risks"] = [{"code": code, "evidence": "f.py:1", "status": "absent", "scope": "whole"}]
                self.assertEqual(aa.validate(self.record, self.run), [])


    # R5.2: hook script hashing, matcher, durable record
    def test_hook_script_edit_revokes_even_if_config_same(self):
        self.ledger["hooks"] = [self.hook(files=[{"path": "hooks/x.sh", "sha256": "e" * 64}])]
        self.assertIn("changed or unapproved", self.err())

    def test_hook_config_only_hash_rejected(self):
        h = self.hook(); h["files"] = []
        self.ledger["hooks"] = [h]
        self.assertIn("config-only hash", self.err())

    def test_hook_unapproved_extra_file(self):
        self.ledger["hooks"] = [self.hook(approved_files={"hooks/x.sh": "d" * 64, "hooks/lib.sh": "f" * 64})]
        self.assertIn("differ from hashed files", self.err())

    def test_hook_bad_matcher_is_error(self):
        self.ledger["hooks"] = [self.hook(matcher="[")]
        self.assertIn("never match-all", self.err())
        self.ledger["hooks"] = [self.hook(matcher="Bash|Edit")]
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_hook_needs_durable_record(self):
        self.ledger["hooks"] = [self.hook(decision_log="telemetry")]
        self.assertIn("durable", self.err())

    def test_r52_risk_codes_recognised(self):
        for code in ("REVIEW-MARKED-ON-FAILURE", "DROPPED-FILES-MARKED", "LAST-COMMIT-ONLY", "BASE-URL-EXFIL", "MATCHER-MATCH-ALL",
                     "UNQUOTED-PATH-SUBST", "FORCED-MANAGED-HOOK", "HOOK-CONFIG-WARN-ONLY", "HOOK-RUN-UNRECORDED", "CONFIG-HASH-ONLY-TRUST"):
            with self.subTest(code=code):
                self.ledger["donor_risks"] = [{"code": code, "evidence": "f.py:1", "status": "absent", "scope": "whole"}]
                self.assertEqual(aa.validate(self.record, self.run), [])



class RecipientPathTests(unittest.TestCase):
    """Portfolio variant: synthetic caller rules preserve conservative path semantics."""
    def rules(self):
        return {"revision": "synthetic-rules-v1", "governed_prefixes": ["src/protected/"],
                "governed_exact": ["src/exact.ts"], "measurement_dependencies": ["metrics/bridge.ts", "notes/measurement.ts"],
                "policy_prefixes": [".policy/"], "preflight_self": ["tools/preflight.ts"],
                "documentation_prefixes": ["notes/"], "test_suffixes": [".test.ts", ".test.js", ".test.mjs"]}

    def test_caller_rules_are_required_and_preserved(self):
        with self.assertRaisesRegex(ValueError, "No bundled recipient rules"):
            aa.radar_path_class("src/protected/x.ts")
        rules = self.rules()
        before = copy.deepcopy(rules)
        self.assertEqual(aa.recipient_path_class("src/exact.ts", rules)["pin"], "synthetic-rules-v1")
        self.assertEqual(rules, before)

    def test_measurement_dependency_is_not_safe(self):
        r = aa.recipient_path_class("metrics/bridge.ts", self.rules())
        self.assertEqual(r["class"], "measurement-dependency")
        self.assertFalse(r["safe_to_change"])

    def test_unlisted_file_ungoverned_but_needs_disposition(self):
        r = aa.recipient_path_class("src/other/index.ts", self.rules())
        self.assertEqual(r["class"], "ungoverned-needs-disposition")
        self.assertFalse(r["safe_to_change"])

    def test_governed_prefix_exact_and_windows_path(self):
        self.assertEqual(aa.recipient_path_class("src/protected/x.ts", self.rules())["class"], "governed")
        self.assertEqual(aa.recipient_path_class("src\\exact.ts", self.rules())["class"], "governed")

    def test_explicit_test_exclusions_policy_and_docs(self):
        self.assertNotEqual(aa.recipient_path_class("src/protected/x.test.ts", self.rules())["class"], "governed")
        self.assertEqual(aa.recipient_path_class(".policy/freeze.md", self.rules())["class"], "freeze-policy-drift")
        r = aa.recipient_path_class("notes/a.md", self.rules())
        self.assertTrue(r["safe_to_change"])
        self.assertIn("not-granted", r["authorization"])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "rules.json"
            rules.write_text(json.dumps(self.rules()), encoding="utf-8")
            for command in ("classify-path", "radar-path"):
                out = subprocess.run([sys.executable, "-B", str(SCRIPT), command, "metrics/bridge.ts", "--rules", str(rules)], capture_output=True, text=True, check=True).stdout
                self.assertEqual(json.loads(out)[0]["class"], "measurement-dependency")
            refused = subprocess.run([sys.executable, "-B", str(SCRIPT), "radar-path", "metrics/bridge.ts"], capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertIn("No bundled recipient rules", refused.stderr)

    def test_measurement_precedes_documentation(self):
        r = aa.recipient_path_class("notes/measurement.ts", self.rules())
        self.assertEqual(r["class"], "measurement-dependency")
        self.assertFalse(r["safe_to_change"])

    def test_missing_or_malformed_rules_refused(self):
        for rules in ({}, None, {"revision": "unverified"}, dict(self.rules(), governed_prefixes="src/"),
                      dict(self.rules(), documentation_prefixes=["../"]), dict(self.rules(), revision="")):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                aa.recipient_path_class("notes/a.md", rules)

    def test_noncanonical_and_absolute_paths_refused(self):
        for path in ("../outside", "/absolute", "C:\\absolute", "src/../notes/a.md", "src//x", "./x", "x\n"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                aa.recipient_path_class(path, self.rules())

    def test_duplicate_rule_keys_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "rules.json"
            rules.write_text('{"revision":"a","revision":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate path-rule JSON key"):
                aa.load_path_rules(rules)

if __name__ == "__main__":
    unittest.main()


class LegalGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_legal_flag_required(self):
        del self.record["items"][0]["ledger"]["legal"]
        self.assertIn("ledger.legal", " ".join(aa.validate(self.record, self.run)))

    def test_legal_red_blocks_transfer(self):
        self.record["items"][0]["ledger"]["legal"]["flag"] = "RED"
        self.record["items"][0]["ledger"]["legal"]["route"] = "discard"
        self.record["items"][0]["ledger"]["legal"]["escalate_to_lawyer"] = True
        err = " ".join(aa.validate(self.record, self.run))
        self.assertIn("legal RED/UNKNOWN blocks transfer", err)

    def test_legal_unknown_blocks_transfer(self):
        self.record["items"][0]["ledger"]["legal"]["flag"] = "UNKNOWN"
        err = " ".join(aa.validate(self.record, self.run))
        self.assertIn("legal RED/UNKNOWN blocks transfer", err)

    def test_legal_yellow_requires_prerequisite(self):
        self.record["items"][0]["ledger"]["legal"]["flag"] = "YELLOW"
        self.record["items"][0]["ledger"]["legal"]["route"] = "idea-only"
        self.record["items"][0]["decision"]["result"] = "ADAPT"
        # keep transfer present from fixture
        err = " ".join(aa.validate(self.record, self.run))
        self.assertIn("YELLOW legal flag requires ADAPT-with-prerequisite", err)

    def test_inferred_claim_needs_confidence(self):
        self.record["claims"].append({
            "id": "c_inf", "subject": "s1", "text": "Inferred internal queue.", "kind": "mechanism",
            "status": "inferred", "scope": "docs", "limitations": "not observed", "evidence": [self.record["evidence"][0]["id"]],
        })
        self.record["items"][0]["decision"]["claims"] = ["c1", "c2", "c_inf"]
        err = " ".join(aa.validate(self.record, self.run))
        self.assertIn("confidence", err)
        self.record["claims"][-1]["confidence"] = "inferred"
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_legal_green_render(self):
        out = aa.render(self.record, self.run)
        self.assertIn("LEGAL: GREEN", out)
        self.assertLess(out.index("LEGAL:"), out.index("aa:verdict:q1"))
