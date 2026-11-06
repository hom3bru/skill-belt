"""P2 adoption, memory group (1.0.0-alpha.5, unreleased).

These are text rules on five core references (memory, context, critique, craft, learn). westack ships no memory
store, instruction loader or reviewer launcher, so there is no behaviour of their own to run; the tests pin what the
pages must keep saying. Each pin also runs against a copy of the page with the rule's phrase taken out, and that copy
must fail, or the pin protects nothing. The same is done for the size cap and the line endings.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CASES = {
    "references/memory.md": {
        "CM-56": ["Read the host's memory once at task start", "later saves are outside that snapshot"],
        "CM-48": ["a gate that can refuse", "\"already known\" names the note and section", "never blocks the task"],
        "CM-55": ["only once written and read back", "separate delivery state needing its own grant"],
        "EV-59": ["full, degraded, failed, skipped", "what it covers"],
    },
    "references/context.md": {
        "CM-05": ["estimating only what came after it", "unknown, never zero or full"],
        "CM-13": ["source file", "where user rules end and project rules begin", "never probe a path"],
        "CM-14": ["an unparseable header means always on, never off"],
    },
    "references/critique.md": {
        "EV-61": ["inputs it actually read", "non-error tool result", "means not-run, never zero findings"],
        "HD-24": ["with the tool missing", "never a quiet same-model run", "unchanged, as data"],
        "SS-07": ["reviewing model and vendor", "fresh-context-same-model at best", "not-run, never approval"],
    },
    "references/craft.md": {
        "WA-80": ["reuse ladder", "first rung that fully works", "Never subtract trust-boundary validation",
                  "data-loss handling"],
        "GS-26": ["against live state", "ids from the event not model text", "argument vector, never a shell"],
    },
    "references/learn.md": {
        "GS-12": ["\"Unverified\"", "do not act on it"],
        "CM-50": ["standing advice", "tool-is-broken claim", "a rule plus why"],
    },
}

# Word counts of the five pages before this group; the group may add at most 20 percent to each.
BASELINE = {"references/memory.md": 417, "references/context.md": 316, "references/critique.md": 373,
            "references/craft.md": 348, "references/learn.md": 288}

APPLIED = ("CM-56", "CM-48", "CM-55", "EV-59", "CM-05", "CM-13", "CM-14", "EV-61", "HD-24", "SS-07", "WA-80",
           "GS-26", "GS-12", "CM-50")
HEADING = "## 1.0.0-alpha.5 (P2 adoption), unreleased"
TOUCHED = tuple(CASES) + ("tests/test_p2_memory.py",)


def text(relative):
    return (ROOT / relative).read_bytes().decode("utf-8")


def flat(relative):
    return re.sub(r"\s+", " ", text(relative))


def gaps(body, phrases):
    """The phrases a page no longer says."""
    return [phrase for phrase in phrases if phrase not in body]


def over_cap(body, baseline):
    return len(body.split()) > baseline * 1.2


class GateWordingTests(unittest.TestCase):
    def test_each_rule_keeps_its_gate_words(self):
        for relative, items in CASES.items():
            body = flat(relative)
            for item, phrases in items.items():
                with self.subTest(page=relative, item=item):
                    self.assertEqual(gaps(body, phrases), [])

    def test_control_a_page_with_the_phrase_taken_out_fails_the_pin(self):
        for relative, items in CASES.items():
            body = flat(relative)
            for item, phrases in items.items():
                for phrase in phrases:
                    with self.subTest(page=relative, item=item, phrase=phrase):
                        self.assertEqual(gaps(body.replace(phrase, ""), [phrase]), [phrase])

    def test_the_cases_cover_every_applied_item(self):
        pinned = {item for items in CASES.values() for item in items}
        self.assertEqual(pinned, set(APPLIED))


class SizeTests(unittest.TestCase):
    def test_each_page_stays_within_twenty_percent_of_its_earlier_size(self):
        for relative, baseline in BASELINE.items():
            with self.subTest(page=relative):
                self.assertFalse(over_cap(text(relative), baseline), len(text(relative).split()))

    def test_control_a_padded_copy_fails_the_cap(self):
        for relative, baseline in BASELINE.items():
            with self.subTest(page=relative):
                self.assertTrue(over_cap(text(relative) + " word" * baseline, baseline))


class ChangelogAndLineEndingTests(unittest.TestCase):
    def test_the_changelog_cites_every_applied_item_under_the_new_section(self):
        body = text("CHANGELOG.md")
        self.assertIn(HEADING, body)
        mine = body.split(HEADING)[1].split("\n## ")[0]
        for item in APPLIED:
            with self.subTest(item=item):
                self.assertIn("P2 (" + item + "):", mine)

    def test_touched_pages_are_lf_only(self):
        for relative in TOUCHED:
            with self.subTest(file=relative):
                self.assertNotIn(b"\r", (ROOT / relative).read_bytes())

    def test_the_changelog_keeps_one_line_ending_throughout(self):
        # CHANGELOG.md is CRLF; an edit must not leave it mixed.
        data = (ROOT / "CHANGELOG.md").read_bytes()
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        self.assertIn(crlf, (0, lf), "mixed line endings: %d CRLF of %d lines" % (crlf, lf))

    def test_control_a_changelog_with_a_bare_lf_is_caught(self):
        data = (ROOT / "CHANGELOG.md").read_bytes().replace(b"\r\n", b"\n", 1)
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        self.assertNotIn(crlf, (0, lf))


if __name__ == "__main__":
    unittest.main()
