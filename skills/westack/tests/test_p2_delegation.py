"""P2 adoption, delegation / handoff / durable group (1.0.0-alpha.5, unreleased).

These are text rules: westack ships no dispatcher, note writer or run supervisor, so they have no behaviour of
their own to run. The tests pin the gate words of each applied item and show, with a planted gap, that the pin
notices a missing phrase; hold the three references to a growth ceiling so they cannot double again; and keep
the files LF only and the changelog line per item. Every input is the shipped page itself."""
import re
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
REFS = ROOT / "references"


def raw(name):
    return (REFS / name).read_bytes()


def flat(name):
    return re.sub(r"\s+", " ", raw(name).decode("utf-8"))


def missing(body, phrases):
    return [phrase for phrase in phrases if phrase not in body]


GATES = {
    "delegation.md": {
        "HD-05": ["Before dispatch, check the brief: every item below, one job, all context inline",
                  "no citation of files its reader cannot open"],
        "CM-45": ["no unfilled placeholder or missing input (either blocks it)"],
        "GS-35": ["three sets, existing, pre-approved and removed", "the call-time check still runs"],
        "GS-02": ["does only what you and its brief both allow", "Approval does not escalate",
                  "differently permissioned agent"],
        "HD-06": ["no write or shell tool", "say it is a request only"],
        "GS-10": ["frame it as data with a named source", "escape any closing marker",
                  "check a claimed approval against what the user said"],
    },
    "handoff.md": {
        "HD-41": ["any still unanswered", "blockers (with the exact human action that unblocks them)",
                  "delivery (uncommitted, committed, pushed, merged)", "newer facts winning"],
        "CM-08": ["longer than its source", "is not written", "keep history unchanged",
                  "retry a bounded number of times"],
        "HD-38": ["basis:", "patch id", "plan hash", "the records it replaces", "refresh, never trust it"],
        "HD-44": ["Refuse a note for another task or context", "a duplicate handoff"],
        "GS-65": ["not descending from the revision recorded at task start"],
        "EV-59": ["Label it full, degraded, failed or skipped", "what its saved state covers and cannot restore"],
    },
    "durable.md": {
        "WA-02": ["Retry a read-only command at most twice",
                  "retry one with side effects only if its brief or the user says so",
                  "one receipt counting attempts"],
        "HD-46": ["`cancelled` is a stop on purpose, never resumed",
                  "never overwrite a terminal or paused outcome", "paused with its reason, never done"],
        "HD-52": ["batch work over different files is no repeat"],
    },
}

# About 1.25 times each page's word count before this adoption (436, 513, 269 words): P1 nearly doubled
# several references and a tightening pass had to claw it back, so a P2 page that grows past this needs a
# decision, not a quiet edit.
CEILING = {"delegation.md": 545, "handoff.md": 641, "durable.md": 336}

APPLIED = ("HD-05", "CM-45", "GS-35", "GS-02", "HD-06", "GS-10", "HD-41", "CM-08", "HD-38", "HD-44", "GS-65",
           "EV-59", "WA-02", "HD-46", "HD-52")


class GateWordTests(unittest.TestCase):
    def test_each_applied_item_keeps_its_gate_words(self):
        for name, items in GATES.items():
            body = flat(name)
            for item, phrases in items.items():
                with self.subTest(page=name, item=item):
                    self.assertEqual(missing(body, phrases), [])

    def test_control_a_page_with_a_gate_phrase_removed_is_reported(self):
        for name, items in GATES.items():
            body = flat(name)
            for item, phrases in items.items():
                for phrase in phrases:
                    with self.subTest(page=name, item=item, phrase=phrase):
                        self.assertEqual(missing(body.replace(phrase, ""), phrases), [phrase])

    def test_the_end_states_the_stop_rule_leans_on_are_still_named(self):
        durable = flat("durable.md")
        for word in ("`cancelled`", "`crashed`", "`lost`", "`budget-exhausted`", "`finished`"):
            self.assertIn(word, durable)


class SizeAndFormTests(unittest.TestCase):
    def words(self, name):
        return len(raw(name).decode("utf-8").split())

    def test_each_reference_stays_under_its_growth_ceiling(self):
        for name, ceiling in CEILING.items():
            with self.subTest(page=name):
                self.assertLessEqual(self.words(name), ceiling)

    def test_control_a_padded_reference_would_exceed_its_ceiling(self):
        for name, ceiling in CEILING.items():
            with self.subTest(page=name):
                padded = raw(name).decode("utf-8") + "extra " * 120
                self.assertGreater(len(padded.split()), ceiling)

    def test_the_three_references_are_lf_only(self):
        for name in CEILING:
            with self.subTest(page=name):
                self.assertNotIn(b"\r", raw(name))

    def test_the_router_did_not_grow(self):
        self.assertLessEqual(len((ROOT / "SKILL.md").read_text(encoding="utf-8").split()), 600)


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        self.changelog = (ROOT / "CHANGELOG.md").read_bytes().decode("utf-8")

    def test_the_p2_heading_exists_and_the_file_keeps_one_line_ending(self):
        self.assertIn("## 1.0.0-alpha.5 (P2 adoption), unreleased", self.changelog)
        data = (ROOT / "CHANGELOG.md").read_bytes()
        self.assertEqual(data.count(b"\r\n"), data.count(b"\n"))

    def test_each_applied_item_has_a_line(self):
        # At least one, not exactly one: EV-59, HD-06, HD-44, GS-65, HD-46 and WA-02 are shared with other
        # groups, whose own lines land in the same section when the groups are merged.
        for item in APPLIED:
            with self.subTest(item=item):
                self.assertGreaterEqual(self.changelog.count("- P2 (%s):" % item), 1)


if __name__ == "__main__":
    unittest.main()
