"""Tests for westack-docs' prose.py: preserve, lint and selflint.

Run from the repo root:  python -B -m unittest discover -s skills/westack-docs/tests -v
PROSE_UNDER_TEST=<path> points the suite at another copy. Each check also runs against a broken copy, the helper (or
its rules file) with that one condition taken out: the bad input must get through there, or the test protects nothing.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("PROSE_UNDER_TEST") or HERE.parent / "scripts" / "prose.py")
RULES = HERE.parent / "references" / "rules.json"


def load(path=SCRIPT, name="westack_docs_prose_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pr = load()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def codes(report, severity=None):
    return {f["code"] for f in report.get("findings", []) if severity is None or f.get("severity") == severity}


def broken(*edits):
    """A copy of the helper with each (old, new) edit applied once: the condition under test taken out."""
    source = SCRIPT.read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    with tempfile.TemporaryDirectory(prefix="westack-docs-broken-") as temp:
        path = pathlib.Path(temp) / "prose_broken.py"
        path.write_text(source, encoding="utf-8")
        module = load(path, "westack_docs_prose_broken_" + sha(repr(edits))[:12])
    module.DEFAULT_RULES = RULES  # the copy sits in a temporary folder with no references/ beside it
    return module


def off(condition):
    """The edit that turns one `if <condition>:` into `if False:`."""
    return ("if " + condition + ":", "if False:")


ORIGINAL = """---
title: Upload client
---

# Upload client

The client may retry an upload when the server returns 503, unless the file is over 25 MB.

Some uploads fail on slow links. Failures are associated with proxy timeouts, according to the 2026 survey by Acme.

Only the first attempt is logged. Retries do not change the file.

| Setting | Default |
| --- | --- |
| retries | 3 |

> "Uploads are idempotent," the API guide says.

Run `upload --dry-run` first, then see [the API guide](docs/api.md) and https://example.com/status for outages.
Settings live in config/upload.toml.

## Limits

```bash
upload --max-size 25MB
```
"""


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-docs-")
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, text, raw=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if raw:
            path.write_bytes(text)
        else:
            path.write_bytes(text.encode("utf-8"))
        return path

    def pair(self, old=None, new=None, rewrite=None, module=None, map_data=None):
        """preserve() over ORIGINAL and a rewrite (ORIGINAL with one replacement, or given text)."""
        if rewrite is None:
            assert ORIGINAL.count(old) == 1, old
            rewrite = ORIGINAL.replace(old, new)
        a = self.write("original.md", ORIGINAL)
        b = self.write("rewrite.md", rewrite)
        m = None
        if map_data is not None:
            m = self.write("map.json", json.dumps(map_data))
        return (module or pr).preserve(str(a), str(b), map_path=str(m) if m else None)

    def lint(self, text, name="README.md", module=None, **kwargs):
        path = self.write(name, text)
        return (module or pr).lint([str(path)], **kwargs)

    def rules_copy(self, change):
        data = json.loads(RULES.read_text(encoding="utf-8"))
        change(data)
        return self.write("rules.json", json.dumps(data))


# ---- preserve (WD-2, WD-1, WD-3) ------------------------------------------------------------------------------------
ELEMENTS = {
    "fence-changed": ("upload --max-size 25MB\n```", "upload --max-size 30MB\n```"),
    "front-matter-changed": ("title: Upload client", "title: Uploader"),
    "quote-changed": ("\"Uploads are idempotent,\"", "\"Uploads are safe to repeat,\""),
    "table-changed": ("| retries | 3 |", "| attempts | 3 |"),
    "inline-code-changed": ("`upload --dry-run`", "`upload --check`"),
    "link-changed": ("(docs/api.md)", "(docs/api-v2.md)"),
    "path-changed": ("config/upload.toml", "config/client.toml"),
    "heading-structure-changed": ("## Limits", "### Limits"),
}
# The condition in prose.py that raises each code; the broken copy turns it off.
GUARDS = {
    "fence-changed": "a.fences != b.fences",
    "front-matter-changed": "a.front != b.front",
    "quote-changed": "Counter(a.quotes) != Counter(b.quotes)",
    "table-changed": "a.tables != b.tables",
    "inline-code-changed": "Counter(a.inline) != Counter(b.inline)",
    "link-changed": "Counter(a.links) != Counter(b.links)",
    "path-changed": "Counter(a.paths) != Counter(b.paths)",
    "heading-structure-changed": "[h[0] for h in a.headings] != [h[0] for h in b.headings]",
}


class PreserveElementTests(Temp):
    def test_each_altered_element_fails_naming_it(self):
        for code, (old, new) in ELEMENTS.items():
            with self.subTest(code=code):
                report = self.pair(old, new)
                self.assertIn(code, codes(report, "fail"))
                self.assertEqual(report["status"], "findings")

    def test_the_unaltered_pair_and_a_wording_only_edit_pass(self):
        same = self.pair(rewrite=ORIGINAL)
        self.assertEqual((same["status"], same["identical"], same["findings"]), ("clean", True, []))
        wording = self.pair("on slow links.", "on slow connections.")
        self.assertEqual(codes(wording, "fail"), set())
        self.assertFalse(wording["identical"])

    def test_control_each_element_gets_through_a_copy_without_its_check(self):
        for code, (old, new) in ELEMENTS.items():
            with self.subTest(code=code):
                module = broken(off(GUARDS[code]))
                self.assertNotIn(code, codes(self.pair(old, new, module=module)))

    def test_warnings_number_heading_wording_and_shrink(self):
        number = self.pair("returns 503", "returns an error")
        self.assertIn("number-dropped", codes(number, "warning"))
        self.assertEqual(number["status"], "clean", "a dropped number warns; it does not fail")
        heading = self.pair("## Limits", "## Size limits")
        self.assertIn("heading-text-changed", codes(heading, "warning"))
        self.assertNotIn("heading-structure-changed", codes(heading))
        short = self.pair(rewrite=ORIGINAL.split("Only the first")[0])
        self.assertIn("shrink", codes(short, "warning"))

    def test_control_warnings_get_through_copies_without_their_checks(self):
        self.assertNotIn("number-dropped", codes(self.pair("returns 503", "returns an error",
                                                           module=broken(off("dropped_numbers")))))
        self.assertNotIn("heading-text-changed", codes(self.pair("## Limits", "## Size limits",
                                                                 module=broken(off("a.headings != b.headings")))))
        self.assertNotIn("shrink", codes(self.pair(rewrite=ORIGINAL.split("Only the first")[0],
                                                   module=broken(off("words_b < SHRINK * words_a")))))

    def test_the_report_says_a_mechanical_pass_is_not_semantic_proof(self):
        report = self.pair(rewrite=ORIGINAL)
        self.assertIn("not semantic proof", report["claim"])


SHIFTS = {
    "may to will": ("may retry", "will retry", {"qualifier-dropped", "strength-added"}),
    "some to most": ("Some uploads fail", "Most uploads fail", {"qualifier-dropped", "scope-changed"}),
    "associated with to caused": ("are associated with proxy", "are caused by proxy", {"attribution-dropped", "strength-added"}),
    "unless dropped": (", unless the file is over 25 MB.", ".", {"condition-dropped"}),
    "only dropped": ("Only the first attempt", "The first attempt", {"scope-changed"}),
    "negation dropped": ("Retries do not change", "Retries change", {"negation-changed"}),
}
SHIFT_GUARDS = {
    "qualifier-dropped": "delta.get(\"hedge\", 0) < 0",
    "strength-added": "delta.get(\"strength\", 0) > 0",
    "scope-changed": "delta.get(\"scope\", 0) != 0",
    "attribution-dropped": "delta.get(\"attribution\", 0) < 0",
    "condition-dropped": "delta.get(\"condition\", 0) < 0",
    "negation-changed": "delta.get(\"negation\", 0) != 0",
}


class PreserveMeaningTests(Temp):
    """WD-1: each shift pair's 'after' fails; a contraction is not a negation change."""

    def test_each_shift_pair_fails(self):
        for name, (old, new, expected) in SHIFTS.items():
            with self.subTest(shift=name):
                self.assertTrue(expected <= codes(self.pair(old, new), "fail"), codes(self.pair(old, new)))

    def test_a_contraction_is_not_a_negation_change(self):
        report = self.pair("Retries do not change", "Retries don't change")
        self.assertNotIn("negation-changed", codes(report))

    def test_control_each_class_gets_through_a_copy_without_its_check(self):
        for code, guard in SHIFT_GUARDS.items():
            name = next(n for n, (_, _, expected) in SHIFTS.items() if code in expected)
            old, new, _ = SHIFTS[name]
            with self.subTest(code=code):
                self.assertNotIn(code, codes(self.pair(old, new, module=broken(off(guard)))))


