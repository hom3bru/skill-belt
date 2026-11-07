"""Page pins for the secret-scanning rules westack-security carries as text (SC-27 amended, SC-33 to SC-38, the per-tool
table), and the size limits of the pages they landed on. The scanner rules moved to references/scanners.md in alpha.21,
word for word, when secrets.md had no room for SC-38 and the table.

Run from the repo root:  python -B -m unittest discover -s skills/westack-security/tests -v
Each pin is also checked against a copy of the page with that phrase taken out, so a test that cannot fail is caught.
The helper checks for the same items are in test_secaudit.py; these pins cover the wording a host reads.
"""
import pathlib
import re
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]

PINS = {
    "SC-27": ("references/scanners.md", ["Betterleaks first, else gitleaks", "config file"]),
    "SC-27 (SKILL.md)": ("SKILL.md", ["Betterleaks/gitleaks", "Record version, command and config.",
                                      "never use live validation"]),
    "SC-27 (scanner list)": ("references/scanners.md", ["Betterleaks/gitleaks, osv-scanner, Semgrep CE, Trivy or Grype "
                                                        "with Syft, Checkov, OpenSSF Scorecard"]),
    "SC-33": ("references/scanners.md", ["Pass `--exit-code 2` and `--redact`.",
                                         "Exit 1, no summary line or \"partial scan\" reads not-run."]),
    "SC-33 (SKILL.md)": ("SKILL.md", ["an erroring or partial scan is not-run"]),
    "SC-34": ("references/scanners.md", ["Scan the working tree (`dir`) and the full history (`git`); one alone is partial",
                                         "a deleted secret stays in history"]),
    "SC-34 (shallow)": ("references/scanners.md", ["a shallow clone cannot show that a secret is absent",
                                                   "Record `shallow`", "a shallow history reads partial"]),
    "SC-35": ("references/secrets.md", ["Betterleaks' `--validation`", "leave it off and say the result is unverified",
                                        "even under a grant", "TruffleHog, Kingfisher and detect-secrets validate by "
                                        "default, so pass their off switch"]),
    "SC-35 (scanners)": ("references/scanners.md", ["westack never uses it, even under a grant",
                                                    "TruffleHog, Kingfisher and detect-secrets validate by default, so "
                                                    "pass their off switch"]),
    "SC-36": ("references/scanners.md", ["Suppress by fingerprint or path, never by the value",
                                         "flags a literal high-entropy allow-list entry"]),
    "SC-36 (triage)": ("references/triage.md", ["by its fingerprint or path, never by writing the secret's value into a config"]),
    "SC-37": ("references/secrets.md", ["Before writing a receipt, note or brief, run `secaudit.py redact FILE`",
                                        "auth schemes and cookie names stay; values under secret-named keys go"]),
    "SC-38": ("references/secrets.md", ["The scanned project never configures its own scan",
                                        "pass a reviewed config, turn inline allow comments off",
                                        "as scope to review, never as settled", "`secaudit.py suppressions ROOT`",
                                        "[scanners](scanners.md)"]),
    "SC-38 (scanners)": ("references/scanners.md", ["Pass `--config` with a config you reviewed",
                                                    "Pass `--ignore-gitleaks-allow`", "no flag stops it",
                                                    "Each is scope to review, never settled"]),
    "SC-38 (SKILL.md)": ("SKILL.md", ["Pass a reviewed config; the target's own suppressions are scope to review, never "
                                      "settled.", "[scanners](references/scanners.md)"]),
    "Per-tool table": ("references/scanners.md", ["| Betterleaks 1.9.0 | off unless `--validation`", "| gitleaks 8.30.1 |",
                                                  "| TruffleHog 3.99.7 | on by default: pass `--no-verification`",
                                                  "| Kingfisher 2.16.0 | on by default: pass `--no-validate`",
                                                  "| detect-secrets 1.5.0 | on by default: pass `-n` or `--no-verify`",
                                                  "| Secretlint 13.1.0 |"]),
}
# Word counts at e297ec5, before the alpha.13 change. A reference may grow at most 20 percent per change; SKILL.md stays at
# or under 1,200 words (the 1,200-word guide, with its Minimum Core block). A new reference stays under 900 words.
BASELINE = {"references/secrets.md": 514, "references/triage.md": 374, "references/record.md": 526, "references/fix.md": 272}
NEW_PAGES = {"references/scanners.md": 900}
SKILL_CAP = 1200
# The brief's 10-31 wording for SC-35 allowed live validation under a named grant; westack keeps never (core authority.md).
NOT_TAKEN = ("unless the user grants", "grants it by name")


def read(relative):
    return (SKILL / relative).read_bytes().decode("utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def missing(body, phrases):
    return [phrase for phrase in phrases if phrase not in flat(body)]


def words(text):
    return len(text.split())


def limit(relative):
    if relative == "SKILL.md":
        return SKILL_CAP
    return NEW_PAGES[relative] if relative in NEW_PAGES else int(BASELINE[relative] * 1.2)


def over_cap(relative, body):
    return words(body) > limit(relative)


class PinTests(unittest.TestCase):
    def test_each_rule_keeps_its_words(self):
        for item, (relative, phrases) in PINS.items():
            with self.subTest(item=item):
                self.assertEqual(missing(read(relative), phrases), [])

    def test_a_page_with_the_phrase_taken_out_fails_the_same_check(self):
        for item, (relative, phrases) in PINS.items():
            body = flat(read(relative))
            for phrase in phrases:
                with self.subTest(item=item, phrase=phrase):
                    self.assertIn(phrase, missing(body.replace(phrase, ""), phrases))

    def test_the_old_trufflehog_only_wording_is_gone(self):
        self.assertNotIn("TruffleHog's live verification", flat(read("SKILL.md")))
        self.assertNotIn("TruffleHog's live verification sends", flat(read("references/secrets.md")))

    def test_the_brief_grant_wording_is_not_taken(self):
        for relative in ("SKILL.md", "references/secrets.md", "references/scanners.md"):
            for phrase in NOT_TAKEN:
                with self.subTest(page=relative, phrase=phrase):
                    self.assertNotIn(phrase, flat(read(relative)))
        planted = flat(read("references/secrets.md")).replace("even under a grant", "unless the user grants it by name")
        self.assertIn(NOT_TAKEN[0], planted, "a page carrying the brief's wording is caught")

    def test_the_scanner_rules_left_secrets_md_whole(self):
        secrets = flat(read("references/secrets.md"))
        for phrase in ("Pass `--exit-code 2` and `--redact`.", "Suppress by fingerprint or path, never by the value"):
            self.assertNotIn(phrase, secrets, "moved to scanners.md, not copied")


class SizeTests(unittest.TestCase):
    PAGES = list(BASELINE) + list(NEW_PAGES) + ["SKILL.md"]

    def test_each_page_stays_within_its_limit(self):
        for relative in self.PAGES:
            with self.subTest(page=relative):
                self.assertFalse(over_cap(relative, read(relative)), (relative, words(read(relative))))

    def test_a_padded_copy_fails_the_limit(self):
        for relative in self.PAGES:
            body = read(relative)
            padded = body + " word" * (limit(relative) - words(body) + 1)
            with self.subTest(page=relative):
                self.assertTrue(over_cap(relative, padded))


if __name__ == "__main__":
    unittest.main()
