"""r16 candidate, round 3 after the second blind comparison (2026-10-29): checks stay inside the write scope,
claims of work match the work done, and a rejected donor's salvage is complete.

The second comparison found a run that wrote a check script into the host's scratchpad, outside the folder the
user named, and then tried to run it; a report that described a search no tool call made and cited a rules file
by rule number as if by line; and a salvage that kept the first clean part of a rejected donor and declined its
siblings. These checks pin the instructions that answer them. Each check returns what is missing, and a
broken-copy control shows that each check fails once its rule is removed. They test wording, not behaviour;
behaviour needs a fresh blind campaign on unseen cases."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BODY = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


WRITE_RULE = ("scratchpad and temp folders count as outside", "Any check you run is inline", "`node -e`",
              "`python -c`", "literal paths", "only inside the named output folder", "mark the claim untested",
              "never write or run elsewhere to get round a denial")
HONESTY_RULE = ("A claimed search, run or read needs the matching tool call in this session",
                "else say it was not done", "check each citation against the file as read", "never from memory")
SALVAGE_RULE = ("every separable part that passed the screen", "a line each", "not just the first found")


def missing_write_rule(body):
    """The write-scope rule, read where it is recorded at the start of a run (§1, before the quick call)."""
    start = section(body, "## 1.", "### Quick call")
    return [phrase for phrase in WRITE_RULE if phrase not in start]


def missing_honesty_rule(body):
    """Claims of work are bound to this session's tool calls; citations come from the file as read (§8)."""
    publish = section(body, "## 8.", "## 9.")
    return [phrase for phrase in HONESTY_RULE if phrase not in publish]


def missing_salvage_rule(body):
    """DISCARD's salvage covers every separable clean part, briefly, and nothing narrows it to one."""
    results = next(line for line in body.splitlines() if line.startswith("Results "))
    discard = results.split("**DISCARD**", 1)[1].split("·", 1)[0]
    missing = [phrase for phrase in SALVAGE_RULE if phrase not in discard]
    if "best salvage" in body:
        missing.append("no 'best salvage' narrowing")
    return missing


class WriteScopeTests(unittest.TestCase):
    def test_checks_run_inline_and_never_outside_the_named_folder(self):
        self.assertEqual(missing_write_rule(BODY), [])

    def test_the_rule_sits_with_the_write_scope(self):
        start = section(BODY, "## 1.", "### Quick call")
        self.assertLess(start.index("**write scope**"), start.index("scratchpad and temp folders count as outside"))
        self.assertLess(start.index("scratchpad and temp folders count as outside"), start.index("What the user states"))


class EvidenceHonestyTests(unittest.TestCase):
    def test_claims_of_work_need_their_tool_call_and_citations_their_file(self):
        self.assertEqual(missing_honesty_rule(BODY), [])


class SalvageCompletenessTests(unittest.TestCase):
    def test_discard_salvage_names_every_separable_clean_part(self):
        self.assertEqual(missing_salvage_rule(BODY), [])


class BrokenCopyControls(unittest.TestCase):
    """Each check must fail on a copy of SKILL.md with only its own rule removed."""

    def broken(self, pattern, replacement=""):
        copy, count = re.subn(pattern, replacement, BODY, count=1, flags=re.S)
        self.assertEqual(count, 1, f"control could not break the copy: {pattern}")
        return copy

    def test_write_check_fails_without_the_inline_rule(self):
        copy = self.broken(r" Any check you run is inline.*?get round a denial\.")
        self.assertTrue(missing_write_rule(copy))
        self.assertEqual(missing_honesty_rule(copy), [])  # the control breaks one rule only

    def test_write_check_fails_without_the_scratchpad_clause(self):
        copy = self.broken(r" \(the host's scratchpad and temp folders count as outside\)")
        self.assertEqual(missing_write_rule(copy), ["scratchpad and temp folders count as outside"])

    def test_honesty_check_fails_without_the_rule(self):
        copy = self.broken(r" A claimed search, run or read.*?never from memory\.")
        self.assertTrue(missing_honesty_rule(copy))
        self.assertEqual(missing_write_rule(copy), [])

    def test_salvage_check_fails_on_the_narrowing_wording(self):
        copy = self.broken(r"\*\*DISCARD\*\* \([^)]*\)", "**DISCARD** (with the best salvage noted, if any)")
        self.assertEqual(set(missing_salvage_rule(copy)), {*SALVAGE_RULE, "no 'best salvage' narrowing"})


if __name__ == "__main__":
    unittest.main()