class PreserveAdditionTests(Temp):
    """WD-3: numbers and names in the rewrite are a subset of the original's; each changed span maps to a finding."""

    def test_an_added_number_or_name_fails(self):
        self.assertIn("added-number", codes(self.pair("on slow links.", "on links under 2 Mbps."), "fail"))
        summary = self.pair(rewrite=ORIGINAL.replace("Only the first attempt is logged.",
                                                     "Only the first attempt is logged. We recommend moving to Redis."))
        self.assertIn("added-name", codes(summary, "fail"))

    def test_control_additions_get_through_copies_without_their_checks(self):
        self.assertNotIn("added-number", codes(self.pair("on slow links.", "on links under 2 Mbps.",
                                                         module=broken(off("added_numbers")))))
        rewrite = ORIGINAL.replace("Only the first attempt is logged.", "Only the first attempt is logged. We recommend moving to Redis.")
        self.assertNotIn("added-name", codes(self.pair(rewrite=rewrite, module=broken(off("added_names")))))

    def test_every_changed_span_maps_to_a_finding_or_request(self):
        line = ORIGINAL.splitlines().index("Some uploads fail on slow links. Failures are associated with proxy timeouts, "
                                           "according to the 2026 survey by Acme.") + 1
        old, new = "on slow links.", "on slow connections."
        mapped = self.pair(old, new, map_data={"changes": [{"id": "F1", "lines": [line, line]}]})
        self.assertEqual(codes(mapped, "fail"), set())
        unmapped = self.pair(old, new, map_data={"changes": [{"id": "F1", "lines": [1, 2]}]})
        self.assertIn("unmapped-change", codes(unmapped, "fail"))
        control = self.pair(old, new, map_data={"changes": [{"id": "F1", "lines": [1, 2]}]},
                            module=broken(off("not covered")))
        self.assertNotIn("unmapped-change", codes(control))

    def test_a_clean_source_comes_back_byte_identical(self):
        report = self.pair(rewrite=ORIGINAL)
        self.assertTrue(report["identical"])
        self.assertIn("byte-identical", " ".join(report["notes"]))


# ---- lint (WD-4, WD-5, WD-6, WD-12, WD-13, WD-14, WD-16, WD-18) -----------------------------------------------------
MACHINERY = {
    "leaked-citation": "Uptime rose last quarter 【4:2†source】.\n",
    "ai-tracking-param": "See https://docs.example.com/setup?utm_source=chatgpt.com for setup.\n",
    "pasted-assistant-line": "Certainly! Here is the install section.\n",
    "invisible-char": "Install the zero​width client.\n",
    "template-placeholder": "Maintained by [Your Name].\n",
}


