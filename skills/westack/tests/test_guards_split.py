"""Guards reference (1.0.0-alpha.5, unreleased): the Host guard section of authority.md moved, unchanged, to
references/guards.md, and the guard items that had no room were applied there (GS-31, GS-13, GS-23, WA-40, GS-06,
GS-24, SS-62, HD-23 egress, GS-11, CM-28, GS-27, GS-33 enforcer sentence, WB-59).

These are text rules, so the tests pin what the pages must keep saying, and each pin also runs on a copy of the page
with the phrase taken out: the check must fail there, or it protects nothing. The ceilings run on a padded copy for
the same reason. No helper was built for any of these items."""
import re
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
HEADING = "## 1.0.0-alpha.5 (P2 adoption), unreleased"
GUARDS_WORDS = 900
AUTHORITY_WORDS_BEFORE = 1254
ROUTER_WORDS = 599


def text(relative):
    return (ROOT / relative).read_bytes().decode("utf-8")


def flat(relative):
    return re.sub(r"\s+", " ", text(relative))


def missing(body, phrases):
    return [phrase for phrase in phrases if phrase not in body]


def words(relative):
    return len(text(relative).split())


# The Host guard section as it stood in authority.md before the split: it moved whole, so each of these opening phrases
# (one per paragraph or bullet) is in guards.md and no longer in authority.md.
MOVED = (
    "A Claude Code host hook can enforce a freeze or careful mode",
    "Label every control you offer or lean on a boundary, a heuristic or advice",
    "A guard that errors, times out, cannot read its policy or cannot enforce what it promises",
    "Each allow, deny or ask rule carries a command it must match and one it must not",
    "A rule that fails to evaluate is listed apart from matched and unmatched",
)

ITEMS = {
    "GS-31": ['keep "could not assess" apart from "low"', "the worst concrete level", "a checker that throws as high",
              "leave all-unknown as unknown", "ask on unknown"],
    "GS-13": ['If a host saves an "always allow", it ranks below every deny', "only the narrowest command family", "never a shell, interpreter",
              "the worst verdict wins"],
    "GS-23": ["State path precedence once per direction", "no allow means no writes", "a deny inside an allow wins",
              "a narrower allow never reopens a broader deny", "never to reopen a deny"],
    "WA-40": ["list every path that changes it", "the strictest gate among its siblings", "an action added later starts closed"],
    "GS-06": ["names what was blocked, why and what is allowed instead", "never grants authority to retry through another tool"],
    "GS-24": ["Canonicalise a host as the resolver reads it", "refuse loopback, link-local, private and metadata addresses",
              "dial the address that passed", "An allowed host is a route, not isolation"],
    "SS-62": ["classify its host the same way", "ask on an unknown host (default no)", "mark it unverified when unattended",
              "Quote instruction-like page text as unverified"],
    "HD-23": ["remove secrets and private data before summarising", "a summary is not redaction", "state what the receiver is given"],
    "GS-11": ["invisible and bidirectional characters", "Unicode tag characters", "HTML comments and hidden attributes",
              "a clean pass is inconclusive for safety", "an ambiguous reconstruction is reported unresolved"],
    "CM-28": ["A host allowlist hides skills from the listing", "does not stop their files being read or scripts run",
              "never call it a restriction"],
    "GS-27": ["may not set `PATH`, library-preload, language-path or other loader variables",
              "no hit, or a failed lookup, is inconclusive, not safe"],
    "GS-33": ["Mark each rule advice or enforced", "naming its enforcer", "a must-not rule with no enforcer is a reported gap"],
    "WB-59": ["lists each capability it needs beyond its files", "the default is none and each is a separate grant",
              "can still spawn processes or reach the network", "list skipped steps"],
}


class SplitTests(unittest.TestCase):
    def test_the_moved_section_is_whole_in_guards_and_gone_from_authority(self):
        guards, authority = flat("references/guards.md"), flat("references/authority.md")
        self.assertEqual(missing(guards, MOVED), [])
        for phrase in MOVED:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, authority)

    def test_authority_keeps_a_one_line_pointer_saying_when_to_read_guards(self):
        body = text("references/authority.md")
        section = re.search(r"^## Host guard\n(.*?)(?=^Provenance:|^## |\Z)", body, re.S | re.M)
        self.assertIsNotNone(section)
        lines = [line for line in section[1].splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        for phrase in ("[guards](guards.md)", "when setting up or relying on a host guard, hook or permission rule set"):
            self.assertIn(phrase, lines[0])
        self.assertTrue((ROOT / "references" / "guards.md").is_file())

    def test_other_pages_point_at_guards_for_what_moved(self):
        self.assertIn("[guards](../references/guards.md), which also covers probing the gate", flat("hosts/README.md"))
        readme = flat("README.md")
        self.assertIn("authority, guards, handoff", readme)
        self.assertIn("twin examples ([guards](references/guards.md))", readme)

    def test_the_router_did_not_grow_and_does_not_list_guards(self):
        router = text("SKILL.md")
        self.assertLessEqual(len(router.split()), ROUTER_WORDS)
        self.assertNotIn("guards", router)

    def test_the_ceilings_hold_and_fail_on_a_padded_copy(self):
        self.assertLessEqual(words("references/guards.md"), GUARDS_WORDS)
        self.assertLess(words("references/authority.md"), AUTHORITY_WORDS_BEFORE)
        padded = text("references/guards.md") + " pad" * 50
        self.assertGreater(len(padded.split()), GUARDS_WORDS)

    def test_the_pages_are_lf_only(self):
        for relative in ("references/guards.md", "references/authority.md", "hosts/README.md", "README.md",
                         "tests/test_guards_split.py", "tests/test_guards_p1.py", "tests/test_guards_p2.py"):
            with self.subTest(file=relative):
                self.assertNotIn(b"\r", (ROOT / relative).read_bytes())


class ItemWordingTests(unittest.TestCase):
    def test_each_item_keeps_its_gate_words_in_guards(self):
        body = flat("references/guards.md")
        for item, phrases in ITEMS.items():
            with self.subTest(item=item):
                self.assertEqual(missing(body, phrases), [])

    def test_a_page_with_the_phrase_taken_out_fails_the_same_check(self):
        body = flat("references/guards.md")
        for item, phrases in ITEMS.items():
            for phrase in phrases:
                with self.subTest(item=item, phrase=phrase):
                    self.assertIn(phrase, missing(body.replace(phrase, ""), phrases))

    def test_no_item_id_leaks_into_the_agent_facing_page(self):
        self.assertIsNone(re.search(r"\b(?:GS|EV|HD|CM|SS|WA|WB)-\d{2}\b", text("references/guards.md")))


class ChangelogTests(unittest.TestCase):
    def section(self):
        body = text("CHANGELOG.md").replace("\r\n", "\n")
        self.assertIn(HEADING, body)
        return body.split(HEADING)[1].split("\n## ")[0]

    def test_one_line_per_item_and_one_for_the_split(self):
        mine = self.section()
        for item in ITEMS:
            with self.subTest(item=item):
                lines = [line for line in mine.splitlines() if re.match(r"- P2 \(" + item + r"\):", line) and "guards.md" in line]
                self.assertEqual(len(lines), 1)
        self.assertEqual(len([line for line in mine.splitlines() if line.startswith("- Split: ")]), 1)

    def test_the_changelog_keeps_one_line_ending_throughout(self):
        data = (ROOT / "CHANGELOG.md").read_bytes()
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        self.assertIn(crlf, (0, lf), "mixed line endings: %d CRLF of %d lines" % (crlf, lf))


if __name__ == "__main__":
    unittest.main()
