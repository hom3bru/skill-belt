"""r16.2 candidate (2026-10-31): a GitHub 404 is recorded as "not found or not visible", never as absence.

GitHub answers 404, not 403, when a caller cannot see a private resource, so that the resource's existence is not
confirmed (GitHub REST troubleshooting page, "404 Not Found for an existing resource"). An assessment that writes
"does not exist" from a 404 can wrongly rule out a private original. The rule sits with the pinning and identity
rules, so it binds idea-only transfers too. It names GitHub on purpose: the registry-existence row, where a 404
from a public registry is the slopsquatting signal, is unchanged. Each check returns what is missing, and a
broken-copy control shows that each check fails once its rule is removed, cut, moved or widened. They test
wording, not behaviour; behaviour needs a fresh blind campaign on unseen cases."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "references/due-diligence.md").read_text(encoding="utf-8")

NOT_FOUND_RULE = ("Record a GitHub 404 as", '"not found or not visible to this account"',
                  "GitHub answers 404, not 403, for private resources a caller cannot see",
                  'Never write "does not exist" from a 404')
RULE_TEXT = r" Record a GitHub 404 as .*?from a 404\."
REGISTRY_ROW = "404 means the plan names a package that does not exist"


def opening(text):
    """The block's opening rules, which bind every route, before the check table."""
    return text.split("| Check |", 1)[0]


def missing_not_found_rule(text):
    head = opening(text)
    return [phrase for phrase in NOT_FOUND_RULE if phrase not in head]


class GitHubNotFoundTests(unittest.TestCase):
    def test_a_github_404_is_not_absence(self):
        self.assertEqual(missing_not_found_rule(PAGE), [])

    def test_the_rule_follows_pinning_and_identity(self):
        head = opening(PAGE)
        self.assertLess(head.index("Name each artifact on its own"), head.index("Record a GitHub 404 as"))

    def test_the_registry_row_keeps_its_own_404_meaning(self):
        self.assertIn(REGISTRY_ROW, PAGE.split("| Check |", 1)[1])


class BrokenCopyControls(unittest.TestCase):
    """Each control breaks one thing in a copy of the page and shows the check notices."""

    def broken(self, pattern, replacement=""):
        copy, count = re.subn(pattern, replacement, PAGE, count=1, flags=re.S)
        self.assertEqual(count, 1, f"control could not break the copy: {pattern}")
        return copy

    def test_check_fails_without_the_rule(self):
        self.assertEqual(missing_not_found_rule(self.broken(RULE_TEXT)), list(NOT_FOUND_RULE))

    def test_check_fails_when_absence_may_be_written(self):
        copy = self.broken(r' Never write "does not exist" from a 404\.')
        self.assertEqual(missing_not_found_rule(copy), ['Never write "does not exist" from a 404'])

    def test_check_fails_when_the_rule_moves_below_the_check_table(self):
        rule = re.search(RULE_TEXT, PAGE, re.S).group(0)
        copy = PAGE.replace(rule, "", 1) + "\n" + rule.strip() + "\n"
        self.assertEqual(missing_not_found_rule(copy), list(NOT_FOUND_RULE))

    def test_check_fails_when_the_rule_is_widened_to_every_404(self):
        copy = self.broken(r"Record a GitHub 404 as", "Record a 404 as")
        self.assertEqual(missing_not_found_rule(copy), ["Record a GitHub 404 as"])


if __name__ == "__main__":
    unittest.main()