class LintMachineryTests(Temp):
    def test_each_token_class_fails(self):
        for code, text in MACHINERY.items():
            with self.subTest(code=code):
                report = self.lint("# Client\n\n" + text)
                self.assertIn(code, codes(report, "fail"))
                self.assertEqual(pr.exit_code(report), 1)

    def test_control_each_class_gets_through_a_rules_file_without_it(self):
        for code, text in MACHINERY.items():
            with self.subTest(code=code):
                rules = self.rules_copy(lambda d, c=code: d.__setitem__("rules", [r for r in d["rules"] if r["id"] != c]))
                self.assertNotIn(code, codes(self.lint("# Client\n\n" + text, rules=str(rules))))

    def test_invisible_char_builtin_has_its_own_control(self):
        text = "# Client\n\nInstall the zero​width client.\n"
        self.assertNotIn("invisible-char", codes(self.lint(text, module=broken(off("ch in INVISIBLE")))))

    def test_an_emoji_joiner_and_a_leading_bom_pass(self):
        text = "﻿# Family\n\nThe family emoji \U0001F468‍\U0001F469‍\U0001F467 keeps its joiners.\n"
        self.assertNotIn("invisible-char", codes(self.lint(text)))

    def test_a_template_leftover_fails_in_both_modes(self):
        for mode in ("draft", "delivery"):
            with self.subTest(mode=mode):
                self.assertIn("template-placeholder", codes(self.lint("Signed, [Your Name]\n", mode=mode), "fail"))

    def test_a_gap_marker_is_open_in_a_draft_and_a_finding_in_delivery(self):
        text = "Churn fell to [churn figure needed] last month.\n"
        draft = self.lint(text, mode="draft")
        self.assertEqual((pr.exit_code(draft), codes(draft)), (0, set()))
        self.assertEqual([g["text"] for g in draft["open_gaps"]], ["[churn figure needed]"])
        delivery = self.lint(text, mode="delivery")
        self.assertIn("gap-marker", codes(delivery, "fail"))
        self.assertEqual(len(delivery["open_gaps"]), 1)
        control = self.lint(text, mode="delivery", module=broken(off("mode == \"draft\" and rule.id == \"gap-marker\"")))
        self.assertIn("gap-marker", codes(control), "the copy treats delivery like a draft only when its mode check is gone")
        control_draft = self.lint(text, mode="draft", module=broken(off("mode == \"draft\" and rule.id == \"gap-marker\"")))
        self.assertIn("gap-marker", codes(control_draft), "without the mode check a draft's gap marker fails")

    def test_code_examples_are_masked_for_prose_rules_but_not_for_machinery(self):
        quoted = self.lint("Write `[Your Name]` where the template has it.\n")
        self.assertNotIn("template-placeholder", codes(quoted))
        leaked = self.lint("```\ncurl https://x.example/a?utm_source=chatgpt.com\n```\n")
        self.assertIn("ai-tracking-param", codes(leaked))
        control = self.lint("Write `[Your Name]` where the template has it.\n", module=broken(off("not rule.in_code")))
        self.assertIn("template-placeholder", codes(control))


# WB-20: the template leftovers `template-placeholder` missed. MADR-style records leave single-curly slots and guidance
# comments in a finished page; each line below is one a person does not write in delivered text. The wording is westack's.
OLD_FORMS = {
    "a bracketed slot": "Signed, [Your Name]\n",
    "a double-curly slot": "Hello {{ customer_name }},\n",
    "a to-do comment": "<!-- Add the install steps here -->\n",
    "an XX date": "Released on 2026-XX-XX.\n",
    "filler text": "Lorem ipsum dolor sit amet.\n",
}
CURLY_FORMS = {
    "a one-word curly slot": "Released on {date}.\n",
    "a curly slot as a heading": "# {title}\n",
    "a curly slot holding a phrase": "* {title of option 1}\n",
    "a curly slot in front matter": "---\ndate: {YYYY-MM-DD of the last update}\n---\n\nText.\n",
    "a quoted curly slot": "Chosen option: \"{title of the option}\", because {why it wins}.\n",
}
GUIDANCE_FORMS = {
    "a comment asking to describe something": "<!-- Describe the context here -->\n",
    "a polite request": "<!-- Please explain your changes in detail -->\n",
    "a three-dash request": "<!--- Provide a short summary of the change -->\n",
    "an optional-section note": "<!-- Optional section. Feel free to remove it. -->\n",
    "a count note": "<!-- the number of options can vary -->\n",
    "a goes-here note": "<!-- the decision goes here -->\n",
    "a request over several lines": "<!--\n  Explain the decision\n-->\n",
}
NEW_FORMS = dict(CURLY_FORMS, **GUIDANCE_FORMS)
# Real text the new forms must leave alone: field sets in a changelog, path and shell templates, set and math notation,
# attribute lists and template tags of other tools, marker comments, and comments that merely start with a verb-like noun.
LEAVE_ALONE = {
    "a field set after a code span": "- optional `evidence[].reason` {code, observed, limit} with eight fixed codes\n",
    "a field set with a key": "- optional `stop` {kind: on-purpose or interrupted, reason}; a stopped record\n",
    "a field set with underscores": "- optional `claim` {owner, state, expires_at, inspection}: one claimant\n",
    "a list of field sets": "- `relations` [{type, target}] are stored once\n",
    "a path parameter": "GET /users/{id} returns the account.\n",
    "a longer path parameter": "GET /users/{userId}/orders lists them.\n",
    "a glob": "Files match src/*.{js,ts} only.\n",
    "a shell variable": "Set ${HOME}/bin first.\n",
    "set notation": "The set {a, b, c} has three members.\n",
    "math": "Euler: e^{ikx}, x_{i} and \\frac{a}{b}.\n",
    "a MyST role": "See {ref}`install` for setup.\n",
    "a heading id": "## Heading {#custom-id}\n",
    "other tools' attributes and tags": "Use [text]{.underline}, {: .class}, {% include x %}, {# note #} and {{< ref >}}.\n",
    "JSON in prose": "JSON such as {\"a\": 1} is fine.\n",
    "a slot in a code span": "Write `{date}` where the template has it.\n",
    "a slot in a fence": "```\n{title}\n```\n",
    "a marker comment": "<!-- westack:minimum-core:start -->\n",
    "a tool directive": "<!-- prettier-ignore -->\n",
    "a comment that starts with a noun": "<!-- List of contributors, generated -->\n",
    "a comment about a state machine": "<!-- State machine diagram -->\n",
    "a build note": "<!-- Generated by build.py; do not edit -->\n",
    "a comment about widths": "<!-- widths can vary by platform -->\n",
    "a sentence that names the verb": "The author may describe the context in the first paragraph.\n",
}


