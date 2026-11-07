"""The review report is the contract behind four text rules, so its shape is pinned here (the rest of those rules
is wording a model follows, which a test cannot see):

  SS-01  a drop is a record (claim, reason, deciding evidence), not a count
  SS-02  a candidate whose validator did not run is listed apart: not a finding, not a drop, and no all-clear
  SS-03  identity is the root cause, never the line, and the settled list never reaches a fresh reviewer (SS-04)
  EV-60  a reviewer's status is listed, and a silent one is not-run, never zero findings

Run: python -B -m unittest discover -s skills/westack-review/tests -v
Each check also runs on a copy of the text with the rule taken out, and must fail there.
"""
import pathlib
import re
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
SKILL_TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
RULES_TEXT = (SKILL / "references" / "rules.md").read_text(encoding="utf-8")
# alpha.34 (lean start pages): rule 6, with EV-60's reviewer wording, moved to references/every-mode.md unchanged
EVERY_MODE_TEXT = (SKILL / "references" / "every-mode.md").read_text(encoding="utf-8")


def report_lines(skill_text):
    block = re.search(r"```text\n(Scope:.*?)```", skill_text, re.S)
    if not block:
        raise AssertionError("the report template is missing from SKILL.md")
    return block.group(1).splitlines()


def check_report(skill_text):
    lines = report_lines(skill_text)
    heads = [line.split(":", 1)[0] for line in lines if re.match(r"[A-Z][A-Za-z ]+:", line)]
    for wanted in ("Dropped at validation", "Not validated", "Reviewers", "Not assessed", "Verdict"):
        assert wanted in heads, wanted + " is missing from the report: " + str(heads)
    assert heads.index("Dropped at validation") < heads.index("Not validated") < heads.index("Reviewers") \
        < heads.index("Not assessed") < heads.index("Verdict"), heads
    dropped = next(line for line in lines if line.startswith("Dropped at validation"))
    assert "claim" in dropped and "evidence" in dropped, "a drop is a record, not a count: " + dropped
    assert not re.search(r"Dropped at validation:\s*n\b", dropped), "a bare count: " + dropped
    flat = " ".join(skill_text.split())
    assert "never a finding, never a drop, and no all-clear" in flat, "a validator that did not run"
    assert "never deletes deterministic tool output" in flat
    assert "retried once, then not-run, never zero findings" in " ".join(EVERY_MODE_TEXT.split())
    assert "not passed or all-clear while any candidate is not validated or a required reviewer is not-run" in flat


def check_rules(rules_text):
    flat = " ".join(rules_text.split())
    assert "never a line number" in flat, "identity is the root cause"
    assert "Merge duplicates on that identity before spending validators" in flat
    assert "Never hand the settled list to a fresh reviewer" in flat
    assert "never count it as dropped or clean" in flat
    assert re.search(r"In a recorded task[^.]*`introduced`[^.]*`trigger`", flat), "the contract-field sentence stays"


class ReportContractTests(unittest.TestCase):
    def test_the_report_lists_drops_apart_from_the_candidates_that_were_not_validated(self):
        check_report(SKILL_TEXT)

    def test_a_count_only_report_fails_the_same_check(self):
        old = "Dropped at validation: n (by exclusion reason)"
        counted = re.sub(r"Dropped at validation:.*", old, SKILL_TEXT, count=1)
        with self.assertRaises(AssertionError):
            check_report(counted)

    def test_a_report_without_the_not_validated_line_fails_the_same_check(self):
        without = re.sub(r"Not validated:.*\n", "", SKILL_TEXT, count=1)
        with self.assertRaises(AssertionError):
            check_report(without)

    def test_a_report_without_reviewer_status_fails_the_same_check(self):
        without = re.sub(r"Reviewers:.*\n", "", SKILL_TEXT, count=1)
        with self.assertRaises(AssertionError):
            check_report(without)

    def test_the_rules_name_root_cause_identity_and_keep_the_settled_list_from_a_fresh_reviewer(self):
        check_rules(RULES_TEXT)

    def test_rules_without_the_settled_list_rule_fail_the_same_check(self):
        with self.assertRaises(AssertionError):
            check_rules(RULES_TEXT.replace("Never hand the settled list to a fresh reviewer.", ""))
        with self.assertRaises(AssertionError):
            check_rules(RULES_TEXT.replace("never a line number", "a line number"))


if __name__ == "__main__":
    unittest.main()
