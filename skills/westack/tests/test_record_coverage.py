"""Record-side coverage items, all optional and additive to schema 1: observations (ruled-out
hypotheses, confirmations and surprises), human-only acceptance criteria and the resume check."""
import copy
import re
import unittest

import test_westack as fixtures
from test_round2 import Records, sha, write

v = fixtures.v
ROOT = fixtures.ROOT


class ObservationTests(Records):
    def observe(self, **changes):
        item = dict(id="o1", kind="ruled-out", text="Not the cache: a cold run fails the same way", evidence_ids=["e1"])
        item.update(changes)
        self.task.setdefault("observations", []).append(item)
        return item

    def test_old_records_need_no_observations(self):
        self.assertNotIn("observations", self.task)
        self.assertEqual(self.errors(), [])

    def test_ruled_out_with_evidence_is_valid(self):
        self.observe()
        self.observe(id="o2", kind="surprise", text="The suite was already red on main", evidence_ids=[])
        self.assertEqual(self.errors(), [])

    def test_elimination_cites_its_evidence(self):
        self.observe(evidence_ids=[])
        self.assertError("o1: a ruled-out observation cites the evidence behind it")
        self.task["observations"][0].update(kind="confirmed")
        self.assertError("o1: a confirmed observation cites the evidence behind it")

    def test_unknown_evidence_kind_and_duplicates(self):
        self.observe(evidence_ids=["e9"])
        self.assertError("o1: unknown evidence e9")
        self.task["observations"] = []
        self.observe(kind="guess")
        self.assertError("value outside enum")
        self.task["observations"] = []
        self.observe()
        self.observe()
        self.assertError("duplicate IDs in observations")

    def test_observations_are_append_only(self):
        self.in_progress()
        self.observe()
        previous = copy.deepcopy(self.task)
        self.task["observations"] = []
        self.assertError("observation removed: o1", previous=previous)
        self.observe(text="Actually the cache after all")
        self.assertError("observation rewritten: o1", previous=previous)


class HumanVerifierTests(Records):
    def setUp(self):
        super().setUp()
        write(self.root, {"review.txt": "Maria checked the printed invoice layout by eye.\n"})
        self.task["evidence"].append(dict(self.task["evidence"][0], id="rev-e", claim_id="rev1",
                                          claim_ids=["rev1", "a1"], type="review", raw_output="review.txt",
                                          raw_sha256=sha(self.root / "review.txt"), exit_code=None,
                                          expected_exit=None, operation="human check of the invoice layout"))
        self.review = dict(id="rev1", author_id=self.task["author_id"], reviewer_id="maria", context_id="person",
                           patch_id=self.task["patch_id"], kind="independent", status="completed",
                           evidence_ids=["rev-e"], finding_ids=[], level="human")
        self.task["acceptance"][0]["verifier"] = "human"

    def test_agent_receipts_cannot_pass_a_human_criterion(self):
        self.assertError("a1: a human-verified criterion needs a passing review receipt from a completed human review")

    def test_completed_human_review_passes_it(self):
        self.task["reviews"] = [self.review]
        self.task["acceptance"][0]["evidence_ids"] = ["e1", "rev-e"]
        self.assertEqual(self.errors(), [])

    def test_a_non_human_review_level_does_not(self):
        self.review["level"] = "different-model"
        self.task["reviews"] = [self.review]
        self.task["acceptance"][0]["evidence_ids"] = ["e1", "rev-e"]
        self.assertError("a1: a human-verified criterion needs")

    def test_open_human_criterion_blocks_completion(self):
        self.task["acceptance"][0]["status"] = "not-run"
        self.assertError("required acceptance incomplete")

    def test_verifier_cannot_relax_within_a_scope(self):
        self.task["reviews"] = [self.review]
        self.task["acceptance"][0]["evidence_ids"] = ["e1", "rev-e"]
        self.in_progress()
        previous = copy.deepcopy(self.task)
        del self.task["acceptance"][0]["verifier"]
        self.assertError("acceptance a1 verifier cannot move from human to agent", previous=previous)

    def test_verifier_values(self):
        self.task["acceptance"][0]["verifier"] = "robot"
        self.assertError("value outside enum")


class ResumeCheckTests(Records):
    def test_names_a_required_criterion(self):
        self.task["resume_check"] = "a1"
        self.assertEqual(self.errors(), [])
        self.task["resume_check"] = "zz"
        self.assertError("resume_check must name a required acceptance criterion: zz")
        self.task["resume_check"] = "a1"
        self.task["acceptance"][0]["required"] = False
        self.assertError("resume_check must name a required acceptance criterion: a1")


class FindingProvenanceTests(Records):
    """Optional finding fields from the review skill: where the defect entered (`introduced`) and the input
    that makes it fail (`trigger`). Additive to schema 1: a finding without them is still valid."""

    def finding(self, **changes):
        item = dict(id="f1", claim="Pager drops the last page", location="pager.py:12", consequence="a user loses a row",
                    evidence_ids=["e1"], severity="high", severity_rationale="plausible trigger on the main path",
                    correction="use <= in the page bound", adjudication="rejected", rationale="the author confirmed it is intended",
                    verification_ids=[])
        item.update(changes)
        self.task["findings"] = [item]
        return item

    def test_existing_findings_need_neither_field(self):
        self.finding()
        self.assertEqual(self.errors(), [])
        required = v.CONTRACT["$defs"]["finding"]["required"]
        self.assertNotIn("introduced", required)
        self.assertNotIn("trigger", required)

    def test_both_fields_validate(self):
        for origin in ("patch", "affected-elsewhere", "pre-existing", "unknown"):
            with self.subTest(introduced=origin):
                self.finding(introduced=origin, trigger="page_size=10 with 20 rows -> 19 rows returned (traced pager.py:12)")
                self.assertEqual(self.errors(), [])
        self.finding(introduced="patch")
        self.assertEqual(self.errors(), [])
        self.finding(trigger="empty input -> IndexError (executed, receipt e1)")
        self.assertEqual(self.errors(), [])

    def test_bad_values_are_rejected(self):
        self.finding(introduced="sometime")
        self.assertError("findings[0].introduced: value outside enum")
        self.finding(trigger="")
        self.assertError("findings[0].trigger: empty string")
        self.finding(trigger=3)
        self.assertError("findings[0].trigger: expected string")
        self.finding(origin="patch")
        self.assertError("findings[0]: unknown key origin")

    def test_adjudication_still_moves_only_forward_with_the_new_fields(self):
        self.in_progress()
        self.finding(adjudication="open", introduced="patch", trigger="t")
        previous = copy.deepcopy(self.task)
        self.task["findings"][0]["adjudication"] = "accepted"
        self.assertEqual(self.errors(previous=previous), [])


class ContractDocsTests(unittest.TestCase):
    def test_field_table_lists_the_finding_fields(self):
        text = (ROOT / "contracts/README.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"\| finding \|[^\n]*\| introduced \(patch/affected-elsewhere/pre-existing/unknown\), trigger(, waived_patch_id)? \|")
        self.assertIn("`findings[].introduced`", text)

    def test_field_table_lists_the_new_fields(self):
        text = (ROOT / "contracts/README.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"\| observation \| id, kind \(ruled-out/confirmed/surprise(/follow-up/memory-read)?\), text, evidence_ids \|")
        self.assertRegex(text, r"\| acceptance \|[^\n]*\| verifier \(agent/human\) \|")
        self.assertRegex(text, r"\| task \|[^\n]*\| [^\n]*observations[^\n]*resume_check")


if __name__ == "__main__":
    unittest.main()