def top_level_alternatives(pattern):
    """The regex split at each | that sits outside parentheses and character classes."""
    parts, current, depth, in_class, i = [], [], 0, False, 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            current.append(pattern[i:i + 2])
            i += 2
            continue
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts


class TemplateLeftoverFormTests(Temp):
    """WB-20: single-curly slots and guidance comments fail like `[Your Name]` does, and real text stays clean."""

    def found(self, text, **kwargs):
        report = self.lint("# Client\n\n" + text if not text.startswith("---") else text, **kwargs)
        self.assertNotEqual(report["status"], "unreadable", report.get("error"))
        return report

    def rule_pattern(self):
        return next(r["pattern"] for r in json.loads(RULES.read_text(encoding="utf-8"))["rules"] if r["id"] == "template-placeholder")

    def without_alternative(self, index):
        """A rules file whose template-placeholder pattern lacks one alternative, and whose examples still all fire."""
        parts = top_level_alternatives(self.rule_pattern())
        self.assertEqual("|".join(parts), self.rule_pattern(), "the splitter keeps every character")
        reduced = "|".join(parts[:index] + parts[index + 1:])

        def change(data):
            rule = next(r for r in data["rules"] if r["id"] == "template-placeholder")
            rule["pattern"] = reduced
            copy = pr.Rule(dict(rule))
            rule["must_match"] = [e for e in rule["must_match"] if pr.fires(copy, e)]
            assert rule["must_match"], "the reduced pattern fires on none of the rule's examples"
        return self.rules_copy(change), parts[index]

    def test_each_new_form_fails_in_both_modes_with_its_line(self):
        for label, text in NEW_FORMS.items():
            for mode in ("draft", "delivery"):
                with self.subTest(form=label, mode=mode):
                    report = self.found(text, mode=mode)
                    self.assertIn("template-placeholder", codes(report, "fail"))
                    self.assertEqual(pr.exit_code(report), 1)
                    self.assertTrue(all(f["line"] for f in report["findings"] if f["code"] == "template-placeholder"))

    def test_a_madr_style_record_with_its_slots_left_in_fails(self):
        record = ("---\nstatus: \"{proposed or accepted}\"\ndate: {YYYY-MM-DD of the last update}\n---\n\n"
                  "# {short title of the decision}\n\n## Context\n\n<!-- Describe the context here -->\n\n"
                  "## Options\n\n* {title of option 1}\n* {title of option 2}\n")
        report = self.lint(record, name="docs/decisions/0001-queue.md")
        self.assertEqual(report["files"][0]["doctype"], "adr")
        hits = [f["line"] for f in report["findings"] if f["code"] == "template-placeholder"]
        self.assertEqual(hits, [2, 3, 6, 10, 14, 15])

    def test_the_old_forms_still_fail(self):
        for label, text in OLD_FORMS.items():
            with self.subTest(form=label):
                self.assertIn("template-placeholder", codes(self.found(text), "fail"))

    def test_code_and_real_prose_are_left_alone(self):
        for label, text in LEAVE_ALONE.items():
            with self.subTest(text=label):
                self.assertNotIn("template-placeholder", codes(self.found(text)), text)

    def test_a_filled_in_record_is_clean(self):
        record = ("---\nstatus: accepted\ndate: 2026-10-31\n---\n\n# Use a queue for uploads\n\n## Context\n\n"
                  "Uploads time out on slow links.\n\n<!-- prettier-ignore -->\n\n## Options\n\n* a queue\n* retries\n")
        self.assertNotIn("template-placeholder", codes(self.lint(record, name="docs/decisions/0002-queue.md")))

    def test_control_a_rules_file_without_the_rule_lets_every_form_through(self):
        rules = self.rules_copy(lambda d: d.__setitem__("rules", [r for r in d["rules"] if r["id"] != "template-placeholder"]))
        for label, text in dict(OLD_FORMS, **NEW_FORMS).items():
            with self.subTest(form=label):
                self.assertNotIn("template-placeholder", codes(self.found(text, rules=str(rules))))

    def test_control_every_alternative_has_a_form_only_it_catches(self):
        every = dict(OLD_FORMS, **NEW_FORMS)
        parts = top_level_alternatives(self.rule_pattern())
        self.assertEqual(len(parts), 8)
        for index in range(len(parts)):
            rules, removed = self.without_alternative(index)
            through = [label for label, text in every.items()
                       if "template-placeholder" not in codes(self.found(text, rules=str(rules)))]
            with self.subTest(removed=removed[:50]):
                self.assertTrue(through, "no example needs this alternative, so it is untested: " + removed)

    def test_control_removing_the_curly_alternative_lets_exactly_the_curly_forms_through(self):
        index = next(i for i, p in enumerate(top_level_alternatives(self.rule_pattern())) if "\\{(?!\\{)" in p)
        rules, _ = self.without_alternative(index)
        for label, text in dict(OLD_FORMS, **NEW_FORMS).items():
            with self.subTest(form=label):
                caught = "template-placeholder" in codes(self.found(text, rules=str(rules)))
                self.assertEqual(caught, label not in CURLY_FORMS)

    def test_control_the_guards_matter_a_naive_curly_pattern_flags_the_text_left_alone(self):
        naive = self.rules_copy(lambda d: next(r for r in d["rules"] if r["id"] == "template-placeholder").update(
            pattern="\\{[^{}\\n]+\\}", must_match=["Released on {date}."], must_not_match=["Plain text."]))
        flagged = [label for label, text in LEAVE_ALONE.items()
                   if "template-placeholder" in codes(self.found(text, rules=str(naive)))]
        self.assertIn("a field set after a code span", flagged)
        self.assertIn("a path parameter", flagged)
        self.assertIn("a shell variable", flagged)
        self.assertNotIn("a slot in a code span", flagged, "code is masked whatever the pattern")


