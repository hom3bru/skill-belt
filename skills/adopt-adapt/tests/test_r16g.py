"""r16.1 candidate (2026-10-31): each artifact that a source bundles, wraps, ports or cites gets its own identity.

Reviewing a shared bot that ships some of another author's plugin skills beside skills of its own, an assessment
nearly credited the bot's own skills to the plugin and treated the plugin's author's other tools, a third-party
port and a directory listing as the same source. The owner's correction is recorded as a due-diligence rule that
sits with the pinning rule, so it binds idea-only transfers too. Each check returns what is missing, and a
broken-copy control shows that each check fails once its rule is removed or moved. They test wording, not
behaviour; behaviour needs a fresh blind campaign on unseen cases."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "references/due-diligence.md").read_text(encoding="utf-8")

IDENTITY_RULE = ("Name each artifact on its own", "bundles, wraps, ports or cites another tool",
                 "its own source, pin and licence", "credit none with another's parts",
                 "A port or directory listing is not the original")
RULE_TEXT = r" Name each artifact on its own\..*?is not the original\."


def opening(text):
    """The block's opening rules, which bind every route, before the check table."""
    return text.split("| Check |", 1)[0]


def missing_identity_rule(text):
    head = opening(text)
    return [phrase for phrase in IDENTITY_RULE if phrase not in head]


class SourceIdentityTests(unittest.TestCase):
    def test_each_artifact_gets_its_own_identity(self):
        self.assertEqual(missing_identity_rule(PAGE), [])

    def test_the_rule_sits_with_pinning_and_holds_for_idea_only_transfers(self):
        head = opening(PAGE)
        self.assertLess(head.index("Pin everything to the commit SHA you read"), head.index("Name each artifact on its own"))
        self.assertIn("Licence and source identity are still checked", head)


class BrokenCopyControls(unittest.TestCase):
    """Each control breaks one thing in a copy of the page and shows the check notices."""

    def broken(self, pattern, replacement=""):
        copy, count = re.subn(pattern, replacement, PAGE, count=1, flags=re.S)
        self.assertEqual(count, 1, f"control could not break the copy: {pattern}")
        return copy

    def test_check_fails_without_the_rule(self):
        self.assertEqual(missing_identity_rule(self.broken(RULE_TEXT)), list(IDENTITY_RULE))

    def test_check_fails_when_a_port_may_count_as_the_original(self):
        copy = self.broken(r" A port or directory listing is not the original\.")
        self.assertEqual(missing_identity_rule(copy), ["A port or directory listing is not the original"])

    def test_check_fails_when_the_rule_moves_below_the_check_table(self):
        rule = re.search(RULE_TEXT, PAGE, re.S).group(0)
        copy = PAGE.replace(rule, "", 1) + "\n" + rule.strip() + "\n"
        self.assertEqual(missing_identity_rule(copy), list(IDENTITY_RULE))


if __name__ == "__main__":
    unittest.main()
