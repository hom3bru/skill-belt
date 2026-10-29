"""r16 candidate, fourth pass (second independent review): a ladder level on every claim, with confidence and
mechanism value capped by it; profile, rubric and routing binding; proportionate independent review; honest
verdicts (need = gap plus symptom or requirement, DISCARD (promising: ...), OPPORTUNITY only without a
recipient); legal fixes (hard lines, patent signal on every reuse route, licence waiver); the routing index,
the outcome log and the bounded-ledger template. Each validator test reproduces a probe the review saw accepted."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_aa import aa, fixture, SCRIPT
from test_r16b import recipient_run

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)
        self.item = self.record["items"][0]
        self.decision = self.item["decision"]
        self.ledger = self.item["ledger"]
        self.legal = self.ledger["legal"]
        self.claims = {c["id"]: c for c in self.record["claims"]}

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return " ".join(aa.validate(self.record, self.run))

    def assertRejected(self, *fragments):
        message = self.errors()
        self.assertTrue(message, "record was accepted")
        for fragment in fragments:
            self.assertIn(fragment, message)

    def assertValid(self):
        self.assertEqual(aa.validate(self.record, self.run), [])

    def no_transfer(self, result):
        self.decision["result"] = result
        self.decision.pop("transfer", None)
        self.decision.pop("inventory", None)

    def add_review(self, level="fresh-context-same-model"):
        packet = self.run / "review-packet.md"
        packet.write_text("Ledger and evidence without the verdict; reviewer reply attached.\n", encoding="utf-8")
        self.ledger["review"] = {"level": level, "artifact": "review-packet.md",
                                 "sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
                                 "disconfirming": "Server may reject repeated request IDs.", "checked": True}

    def set_profile(self, profile, rubric=None):
        self.record["recipients"][0]["profile"] = profile
        self.record["routing"] = [{"profile": profile, "confidence": "high", "evidence": [f"User named {profile} as the recipient."], "explicit": True}]
        if rubric is not None:
            self.decision["score"]["rubric"] = rubric


class BaselineTests(Case):
    def test_upgraded_fixture_is_valid(self):
        self.assertValid()


class LadderLevelTests(Case):
    def test_every_claim_needs_a_ladder_level(self):
        del self.claims["c1"]["level"]
        self.assertRejected("level")
        self.claims["c1"]["level"] = "verified"
        self.assertRejected("level")

    def test_present_or_above_needs_read_evidence(self):
        self.record["claims"].append({"id": "c9", "subject": "s1", "text": "Inferred internal queue.", "kind": "mechanism", "status": "inferred",
                                      "confidence": "inferred", "scope": "docs", "limitations": "not read", "evidence": [], "level": "present"})
        self.assertRejected("c9", "read evidence")

    def test_stale_or_unvalidated_claim_stays_claimed(self):
        self.record["claims"].append({"id": "c9", "subject": "s1", "text": "Planned runtime check.", "kind": "experiment", "status": "unvalidated",
                                      "scope": "planned", "limitations": "not run", "evidence": [], "level": "wired"})
        self.assertRejected("c9", "claimed")
        self.record["claims"][-1]["level"] = "claimed"
        self.assertValid()

    def test_tested_level_needs_a_run_from_this_work(self):
        self.claims["c2"]["level"] = "tested"
        self.assertRejected("c2", "execution")
        self.claims["c2"]["execution"] = recipient_run(self.run, self.record)
        self.assertValid()

    def test_ladder_table_is_rendered_before_the_verdict(self):
        output = aa.render(self.record, self.run)
        self.assertIn("Evidence ladder", output)
        self.assertRegex(output, r"\| c1 \| s1 \| PRESENT \| supported \|")
        self.assertLess(output.index("Evidence ladder"), output.index("aa:verdict:q1"))
        self.assertTrue(aa.check_output(self.record, self.run, output))


class CapTests(Case):
    def test_high_confidence_on_an_inferred_claim_rejected(self):
        self.record["claims"].append({"id": "c9", "subject": "s1", "text": "Inferred benefit.", "kind": "mechanism", "status": "inferred",
                                      "confidence": "speculated", "scope": "x", "limitations": "x", "evidence": [], "level": "claimed"})
        self.decision["claims"].append("c9")
        self.decision["confidence_level"] = "high"
        self.assertRejected("confidence_level", "c9")
        self.decision["confidence_level"] = "medium"
        self.assertRejected("confidence_level", "c9")
        self.decision["confidence_level"] = "low"
        self.assertValid()

    def test_high_confidence_needs_a_tested_or_observed_claim(self):
        self.decision["confidence_level"] = "high"
        self.add_review()
        self.assertRejected("high", "TESTED or OBSERVED")
        self.claims["c1"]["level"] = "wired"
        self.claims["c2"]["level"] = "tested"
        self.claims["c2"]["execution"] = recipient_run(self.run, self.record)
        self.assertValid()

    def test_value_three_needs_a_recorded_run(self):
        self.decision["mechanism_value"] = 3
        self.assertRejected("mechanism_value 3")
        self.claims["c2"]["level"] = "tested"
        self.claims["c2"]["execution"] = recipient_run(self.run, self.record)
        self.assertValid()

    def test_value_two_needs_an_inspected_source_mechanism(self):
        self.claims["c1"]["level"] = "claimed"
        self.decision["confidence_level"] = "low"
        self.assertRejected("mechanism_value", "PRESENT")

    def test_inconclusive_is_low_confidence_and_names_what_is_missing(self):
        self.no_transfer("INCONCLUSIVE")
        self.decision["confidence_level"] = "high"
        self.assertRejected("INCONCLUSIVE", "low")
        self.decision["confidence_level"] = "low"
        self.ledger["doubt"]["unknowns"] = []
        self.assertRejected("INCONCLUSIVE", "unknowns")
        self.ledger["doubt"]["unknowns"] = ["Server contract"]
        self.assertValid()

    def test_already_covered_has_mechanism_value_zero(self):
        self.decision["result"] = "ALREADY-COVERED"
        self.decision["inventory"]["implemented"]["state"] = "present"
        self.decision["inventory"]["wired"]["state"] = "present"
        self.decision["mechanism_value"] = 3
        self.assertRejected("ALREADY-COVERED", "mechanism_value 0")
        self.decision["mechanism_value"] = 0
        self.assertValid()


class ProfileRubricRoutingTests(Case):
    def adopt(self, rubric, components):
        self.decision.update(result="ADOPT", whole_tool="ADOPT",
                             score={"rubric": rubric, "components": components, "penalty": 0, "total": sum(components), "rationale": "test"})
        self.add_review()

    def test_wrong_rubric_for_the_recipient_rejected(self):
        self.adopt("coding-workflow", [3, 2, 3, 2])
        self.assertRejected("rubric")
        self.adopt("self", [3, 3, 2, 2])
        self.assertRejected("rubric")
        self.adopt("generic", [3, 3, 2, 2])
        self.assertValid()

    def test_profile_with_its_own_rubric_needs_it(self):
        self.set_profile("coding-workflow", rubric="generic")
        self.assertRejected("rubric", "coding-workflow")
        self.decision["score"]["rubric"] = "coding-workflow"
        self.assertValid()
        self.decision["score"]["rubric"] = "tooling"  # legacy alias of the same rubric
        self.assertValid()

    def test_profiles_without_a_rubric_use_generic(self):
        for profile in ("frankenmine", "westack"):
            with self.subTest(profile=profile):
                self.set_profile(profile, rubric="generic")
                self.assertValid()
                self.decision["score"]["rubric"] = "coding-workflow"
                self.assertRejected("rubric")

    def test_every_recipient_with_a_verdict_needs_a_routing_row(self):
        del self.record["routing"]
        self.assertRejected("routing")
        self.set_profile("coding-workflow", rubric="coding-workflow")
        del self.record["routing"]
        self.assertRejected("routing")

    def test_unspecified_default_fails_until_a_profile_is_chosen(self):
        self.record["recipients"][0]["profile"] = "unspecified"
        del self.record["routing"]
        self.assertRejected("routing")
        self.record["routing"] = [{"profile": "unspecified", "confidence": "high", "evidence": ["No recipient named; opportunity mining."], "explicit": True}]
        self.assertRejected("unspecified")  # still an ADAPT: no target-specific result without a profile
        self.no_transfer("OPPORTUNITY")
        self.decision.update(mechanism_value=1, score=None, score_reason="No recipient: no fit score.")
        self.assertValid()

    def test_init_takes_id_equals_profile_and_defaults_to_unspecified(self):
        record = aa.init_run(self.root / "init-a", ["https://example.test/a"], ["app=coding-workflow", "other"])
        self.assertEqual([r["profile"] for r in record["recipients"]], ["coding-workflow", "unspecified"])
        with self.assertRaises(aa.Invalid):
            aa.init_run(self.root / "init-b", ["https://example.test/a"], ["app=not-installed-profile"])
        with self.assertRaises(aa.Invalid):
            aa.init_run(self.root / "init-c", ["https://example.test/a"], ["s1"])

    def test_cli_init_records_the_chosen_profile(self):
        run = self.root / "init-cli"
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "init", str(run), "--source", "https://example.test/a", "--recipient", "app=generic"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((run / "run.json").read_text(encoding="utf-8"))["recipients"][0]["profile"], "generic")

    def test_input_only_runs_still_report_status(self):
        record = aa.init_run(self.root / "queued", ["https://example.test/a"], ["app"])
        self.assertEqual(aa.record_status(record, self.root / "queued")["scope"], "inputs-only")


class VerdictHonestyTests(Case):
    def test_opportunity_needs_an_unspecified_recipient(self):
        self.no_transfer("OPPORTUNITY")
        self.decision["mechanism_value"] = 1
        self.assertRejected("OPPORTUNITY")
        self.decision["result"] = "DISCARD"
        self.decision["whole_tool"] = "OPPORTUNITY"
        self.assertRejected("OPPORTUNITY")

    def test_promising_label_only_on_value_one_discard(self):
        self.no_transfer("DISCARD")
        self.decision["mechanism_value"] = 1
        self.decision["promising_check"] = "Measure p95 latency of the send path before proposing a cache."
        self.assertValid()
        output = aa.render(self.record, self.run)
        self.assertIn("### DISCARD (promising: Measure p95 latency of the send path before proposing a cache.)", output)
        self.decision["mechanism_value"] = 2
        self.assertRejected("promising")
        self.decision["mechanism_value"] = 1
        self.decision["result"] = "INCONCLUSIVE"
        self.decision["confidence_level"] = "low"
        self.assertRejected("promising")

    def test_adapt_over_an_implemented_and_wired_capability_must_say_it_replaces_or_augments(self):
        self.decision["inventory"]["implemented"]["state"] = "present"
        self.decision["inventory"]["wired"]["state"] = "present"
        self.assertRejected("relation", "ALREADY-COVERED")
        self.decision["transfer"]["relation"] = "replaces"
        self.assertValid()

    def test_transfer_relation_and_seam_status_are_required(self):
        for key, bad in (("relation", "rewrites"), ("seam_status", "maybe")):
            with self.subTest(key=key):
                saved = self.decision["transfer"][key]
                self.decision["transfer"][key] = bad
                self.assertRejected(key)
                del self.decision["transfer"][key]
                self.assertRejected(key)
                self.decision["transfer"][key] = saved

    def test_refutation_target_placeholder_rejected(self):
        coverage = self.ledger["coverage"]
        for bad in ("-", "n/a", "x"):
            with self.subTest(bad=bad):
                coverage["refutation_targets"] = [bad]
                self.assertRejected("refutation")
        coverage["refutation_targets"] = [{"target": "Server rejects a repeated request ID", "outcome": "unknown"}]
        self.assertValid()
        coverage["refutation_targets"][0]["outcome"] = "maybe"
        self.assertRejected("refutation")

    def test_decision_tree_reaches_opportunity_before_inconclusive(self):
        tree = section(read("SKILL.md"), "```\nhard gate", "```")
        self.assertLess(tree.index("no recipient?"), tree.index("INCONCLUSIVE"))


class LegalTests(Case):
    def part(self, **fields):
        row = {"id": "p1", "part": "documented stable request-ID idea", "flag": "GREEN", "route": "idea-only",
               "basis": "Idea only; behaviour-level contract, no donor expression copied.", "patent_signal": "none", "terms_restriction": "none"}
        row.update(fields)
        return row

    def test_hard_line_hit_is_required(self):
        del self.legal["hard_line_hit"]
        self.assertRejected("hard_line_hit")

    def test_a_hard_line_blocks_every_part(self):
        self.legal.update(flag="RED", route="discard", escalate_to_lawyer=True, hard_line_hit=True, parts=[self.part()])
        self.decision["legal_part"] = "p1"
        self.assertRejected("hard line")
        self.legal["hard_line_hit"] = False
        self.assertValid()

    def test_patent_signal_on_every_reuse_route(self):
        del self.legal["patent_signal"]
        self.assertRejected("patent_signal")
        self.legal.update(patent_signal="hit", escalate_to_lawyer=False)
        self.assertRejected("patent")
        self.legal["escalate_to_lawyer"] = True
        self.assertRejected("GREEN")
        self.legal["flag"] = "YELLOW"
        self.assertValid()  # fixture result is ADAPT-with-prerequisite

    def test_discard_route_cannot_carry_a_transfer(self):
        self.legal.update(flag="GREEN", route="discard")
        self.decision["result"] = "ADAPT"
        self.assertRejected("discard")

    def test_legal_sources_need_a_url_and_iso_date(self):
        self.legal["sources"] = [{"title": "x", "url": "x", "accessed": "2026-10-09"}]
        self.assertRejected("url")
        self.legal["sources"] = [{"title": "x", "url": "https://example.test/terms", "accessed": "yesterday-ish"}]
        self.assertRejected("accessed")

    def test_owner_waiver_turns_an_unknown_licence_into_yellow_only(self):
        self.legal["flag"] = "UNKNOWN"
        self.assertRejected("RED/UNKNOWN")
        self.legal["waiver"] = {"by": "owner", "covers": "licence", "text": "I accept the unclear licence for an idea-level port.", "date": "2026-10-28"}
        self.assertValid()  # ADAPT-with-prerequisite under the effective YELLOW
        self.decision["result"] = "ADAPT"
        self.assertRejected("YELLOW")
        self.decision["result"] = "ADAPT-with-prerequisite"
        for key, bad in (("covers", "terms"), ("date", "today")):
            with self.subTest(key=key):
                saved = self.legal["waiver"][key]
                self.legal["waiver"][key] = bad
                self.assertRejected("waiver")
                self.legal["waiver"][key] = saved
        self.legal["flag"] = "GREEN"
        self.assertRejected("waiver")

    def test_reference_resolves_no_licence_and_idea_rungs(self):
        legal = read("references/legal.md")
        unknown_row = next(line for line in legal.splitlines() if line.startswith("| **UNKNOWN**"))
        self.assertNotIn("no LICENSE", unknown_row)
        self.assertRegex(legal, r"No LICENSE[^\n]*code or text reuse[^\n]*RED")
        self.assertIn("Idea-only transfers start at rung 2", legal)
        self.assertIn("without assent", legal)
        self.assertIn("every reuse route", legal)
        self.assertIn("waiver", legal)


class ReviewTests(Case):
    def test_ordinary_plan_needs_no_independent_review(self):
        self.assertNotIn("review", self.ledger)
        self.assertValid()

    def needs_review_above_self(self):
        self.assertRejected("independent review")
        self.add_review(level="self")
        self.assertRejected("independent review", "self")
        self.add_review()
        self.assertValid()

    def test_consequential_decision_needs_review_above_self(self):
        self.ledger["doubt"]["consequential"] = True
        self.needs_review_above_self()

    def test_governed_or_frozen_seam_needs_review_above_self(self):
        self.decision["transfer"]["seam_status"] = "governed"
        self.needs_review_above_self()

    def test_review_artifact_hash_must_match(self):
        self.ledger["doubt"]["consequential"] = True
        self.add_review()
        self.ledger["review"]["sha256"] = "0" * 64
        self.assertRejected("review")
        self.add_review(level="vibes")
        self.assertRejected("review")

    def test_review_renders_in_the_ledger(self):
        self.ledger["doubt"]["consequential"] = True
        self.add_review()
        output = aa.render(self.record, self.run)
        self.assertIn("REVIEW: fresh-context-same-model", output)
        self.assertLess(output.index("REVIEW:"), output.index("aa:verdict:q1"))


class OutcomeTests(Case):
    def setUp(self):
        super().setUp()
        self.path = self.run / "run.json"
        aa.save(self.path, self.record)
        self.receipt = self.root / "acceptance.txt"
        self.receipt.write_text("1 passed; broken copy failed as expected\n", encoding="utf-8")
        self.outcomes = self.root / "outcomes.jsonl"

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "outcome", str(self.path), "--ledger", str(self.outcomes), *args], capture_output=True, text=True)

    def test_outcome_is_appended_next_to_the_original_verdict(self):
        self.outcomes.write_text("not json and never read\n", encoding="utf-8")
        result = self.cli("--item", "q1", "--result", "passed", "--receipt", str(self.receipt))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.outcomes.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "not json and never read")
        event = json.loads(lines[1])
        self.assertEqual((event["kind"], event["item"], event["result"], event["mechanism_value"], event["confidence_level"], event["outcome"]),
                         ("outcome", "q1", "ADAPT-with-prerequisite", 2, "medium", "passed"))
        self.assertEqual(event["receipt"]["sha256"], hashlib.sha256(self.receipt.read_bytes()).hexdigest())
        self.assertEqual(event["acceptance_test"], self.decision["transfer"]["verification"])

    def test_outcome_needs_a_receipt_or_a_reason_and_a_transfer_item(self):
        self.assertEqual(self.cli("--item", "q1", "--result", "passed").returncode, 2)
        self.assertEqual(self.cli("--item", "q1", "--result", "blocked").returncode, 2)
        self.assertEqual(self.cli("--item", "q1", "--result", "blocked", "--reason", "Server sandbox unavailable").returncode, 0)
        self.assertEqual(self.cli("--item", "q9", "--result", "not-run", "--reason", "x").returncode, 2)
        self.no_transfer("DISCARD")
        aa.save(self.path, self.record)
        self.assertEqual(self.cli("--item", "q1", "--result", "not-run", "--reason", "x").returncode, 2)

    def test_outcome_executes_nothing(self):
        with mock.patch.object(aa.subprocess, "run", side_effect=AssertionError("outcome must not execute")):
            aa.append_outcome(self.path, "q1", "passed", self.outcomes, receipt=self.receipt)
        self.assertEqual(json.loads(self.outcomes.read_text(encoding="utf-8"))["outcome"], "passed")


class RoutingIndexTests(unittest.TestCase):
    def test_index_is_generated_from_every_profile_section(self):
        index = aa.routing_index()
        for path in sorted((ROOT / "references" / "profiles").glob("*.md")):
            body = re.search(r"^## Routing signals[^\n]*\n(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
            self.assertIsNotNone(body, path.name)
            self.assertIn(body.group(1).strip(), index, path.name)
            self.assertIn(f"profiles/{path.name}", index)

    def test_index_is_small(self):
        self.assertLessEqual(len(re.findall(r"\S+", aa.routing_index())), 700)

    def test_routing_reads_the_index_not_every_profile(self):
        routing = read("references/routing.md")
        self.assertIn('aa.py" routing-index', routing)
        self.assertNotIn("read every installed profile", routing)
        self.assertIn("routing-index", section(read("SKILL.md"), "## 1.", "### Bounded"))

    def test_cli_prints_the_index(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "routing-index"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode("utf-8").replace("\r\n", "\n"), aa.routing_index())


class DocumentTests(unittest.TestCase):
    def test_bounded_template_is_shipped_and_linked(self):
        template = read("references/bounded-ledger-template.md")
        for field in ("ROUTING:", "Refutation targets", "Evidence ladder", "LEGAL:", "VERDICT:", "promising"):
            self.assertIn(field, template)
        self.assertIn("(references/bounded-ledger-template.md)", section(read("SKILL.md"), "### Bounded mechanism review", "## 2."))
        package = read("scripts/package.py")
        self.assertIn('"references/bounded-ledger-template.md"', package)

    def test_need_definition_and_promising_label(self):
        numbers = section(read("SKILL.md"), "## 4.", "## 5.")
        self.assertIn("observed symptom or a stated requirement", numbers)
        self.assertIn("DISCARD (promising: <check to run>)", read("SKILL.md"))
        self.assertIn("DISCARD (promising: <check to run>)", read("references/output-template.md"))

    def test_map_prefers_sources_the_donor_cannot_steer(self):
        acquire = section(read("SKILL.md"), "## 2.", "## 3.")
        self.assertNotIn("CodeWiki → DeepWiki → self-built", acquire)
        self.assertIn("donor can't steer", acquire)

    def test_full_route_skips_package_checks_for_a_hard_gate_discard(self):
        gates = section(read("SKILL.md"), "## 3.", "## 4.")
        self.assertIn("hard gate", gates)
        self.assertIn("Scorecard", gates)
        self.assertRegex(gates, r"Skip Scorecard, OSV, maintenance and the fit score")

    def test_per_mechanism_workaround_is_documented(self):
        records = read("references/records.md")
        self.assertIn("#mechanism-", records)
        self.assertIn("per-mechanism decisions", read("CHANGES.md"))

    def test_review_is_proportionate(self):
        doubt = section(read("SKILL.md"), "## 7.", "## 8.")
        for trigger in ("ADOPT", "governed", "consequential", "high confidence"):
            self.assertIn(trigger, doubt)


if __name__ == "__main__":
    unittest.main()