class LintDocTypeTests(Temp):
    SENTENCE = "We added retries to the upload client.\n"

    def test_diff_narration_fails_in_a_readme_and_passes_in_a_changelog(self):
        readme = self.lint(self.SENTENCE, name="README.md")
        self.assertIn("diff-narration", codes(readme, "fail"))
        changelog = self.lint(self.SENTENCE, name="CHANGELOG.md")
        self.assertNotIn("diff-narration", codes(changelog))
        self.assertIn("diff-narration", changelog["files"][0]["skipped"], "skip is listed as not audited, never clean")
        self.assertEqual(changelog["files"][0]["doctype"], "changelog")

    def test_an_explicit_type_wins_over_the_file_name(self):
        report = self.lint(self.SENTENCE, name="CHANGELOG.md", doctype="readme")
        self.assertIn("diff-narration", codes(report, "fail"))
        self.assertFalse(report["files"][0]["inferred"])

    def test_control_a_copy_that_ignores_skip_flags_the_changelog(self):
        module = broken(off("level == \"skip\""))
        self.assertIn("diff-narration", codes(self.lint(self.SENTENCE, name="CHANGELOG.md", module=module)))

    def test_relaxed_level_reports_a_candidate(self):
        report = self.lint(self.SENTENCE, name="reply.md", doctype="reply")
        self.assertIn("diff-narration", codes(report, "candidate"))
        self.assertEqual(pr.exit_code(report), 0)
        control = self.lint(self.SENTENCE, name="reply.md", doctype="reply", module=broken(off("level == \"relaxed\"")))
        self.assertIn("diff-narration", codes(control, "fail"))

    def test_an_unknown_type_is_a_usage_error(self):
        path = self.write("README.md", self.SENTENCE)
        self.assertEqual(pr.main(["lint", str(path), "--type", "novel"]), 64)

    def test_type_inference(self):
        for name, expected in (("README.md", "readme"), ("CHANGELOG.md", "changelog"), ("AGENTS.md", "instructions"),
                               ("CLAUDE.md", "instructions"), ("docs/adr/0001-queue.md", "adr"), ("docs/setup.md", "reference")):
            with self.subTest(name=name):
                self.assertEqual(self.lint("Plain text.\n", name=name)["files"][0]["doctype"], expected)


class LintEvidenceTests(Temp):
    """WD-4: report-only candidates; a candidate never changes the exit code."""

    def test_a_comparative_without_a_baseline_is_a_candidate(self):
        report = self.lint("The new cache is significantly faster.\n")
        self.assertIn("comparative-no-baseline", codes(report, "candidate"))
        self.assertEqual((report["status"], pr.exit_code(report)), ("clean", 0))
        self.assertNotIn("comparative-no-baseline", codes(self.lint("The new cache is 30% faster than the old one.\n")))

    def test_control_the_comparative_gets_through_a_copy_without_its_check(self):
        module = broken(off("COMPARATIVE.search(sentence) and not BASELINE.search(sentence)"))
        self.assertNotIn("comparative-no-baseline", codes(self.lint("The new cache is significantly faster.\n", module=module)))

    def test_hedges_performed_versus_evidential(self):
        self.assertIn("performed-hedge", codes(self.lint("It is important to note that the cache is cold.\n")))
        self.assertNotIn("performed-hedge", codes(self.lint("The upload may fail when the disk is full.\n")))

    def test_judgment_rules_are_listed_as_not_checked(self):
        report = self.lint("Plain text.\n")
        self.assertIn("universal-needs-cases", report["judgment_only"])
        self.assertIn("reply-verdict-first", report["judgment_only"])


class LintPolicyAndPageTests(Temp):
    def test_a_secret_in_a_command_argument_fails_with_file_and_line(self):
        report = self.lint("# Sync\n\nPass your token with --token when you run the sync.\n")
        hit = [f for f in report["findings"] if f["code"] == "secret-in-argument"]
        self.assertEqual([(pathlib.Path(h["file"]).name, h["line"]) for h in hit], [("README.md", 3)])
        rules = self.rules_copy(lambda d: d.__setitem__("rules", [r for r in d["rules"] if r["id"] != "secret-in-argument"]))
        self.assertNotIn("secret-in-argument", codes(self.lint("Pass your token with --token.\n", rules=str(rules))))

    def test_an_as_built_page_without_a_last_verified_commit_fails(self):
        page = "# Architecture\n\nLast updated: 2026-10-30\nApplies when: running the 2.x server\n\nThe queue feeds the workers.\n"
        self.assertIn("as-built-header", codes(self.lint(page, name="arch.md", doctype="as-built"), "fail"))
        good = page.replace("Last updated", "Last verified against: 1a2b3c4d\nLast updated")
        self.assertNotIn("as-built-header", codes(self.lint(good, name="arch.md", doctype="as-built")))
        self.assertNotIn("as-built-header", codes(self.lint(page, name="arch.md", doctype="as-built",
                                                            module=broken(off("missing")))))

    def test_ui_strings_give_three_findings(self):
        strings = ("publish.button: Submit\npublish.toast: Done\n"
                   "publish.error: Sorry, something went wrong.\nsave.button: Save changes\n")
        report = self.lint(strings, name="strings.txt", doctype="ui")
        self.assertEqual(sorted(f["code"] for f in report["findings"]),
                         ["ui-apology-error", "ui-generic-button", "ui-generic-confirmation"])

    def test_a_hard_wrapped_pr_body_fails_and_the_same_text_passes_as_a_markdown_file(self):
        body = ("This change moves the retry loop into the client so that each caller\n"
                "gets the same backoff and the same limit on attempts.\n")
        self.assertIn("hard-wrap", codes(self.lint(body, name="body.md", doctype="pr"), "fail"))
        self.assertNotIn("hard-wrap", codes(self.lint(body, name="guide.md", doctype="guide")))
        self.assertNotIn("hard-wrap", codes(self.lint(body, name="body.md", doctype="pr",
                                                      module=broken(off("len(first) >= WRAP_WIDTH")))))


class LintRootsTests(Temp):
    """WD-13: tracked docs only in named roots; an exception is an exact path with a written reason."""

    def roots(self, data):
        return self.write("docs-roots.json", json.dumps(dict({"format": "westack-docs-roots-1"}, **data)))

    def test_a_stray_file_outside_the_roots_fails_and_an_exception_with_a_reason_passes(self):
        config = self.roots({"roots": ["docs/", "README.md"], "exceptions": [{"path": "SECURITY.md", "reason": "GitHub reads it here"}]})
        stray = self.write("notes.md", "Plain text.\n")
        inside = self.write("docs/setup.md", "Plain text.\n")
        excepted = self.write("SECURITY.md", "Plain text.\n")
        report = pr.lint([str(stray), str(inside), str(excepted)], roots=str(config))
        hits = [f for f in report["findings"] if f["code"] == "outside-roots"]
        self.assertEqual([pathlib.Path(h["file"]).name for h in hits], ["notes.md"])
        control = broken(off("not inside"))
        self.assertNotIn("outside-roots", codes(control.lint([str(stray)], roots=str(config))))

    def test_an_exception_without_a_reason_or_a_directory_hole_stops_the_run(self):
        doc = self.write("notes.md", "Plain text.\n")
        for exceptions in ([{"path": "notes.md", "reason": ""}], [{"path": "scratch/", "reason": "drafts"}],
                           [{"path": "notes/*.md", "reason": "drafts"}]):
            with self.subTest(exceptions=exceptions):
                config = self.roots({"roots": ["docs/"], "exceptions": exceptions})
                report = pr.lint([str(doc)], roots=str(config))
                self.assertEqual((report["status"], pr.exit_code(report)), ("unreadable", 2))
        config = self.roots({"roots": ["docs/"], "exceptions": [{"path": "scratch/", "reason": "drafts"}]})
        control = broken(off("bad_exception(entry, base)"))
        self.assertNotEqual(control.lint([str(doc)], roots=str(config))["status"], "unreadable")


class LintInputTests(Temp):
    def test_a_file_that_is_not_utf8_is_unreadable_and_exits_2(self):
        path = self.write("README.md", b"caf\xe9 au lait\n", raw=True)
        report = pr.lint([str(path)])
        self.assertEqual((report["status"], pr.exit_code(report)), ("unreadable", 2))
        control = broken(("except UnicodeDecodeError as exc:", "except ZeroDivisionError as exc:"),
                         ("data.decode(\"utf-8\")", "data.decode(\"utf-8\", \"replace\")"))
        self.assertNotEqual(control.lint([str(path)])["status"], "unreadable")

    def test_a_missing_file_is_unreadable(self):
        self.assertEqual(pr.lint([str(self.root / "nope.md")])["status"], "unreadable")


# ---- the rules file contract (WD-7) and calibrated gates (WD-9) ----------------------------------------------------
class RuleContractTests(Temp):
    def test_the_shipped_rules_file_keeps_its_contract(self):
        data = json.loads(RULES.read_text(encoding="utf-8"))
        self.assertEqual(pr.contract_problems(data, RULES.parent), [])
        checked = [r for r in data["rules"] if r["kind"] != "judgment"]
        self.assertGreaterEqual(len(checked), 15)
        for rule in checked:
            with self.subTest(rule=rule["id"]):
                self.assertTrue(rule["must_match"] and rule["must_not_match"])
        for entry in data["reverted"]:
            self.assertTrue(entry["false_positive"])

    def test_control_every_checked_rule_lets_its_example_through_a_rules_file_without_it(self):
        data = json.loads(RULES.read_text(encoding="utf-8"))
        doctypes = list(data["doctypes"])
        for rule in (r for r in data["rules"] if r["kind"] != "judgment"):
            with self.subTest(rule=rule["id"]):
                levels = rule["levels"]
                doctype = next((d for d in doctypes if levels.get(d, levels["default"]) == "strict"), None)
                self.assertIsNotNone(doctype, "a rule strict for no document type is never checked")
                example = rule["must_match"] if isinstance(rule["must_match"], str) else rule["must_match"][0]
                self.assertIn(rule["id"], codes(self.lint(example, name="example.md", doctype=doctype)))
                rules = self.rules_copy(lambda d, rid=rule["id"]: d.__setitem__("rules", [r for r in d["rules"] if r["id"] != rid]))
                self.assertNotIn(rule["id"], codes(self.lint(example, name="example.md", doctype=doctype, rules=str(rules))))

    def bad(self, change, text):
        path = self.rules_copy(change)
        with self.assertRaises(pr.RuleFileError) as caught:
            pr.load_rules(path)
        self.assertIn(text, str(caught.exception))
        return path

    def test_a_rule_added_without_a_must_not_fire_example_fails(self):
        def add(d):
            d["rules"].append({"id": "new-rule", "item": "WD-7", "kind": "regex", "severity": "candidate",
                               "pattern": "\\bsynergy\\b", "levels": {"default": "strict"},
                               "must_match": ["Find the synergy."], "why": "taste"})
        path = self.bad(add, "must_not_match")
        report = pr.lint([str(self.write("README.md", "Plain.\n"))], rules=str(path))
        self.assertEqual(pr.exit_code(report), 2)
        control = broken(off("not must_not"))
        control.load_rules(path)

    def test_an_example_that_disagrees_fails(self):
        def fire(d):
            rule = next(r for r in d["rules"] if r["id"] == "causal-verb")
            rule["must_not_match"].append("The deploy caused the outage.")
        self.bad(fire, "must not fire")

        def miss(d):
            rule = next(r for r in d["rules"] if r["id"] == "causal-verb")
            rule["must_match"].append("The outage followed the deploy.")
        self.bad(miss, "must fire")

    def test_judgment_reverted_and_level_entries_are_checked(self):
        self.bad(lambda d: d["rules"].append({"id": "j", "item": "WD-4", "kind": "judgment"}), "why")
        self.bad(lambda d: d["reverted"].append({"id": "r", "item": "WD-5", "pattern": "x", "why": "y"}), "false_positive")
        def level(d):
            next(r for r in d["rules"] if r["id"] == "causal-verb")["levels"]["novel"] = "strict"
        self.bad(level, "unknown document type")


class GateTests(Temp):
    """WD-9: a numeric gate is calibrated on a hashed corpus; a tampered corpus stops the run."""

    def corpus(self, n=100, registers=("docs", "changelog")):
        entries = []
        for i in range(n):
            register = registers[i % len(registers)]
            path = self.write("corpus/%s/%03d.md" % (register, i), "A plain page number %d.\n" % i)
            entries.append({"path": "corpus/%s/%03d.md" % (register, i), "sha256": sha(path.read_bytes()), "register": register})
        manifest = self.write("corpus/manifest.json", json.dumps({"files": entries}))
        return manifest

    def gated_rules(self, manifest, n=100, registers=("docs", "changelog"), threshold=5.0):
        gate = {"rule": "performed-hedge", "per_1000_words": threshold,
                "corpus": {"manifest": "corpus/manifest.json", "sha256": sha(manifest.read_bytes())},
                "n": n, "registers": list(registers)}
        return self.rules_copy(lambda d: d.__setitem__("gates", [gate]))

    def test_a_calibrated_gate_loads_and_counts_a_rate(self):
        rules = self.gated_rules(self.corpus())
        pr.load_rules(rules)
        dense = self.lint("It is important to note that it is arguably cold.\n", rules=str(rules))
        self.assertIn("performed-hedge", codes(dense))
        sparse = self.lint("Arguably cold. " + "word " * 600 + "\n", rules=str(rules))
        self.assertNotIn("performed-hedge", codes(sparse), "one hedge in 600 words is under 5 per 1,000")

    def test_a_tampered_corpus_file_stops_the_run_with_a_hash_mismatch(self):
        rules = self.gated_rules(self.corpus())
        (self.root / "corpus/docs/000.md").write_bytes(b"tampered\n")
        with self.assertRaises(pr.RuleFileError) as caught:
            pr.load_rules(rules)
        self.assertIn("corpus hash mismatch", str(caught.exception))
        report = self.lint("Plain.\n", rules=str(rules))
        self.assertEqual(pr.exit_code(report), 2)
        broken(off("digest != entry.get(\"sha256\")")).load_rules(rules)

    def test_a_tampered_manifest_stops_the_run(self):
        manifest = self.corpus()
        rules = self.gated_rules(manifest)
        manifest.write_bytes(manifest.read_bytes() + b" ")
        with self.assertRaises(pr.RuleFileError):
            pr.load_rules(rules)

    def test_no_rate_under_n_100_or_from_one_register(self):
        small = self.gated_rules(self.corpus(n=99), n=99)
        with self.assertRaises(pr.RuleFileError) as caught:
            pr.load_rules(small)
        self.assertIn("n under 100", str(caught.exception))
        broken(off("gate.get(\"n\", 0) < MIN_CORPUS")).load_rules(small)

    def test_one_register_is_refused(self):
        one = self.gated_rules(self.corpus(registers=("docs",)), registers=("docs",))
        with self.assertRaises(pr.RuleFileError) as caught:
            pr.load_rules(one)
        self.assertIn("one register", str(caught.exception))


# ---- selflint (WD-8) ------------------------------------------------------------------------------------------------
class SelflintTests(Temp):
    def tree(self):
        self.write("skills/x/SKILL.md", "# X\n\nWrite `[Your Name]` where the template has it.\n")
        self.write("skills/x/evals/fixture.md", "Signed, [Your Name]\n")
        self.write("skills/x/CHANGELOG.md", "# Changelog\n\nWe added retries to the upload client.\n")
        self.write("skills/x/references/page.md", "The upload client retries three times.\n")
        return self.root

    def test_each_exclusion_reports_its_hits_beside_the_naive_scan(self):
        report = pr.selflint(str(self.tree()))
        self.assertEqual((report["status"], pr.exit_code(report)), ("clean", 0))
        for name in ("not-shipped", "doctype-skip", "code"):
            with self.subTest(exclusion=name):
                self.assertGreaterEqual(report["exclusions"][name], 1)
        self.assertEqual(report["dead_exclusions"], [])
        placeholder = report["rules"]["template-placeholder"]
        self.assertEqual((placeholder["naive"], placeholder["kept"]), (2, 0))
        self.assertEqual(report["files"], 4)

    def test_control_disabling_one_exclusion_drops_its_count_to_zero(self):
        for name in ("not-shipped", "doctype-skip", "code"):
            with self.subTest(exclusion=name):
                module = broken(off("exclusion_on(\"%s\")" % name))
                report = module.selflint(str(self.tree()))
                self.assertEqual(report["exclusions"][name], 0)
                self.assertIn(name, report["dead_exclusions"])
                self.assertEqual(module.exit_code(report), 1, "the hit it used to remove now counts against a ceiling of 0")

    def test_a_seeded_leak_in_a_shipped_page_fails_with_file_and_line(self):
        self.tree()
        self.write("skills/x/references/leak.md", "# Leak\n\nSee https://a.example/b?utm_source=chatgpt.com\n")
        report = pr.selflint(str(self.root))
        self.assertEqual(pr.exit_code(report), 1)
        hit = next(f for f in report["findings"] if f["code"] == "ai-tracking-param")
        self.assertEqual((pathlib.Path(hit["file"]).name, hit["line"]), ("leak.md", 3))

    def test_an_unreadable_file_exits_2_never_passes(self):
        self.tree()
        self.write("skills/x/references/latin1.md", b"caf\xe9\n", raw=True)
        report = pr.selflint(str(self.root))
        self.assertEqual((report["status"], pr.exit_code(report)), ("unreadable", 2))
        self.assertEqual([pathlib.Path(p).name for p in report["unreadable"]], ["latin1.md"])

    def test_a_dead_exclusion_shows_zero(self):
        # No fixtures and no code: two exclusions remove nothing. doctype-skip stays live, since the naive scan runs the
        # as-built header check on every page and that rule is skipped for every type but as-built.
        self.write("skills/x/references/page.md", "Plain text.\n")
        report = pr.selflint(str(self.root))
        self.assertEqual(set(report["dead_exclusions"]), {"not-shipped", "code"})
        self.assertEqual(report["exclusions"]["doctype-skip"], report["rules"]["as-built-header"]["naive"])

    def ceilinged(self, ceilings, log):
        def change(d):
            d["selflint"]["ceilings"] = ceilings
            d["selflint"]["ceiling_log"] = log
        return self.rules_copy(change)

    def test_a_logged_ceiling_admits_its_hits_and_can_only_move_down(self):
        self.tree()
        self.write("skills/x/references/one.md", "Signed, [Your Name]\n")
        first = {"rule": "template-placeholder", "to": 1, "date": "2026-10-30", "reason": "one quoted example"}
        ok = self.ceilinged({"template-placeholder": 1}, [first])
        self.assertEqual(pr.exit_code(pr.selflint(str(self.root), rules=str(ok))), 0)
        raised = self.ceilinged({"template-placeholder": 2},
                                [first, {"rule": "template-placeholder", "from": 1, "to": 2, "date": "2026-10-31", "reason": "more"}])
        with self.assertRaises(pr.RuleFileError) as caught:
            pr.load_rules(raised)
        self.assertIn("only move down", str(caught.exception))
        broken(off("entry[\"to\"] > entry[\"from\"]")).load_rules(raised)
        unlogged = self.ceilinged({"template-placeholder": 3}, [])
        with self.assertRaises(pr.RuleFileError):
            pr.load_rules(unlogged)


# ---- audit leaves files unchanged; the helper runs nothing and writes nothing -----------------------------------------
class NoWriteTests(Temp):
    def hashes(self):
        return {p.relative_to(self.root).as_posix(): sha(p.read_bytes()) for p in sorted(self.root.rglob("*")) if p.is_file()}

    def run_all(self, module):
        a = self.write("docs/original.md", ORIGINAL)
        b = self.write("docs/rewrite.md", ORIGINAL.replace("may retry", "will retry"))
        c = self.write("docs/README.md", "Signed, [Your Name]\nWe added retries.\n")
        module.preserve(str(a), str(b))
        module.lint([str(a), str(b), str(c)])
        module.selflint(str(self.root))

    def test_an_audit_run_leaves_every_file_hash_unchanged(self):
        self.write("docs/README.md", "Signed, [Your Name]\nWe added retries.\n")
        before = self.hashes()
        self.run_all(pr)
        self.assertEqual(self.hashes(), {**before, **{k: v for k, v in self.hashes().items() if k not in before}})
        for key, value in before.items():
            self.assertEqual(self.hashes()[key], value, key)

    def test_control_a_copy_that_writes_back_changes_a_hash(self):
        module = broken(("    files = [pathlib.Path(p) for p in paths]\n",
                         "    files = [pathlib.Path(p) for p in paths]\n    files[-1].write_bytes(files[-1].read_bytes() + b'x')\n"))
        self.write("docs/README.md", "Signed, [Your Name]\nWe added retries.\n")
        before = self.hashes()
        self.run_all(module)
        self.assertNotEqual(self.hashes()["docs/README.md"], before["docs/README.md"])

    def test_the_helper_has_no_write_network_or_process_calls(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for pattern in (r"open\([^)]*['\"][wax]", r"\.write_text\(", r"\.write_bytes\(", r"\bos\.(?:remove|unlink|rename|replace)\b",
                        r"\bshutil\b", r"\bsubprocess\b", r"\bsocket\b", r"\burllib\b", r"\bhttp\.client\b"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, source), pattern)


# ---- command line ---------------------------------------------------------------------------------------------------
class CliTests(Temp):
    def run_cli(self, *args):
        done = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True, timeout=120)
        return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else None)

    def test_exit_codes_and_json(self):
        a = self.write("a.md", ORIGINAL)
        b = self.write("b.md", ORIGINAL.replace("may retry", "will retry"))
        code, report = self.run_cli("preserve", str(a), str(a))
        self.assertEqual((code, report["format"], report["status"]), (0, "westack-docs-prose-1", "clean"))
        self.assertTrue(report["claim"])
        code, report = self.run_cli("preserve", str(a), str(b))
        self.assertEqual(code, 1)
        code, report = self.run_cli("lint", str(self.write("README.md", "Signed, [Your Name]\n")))
        self.assertEqual((code, report["status"]), (1, "findings"))
        code, report = self.run_cli("lint", str(self.root / "missing.md"))
        self.assertEqual(code, 2)
        code, report = self.run_cli("selflint", str(self.root))
        self.assertIn(code, (0, 1))
        self.assertTrue(report["claim"])

    def test_usage_errors_exit_64(self):
        self.assertEqual(self.run_cli()[0], 64)
        self.assertEqual(self.run_cli("rewrite", "x")[0], 64)
        self.assertEqual(self.run_cli("lint", "x.md", "--mode", "final")[0], 64)


if __name__ == "__main__":
    unittest.main()
