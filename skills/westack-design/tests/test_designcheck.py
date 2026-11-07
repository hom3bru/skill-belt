"""Tests for westack-design's designcheck.py: token, contrast, rule, waiver, inventory, record and report checks.

Run from the repo root:  python -B -m unittest discover -s skills/westack-design/tests -v
DESIGNCHECK_UNDER_TEST=<path> points the suite at another copy (its references/ folder must sit beside its scripts/
folder). Each check is also run against a copy of the script with that one condition removed (a broken copy): the bad
input must get through there, or the test protects nothing.
"""
import atexit
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = pathlib.Path(os.environ.get("DESIGNCHECK_UNDER_TEST") or SKILL / "scripts" / "designcheck.py")
REFERENCES = SCRIPT.parent.parent / "references"
_TEMPS = []


def _cleanup():
    for temp in _TEMPS:
        temp.cleanup()


atexit.register(_cleanup)


def load(path=SCRIPT, name="westack_designcheck_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dc = load()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def broken(*edits):
    """A copy of the script with each (old, new) edit applied once (the condition under test removed), beside a copy
    of the references it reads by default."""
    source = SCRIPT.read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    temp = tempfile.TemporaryDirectory(prefix="westack-design-broken-")
    _TEMPS.append(temp)
    root = pathlib.Path(temp.name)
    (root / "scripts").mkdir()
    shutil.copytree(REFERENCES, root / "references")
    path = root / "scripts" / "designcheck.py"
    path.write_text(source, encoding="utf-8")
    return load(path, "westack_designcheck_broken_" + sha(repr(edits))[:12])


def off(condition):
    """The edit that turns one `if <condition>:` into `if False:`."""
    return ("if " + condition + ":", "if False:")


def run(module, *argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = module.main([str(a) for a in argv])
    text = out.getvalue()
    try:
        return code, json.loads(text)
    except ValueError:
        return code, {"raw": text}


def codes(report, key="findings"):
    return [f.get("code") for f in report.get(key, [])]


class Tree(unittest.TestCase):
    """A temporary folder written from a {relative path: text} map."""

    files = {}

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="westack-design-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.write(self.files)

    def write(self, files):
        for relative, text in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text if isinstance(text, str) else json.dumps(text, indent=2), encoding="utf-8")

    def p(self, relative):
        return self.root / relative


THEME = {"colors": {"primary": "#112233", "accent": "#FF6A6A", "background": "#FFFFFF", "foreground": "#111827"},
         "spacing": {"base": "4px", "2": "8px", "3": "12px", "4": "16px"}, "rounded": {"md": "6px"}}


class TokensTests(Tree):
    files = {"theme.json": THEME,
             "src/button.css": ".btn{background:#FF6B6B;color:var(--x)}\n",
             "src/title.css": ".title { color: #112233; }\n",
             "src/card.css": ".card { padding: 8px 13px; border: 1px solid; margin: 0; }\n",
             "src/page.html": "<div class=\"p-[13px] bg-[#112233]\">x</div>\n<a href=\"#add\">anchor</a>\n",
             "src/brand.css": ".x { --brand: #ff0000; }\n"}

    def tokens(self, module, *src, extra=()):
        return run(module, "tokens", *[self.p(s) for s in src], "--theme", self.p("theme.json"), *extra)

    def test_a_hex_beside_var_is_reported_with_the_token_to_use(self):
        code, report = self.tokens(dc, "src/button.css")
        self.assertEqual(code, 1, report)
        hits = [f for f in report["findings"] if f["code"] == "raw-colour"]
        self.assertEqual([f["value"] for f in hits], ["#FF6B6B"])
        self.assertEqual(hits[0]["use"], "colors.accent")
        self.assertIn("theme.json", hits[0]["message"])
        # the donor's earlier bug: skip every line that also uses var(
        control = broken(('for hit in literal_colours(m.group("value")):',
                          'for hit in ([] if "var(" in text.splitlines()[line_of(text, m.start()) - 1] '
                          'else literal_colours(m.group("value"))):'))
        self.assertEqual(codes(self.tokens(control, "src/button.css")[1]), [])

    def test_an_exact_theme_colour_names_its_token(self):
        _, report = self.tokens(dc, "src/title.css")
        hit = report["findings"][0]
        self.assertEqual((hit["use"], hit["exact"]), ("colors.primary", True))
        control = broken(off("exact_colour"))
        self.assertFalse(self.tokens(control, "src/title.css")[1]["findings"][0]["exact"])

    def test_every_value_position_is_scanned_and_hairlines_and_zero_pass(self):
        _, report = self.tokens(dc, "src/card.css")
        self.assertEqual([f["value"] for f in report["findings"]], ["8px", "13px"])
        self.assertEqual(report["findings"][0]["use"], "spacing.2")
        control = broken(("for lm in LENGTH_RE.finditer(value):", "for lm in list(LENGTH_RE.finditer(value))[:1]:"))
        self.assertEqual([f["value"] for f in self.tokens(control, "src/card.css")[1]["findings"]], ["8px"])

    def test_an_arbitrary_value_gets_its_on_scale_class(self):
        _, report = self.tokens(dc, "src/page.html")
        by_value = {f["value"]: f for f in report["findings"]}
        self.assertEqual(sorted(by_value), ["#112233", "13px"], "an href fragment is not a colour")
        self.assertEqual(by_value["13px"]["use"], "p-3.25")
        self.assertEqual(by_value["#112233"]["use"], "bg-primary")
        control = broken(off("on_scale is not None"))
        controlled = {f["value"]: f for f in self.tokens(control, "src/page.html")[1]["findings"]}
        self.assertNotEqual(controlled["13px"]["use"], "p-3.25")

    def test_a_literal_custom_property_outside_the_token_files_is_flagged(self):
        _, report = self.tokens(dc, "src/brand.css")
        self.assertEqual(codes(report), ["raw-colour"])
        code, report = self.tokens(dc, "src/brand.css", extra=("--token-file", self.p("src/brand.css")))
        self.assertEqual((code, report["status"]), (2, "not-run"), "every file exempt: nothing was scanned")

    def test_a_baseline_lists_new_tokens_as_proposals(self):
        newer = json.loads(json.dumps(THEME))
        newer["colors"]["brand"] = "#AA3355"
        self.write({"theme.json": newer, "old.json": THEME})
        code, report = self.tokens(dc, "src/title.css", extra=("--baseline", self.p("old.json")))
        self.assertIn({"kind": "token", "name": "colors.brand"}, [
            {k: p[k] for k in ("kind", "name")} for p in report["proposals"]])
        self.assertEqual(code, 1)


class PreflightTests(Tree):
    files = {"project/styles/global.css": ":root {\n  --brand: #123456;\n}\n", "project/app.css": ".a{color:red}\n",
             "project/tailwind.config.js": "throw new Error('this file must never be run');\n"}

    def test_a_project_with_root_variables_refuses_a_new_token_file(self):
        code, report = run(dc, "tokens", self.p("project"), "--writing", self.p("project/tokens.json"))
        self.assertEqual(code, 1, report)
        kinds = {pathlib.Path(s["file"]).name: s["kind"] for s in report["sources"]}
        self.assertIn("css-variables", kinds["global.css"])
        self.assertIn("never loaded", kinds["tailwind.config.js"])
        self.assertIn("token-source-exists", codes(report))
        code, report = run(dc, "tokens", self.p("project"), "--writing", self.p("project/tokens.json"),
                           "--replace-authorised", "turn 7")
        self.assertEqual((code, report["status"]), (0, "clean"))
        control = broken(off("css_variables"))
        names = [pathlib.Path(s["file"]).name for s in run(control, "tokens", self.p("project/styles"), "--writing",
                                                            self.p("project/tokens.json"))[1].get("sources", [])]
        self.assertNotIn("global.css", names)


class SuppressionTests(Tree):
    files = {"theme.json": THEME,
             "agent.css": "/* designcheck: ignore-rule raw-colour by=agent because brand */\n.a { color: #ff0000; }\n",
             "user.css": "/* designcheck: ignore-rule raw-colour by=user turn=12 because brand red from logo.svg */\n"
                         ".a { color: #ff0000; }\n",
             "value.css": "/* designcheck: ignore raw-colour value=#ff0000 by=agent because the fill of logo.svg */\n"
                          ".a { color: #ff0000; }\n.b { color: #00ff00; }\n"}

    def check(self, module, name):
        return run(module, "tokens", self.p(name), "--theme", self.p("theme.json"))[1]

    def test_a_rule_wide_ignore_needs_the_user(self):
        report = self.check(dc, "agent.css")
        self.assertEqual(sorted(codes(report)), ["raw-colour", "suppression-needs-user"])
        report = self.check(dc, "user.css")
        self.assertEqual(codes(report), [])
        self.assertEqual(report["suppressions"][0]["applied_to"], 1, "an applied ignore is listed, never hidden")
        control = broken(off('kind != "ignore" and not (fields.get("by") == "user" and fields.get("turn"))'))
        self.assertEqual(codes(self.check(control, "agent.css")), [])

    def test_a_value_scoped_ignore_silences_only_that_value(self):
        report = self.check(dc, "value.css")
        self.assertEqual([f["value"] for f in report["findings"]], ["#00ff00"])
        self.assertEqual(report["suppressions"][0]["kind"], "ignore")


RECORD_JSON = {
    "format": "westack-design-record-1",
    "colors": {"background": "#FFFFFF", "foreground": "#111827", "primary": "#1D4ED8", "on-primary": "#FFFFFF",
               "muted": "#F3F4F6", "muted-foreground": "#4B5563", "ring": "#2563EB"},
    "spacing": {"2": "8px", "4": "16px"}, "rounded": {"md": "6px"},
    "typography": {"body": {"fontFamily": "Inter", "fontSize": "16px", "fontWeight": 400}},
    "components": {"button-primary": {"textColor": "{colors.on-primary}", "backgroundColor": "{colors.primary}"},
                   "button-primary-hover": {"backgroundColor": "#3B82F6"}},
    "omitted": {"Elevation": "flat surfaces; the product uses no shadows"},
}
SECTION_TEXT = {"Overview": "Ledger screens for finance teams who close the books monthly.",
                "Colors": "Ink on white; one blue for actions.", "Typography": "Inter throughout.",
                "Layout": "An 8px rhythm.", "Shapes": "6px corners.", "Components": "Buttons only so far.",
                "Do and Don't": "Do keep one action colour. Don't add gradients."}


def record_md(tokens=RECORD_JSON, sections=("Overview", "Colors", "Typography", "Layout", "Shapes", "Components",
                                             "Do and Don't"), extra_blocks=()):
    parts = ["# Ledger design record", ""]
    for name in sections:
        parts += ["## " + name, "", SECTION_TEXT.get(name, "text"), ""]
        if name == "Overview":
            parts += ["```json tokens", json.dumps(tokens, indent=2), "```", ""]
    for block in extra_blocks:
        parts += ["```json tokens", block, "```", ""]
    return "\n".join(parts)


class ContrastTests(Tree):
    files = {"record.md": record_md()}

    def contrast(self, module, tokens=None):
        if tokens is not None:
            self.write({"r.json": tokens})
            return run(module, "contrast", self.p("r.json"))
        return run(module, "contrast", self.p("record.md"))

    def test_a_hover_variant_inherits_its_text_and_fails(self):
        code, report = self.contrast(dc)
        self.assertEqual(code, 1, report)
        self.assertEqual([f["where"] for f in report["findings"]], ["components.button-primary-hover text"])
        base = next(p for p in report["pairs"] if p["pair"] == "components.button-primary text")
        self.assertGreaterEqual(base["ratio"], 4.5)
        control = broken(("while base:", "while False:"))
        self.assertEqual(self.contrast(control)[0], 0, "a checker that skips variants passes the hover")

    def test_ratios_follow_wcag_and_are_never_rounded_up(self):
        self.assertAlmostEqual(dc.contrast_ratio(dc.parse_colour("#000"), dc.parse_colour("#fff")), 21.0, places=6)
        report = self.contrast(dc, {"colors": {"background": "#FFFFFF", "foreground": "#777777"}})[1]
        self.assertEqual((report["pairs"][0]["ratio"], report["pairs"][0]["status"]), (4.47, "failed"))
        report = self.contrast(dc, {"colors": {"background": "#FFFFFF", "foreground": "#767676"}})[1]
        self.assertEqual((report["pairs"][0]["ratio"], report["pairs"][0]["status"]), (4.54, "passed"))
        control = broken(("ratio = contrast_ratio(fg, bg)", "ratio = round(contrast_ratio(fg, bg), 1)"))
        self.assertEqual(self.contrast(control, {"colors": {"background": "#FFFFFF", "foreground": "#777777"}})[0], 0)

    def test_alpha_is_composited_or_marked_unresolved(self):
        code, report = self.contrast(dc, {"colors": {"background": "#FFFFFF", "foreground": "#0000004D"}})
        self.assertEqual(codes(report), ["contrast-fail"])
        control = broken(off("fg[3] < 1"))
        self.assertEqual(self.contrast(control, {"colors": {"background": "#FFFFFF", "foreground": "#0000004D"}})[0], 0)
        report = self.contrast(dc, {"colors": {"background": "#FFFFFF80", "foreground": "#111827"}})[1]
        self.assertEqual(codes(report), ["contrast-unresolved"])

    def test_muted_text_is_never_stronger_than_primary_text(self):
        tokens = {"colors": {"background": "#FFFFFF", "foreground": "#6B7280", "muted-foreground": "#111827"}}
        self.assertIn("muted-stronger", codes(self.contrast(dc, tokens)[1]))
        control = broken(off("muted > fg_ratio"))
        self.assertNotIn("muted-stronger", codes(self.contrast(control, tokens)[1]))

    def test_large_text_and_icons_use_three_to_one(self):
        tokens = {"colors": {"background": "#FFFFFF"}, "components": {
            "hero-title": {"textColor": "#8A8A8A", "typography": {"fontSize": "24px", "fontWeight": 400}},
            "caption": {"textColor": "#8A8A8A", "typography": {"fontSize": "14px"}},
            "toolbar": {"iconColor": "#8A8A8A", "backgroundColor": "#FFFFFF"}}}
        report = self.contrast(dc, tokens)[1]
        self.assertEqual([f["where"] for f in report["findings"]], ["components.caption text"])
        control = broken(("needs = ui_t if large else text_t", "needs = ui_t"))
        self.assertEqual(self.contrast(control, tokens)[0], 0)

    def test_no_pair_to_check_is_not_clean(self):
        self.assertEqual(self.contrast(dc, {"colors": {"primary": "#112233"}})[0], 2)


SEEDED_CSS = (".page { background: #F4F1EA; }\n.cta { background: #D97757; }\n"
              ".card-a { border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }\n"
              ".card-b { border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }\n"
              ".card-c { border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }\n"
              ".hero { background: linear-gradient(135deg, #7C3AED, #2563EB); }\n")
SEEDED_HTML = ("<p class=\"text-xs uppercase tracking-widest\">Why teams switch</p>\n"
               "<h2>Built for the <span class=\"accent\">close</span></h2>\n"
               "<ul><li>Reconciliation — every night</li></ul>\n"
               "<a class=\"button\" href=\"/signup\">Start free →</a>\n")
TELLS = ["tell-arrow-in-button", "tell-cream-terracotta", "tell-eyebrow", "tell-headline-accent-word",
         "tell-purple-blue-gradient", "tell-spaced-em-dash-label", "tell-uniform-card-chrome"]


class RulesTests(Tree):
    files = {"site/styles.css": SEEDED_CSS, "site/index.html": SEEDED_HTML,
             "neutral.md": "A landing page for an accounting tool.\n",
             "warm.md": "A warm editorial look: cream paper and terracotta accents.\n",
             "thin/index.html": "<section><h2>Security</h2><p>We take security seriously.</p></section>\n"
                                "<section><h2>Speed</h2><p>Fast.</p></section>\n<p>Lorem ipsum dolor sit amet.</p>\n",
             "honest/index.html": "<form><input name=\"email\"><button>Join</button><p>Thanks, you're on the list!</p>"
                                  "</form>\n<p class=\"stat\">10,000+ teams</p>\n",
             "honest-ok/index.html": "<form action=\"/api/join\" method=\"post\"><input name=\"email\"></form>\n"
                                     "<p class=\"stat\" data-source=\"metrics.csv\">10,000+ teams</p>\n",
             "frame/list.tsx": "if (window.innerWidth < 768) setCompact(true);\n"
                               "if (rows.length === 0) return <Empty />;\nif (isLoading) return null;\n",
             "type/a.css": ".legal { font-size: 10.9px; }\n", "type/b.css": ".legal { font-size: 11px; }\n",
             "finish/index.html": "<p style=\"color: #555\">Note</p>\n"}

    def rules(self, module, src, brief="neutral.md", extra=()):
        return run(module, "rules", self.p(src), "--brief", self.p(brief), *extra)

    def test_a_seeded_page_raises_every_tell_and_the_brief_wins(self):
        code, report = self.rules(dc, "site")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(set(f["rule"] for f in report["findings"])), TELLS)
        report = self.rules(dc, "site", brief="warm.md")[1]
        self.assertNotIn("tell-cream-terracotta", [f["rule"] for f in report["findings"]])
        self.assertEqual([f["rule"] for f in report["allowed_by_brief"]], ["tell-cream-terracotta"])
        control = broken(off("terms"))
        self.assertIn("tell-cream-terracotta", [f["rule"] for f in self.rules(control, "site", "warm.md")[1]["findings"]])

    def test_each_code_tell_has_its_control(self):
        for edit, rule in ((off("not passes_cut(len(members), limit)"), "tell-uniform-card-chrome"),
                           (off("in_a and in_b"), "tell-cream-terracotta"),
                           (off("any(in_band(c, band_a) for c in stops) and any(in_band(c, band_b) for c in stops)"),
                            "tell-purple-blue-gradient")):
            with self.subTest(rule=rule):
                self.assertIn(rule, [f["rule"] for f in self.rules(dc, "site")[1]["findings"]])
                # the load-time example check would refuse a copy whose matcher no longer matches its own example,
                # so the control runs on a copy with that check also off
                control = broken(edit, off("not match(example)"))
                self.assertNotIn(rule, [f["rule"] for f in self.rules(control, "site")[1]["findings"]])

    def test_a_thin_page_that_passes_every_ban_is_reported(self):
        report = self.rules(dc, "thin")[1]
        self.assertEqual(sorted(f["rule"] for f in report["findings"]),
                         ["substance-placeholder-copy", "substance-thin-section", "substance-thin-section"])
        self.assertFalse(any(f["rule"].startswith("tell-") for f in report["findings"]))
        data = json.loads((REFERENCES / "rules.json").read_text(encoding="utf-8"))
        data["rules"] = [r for r in data["rules"] if not r["id"].startswith("substance-")]
        self.write({"no-substance.json": data})
        self.assertEqual(self.rules(dc, "thin", extra=("--rules", self.p("no-substance.json")))[0], 0)

    def test_honesty_rules_flag_invented_proof_and_dead_success(self):
        report = self.rules(dc, "honest")[1]
        self.assertEqual(sorted(f["rule"] for f in report["findings"]),
                         ["honesty-success-no-endpoint", "honesty-unsourced-stat"])
        self.assertTrue(all(f["tier"] == "floor" for f in report["findings"]))
        self.assertEqual(self.rules(dc, "honest-ok")[0], 0)

    def test_frame_rules_flag_derived_pixels_and_a_false_empty_state(self):
        report = self.rules(dc, "frame")[1]
        self.assertEqual(sorted(f["rule"] for f in report["findings"]), ["frame-derived-px", "frame-false-empty"])

    def test_the_functional_type_floor_flags_10_9px_and_passes_11px(self):
        self.assertEqual([f["rule"] for f in self.rules(dc, "type/a.css")[1]["findings"]], ["type-below-functional-floor"])
        self.assertEqual(self.rules(dc, "type/b.css")[0], 0)
        control = broken(off("px > 0 and not passes_cut(px, floor)"), off("not match(example)"))
        self.assertEqual(self.rules(control, "type/a.css")[0], 0)

    def test_a_finish_rule_is_answered_not_blocking(self):
        code, report = self.rules(dc, "finish")
        self.assertEqual((code, [f["rule"] for f in report["answer"]]), (0, ["finish-inline-style"]))
        control = broken(('(answer if item["tier"] == "finish" else findings).append(item)', "findings.append(item)"))
        self.assertEqual(self.rules(control, "finish")[0], 1)

    def test_a_rule_that_disagrees_with_its_examples_refuses_the_file(self):
        data = json.loads((REFERENCES / "rules.json").read_text(encoding="utf-8"))
        rule = next(r for r in data["rules"] if r["id"] == "tell-eyebrow")
        rule["must_match"] = ["<h2>no eyebrow here</h2>"]
        self.write({"bad-rules.json": data})
        code, report = self.rules(dc, "site", extra=("--rules", self.p("bad-rules.json")))
        self.assertEqual((code, report["status"]), (2, "not-run"))
        self.assertIn("tell-eyebrow", report["error"])
        control = broken(off("not match(example)"))
        self.assertNotEqual(self.rules(control, "site", extra=("--rules", self.p("bad-rules.json")))[1]["status"],
                            "not-run")

    def test_tell_messages_never_prescribe_a_font_or_colour(self):
        data = json.loads((REFERENCES / "rules.json").read_text(encoding="utf-8"))

        def prescribes(message):
            return bool(re.search(r"(?i)\binstead\b|\buse (?:the )?(?:font|colou?r|#)|\bswitch to\b", message))
        for rule in (r for r in data["rules"] if r.get("tell")):
            with self.subTest(rule=rule["id"]):
                self.assertFalse(prescribes(rule["message"]), rule["message"])
                self.assertIn(rule["status"], ("flagged", "warned", "retired"))
                self.assertIn(rule["basis"], ("measured", "taste", "brand"))
                self.assertRegex(rule["since"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(prescribes("pick Inter instead"), "the control: a prescribing message is caught")


class ThresholdTests(Tree):
    files = {"a.css": ".legal { font-size: 10.9px; }\n", "brief.md": "A page.\n"}

    def planted(self, change):
        data = json.loads((REFERENCES / "thresholds.json").read_text(encoding="utf-8"))
        change(data["thresholds"]["functional-text-min-px"])
        self.write({"t.json": data})
        return self.p("t.json")

    def rules(self, module, thresholds):
        return run(module, "rules", self.p("a.css"), "--brief", self.p("brief.md"), "--thresholds", thresholds)

    def test_a_number_with_no_basis_or_date_is_refused(self):
        path = self.planted(lambda t: (t.pop("basis"), t.pop("date")))
        code, report = self.rules(dc, path)
        self.assertEqual((code, report["status"]), (2, "not-run"))
        self.assertIn("functional-text-min-px", report["error"])
        control = broken(off("not text_value(item.get(key))"))
        self.assertNotEqual(self.rules(control, path)[1]["status"], "not-run")

    def test_a_fixture_on_the_wrong_side_of_the_cut_is_refused(self):
        path = self.planted(lambda t: t["fixtures"].update(fails=11.5))
        self.assertEqual(self.rules(dc, path)[0], 2)
        control = broken(off('passes_cut(fixtures["fails"], item) or not passes_cut(fixtures["passes"], item)'))
        self.assertNotEqual(self.rules(control, path)[1]["status"], "not-run")

    def test_the_shipped_thresholds_load_and_every_cut_has_both_fixtures(self):
        data = json.loads((REFERENCES / "thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(dc.threshold_problems(data), [])
        for name, item in data["thresholds"].items():
            with self.subTest(threshold=name):
                if item["kind"] == "cut":
                    self.assertFalse(dc.passes_cut(item["fixtures"]["fails"], item))
                    self.assertTrue(dc.passes_cut(item["fixtures"]["passes"], item))


PRICING = ("<p class=\"text-xs uppercase tracking-widest\">Plans</p><h2>Pricing that scales</h2>\n"
           "<p class=\"stat\">10,000+ teams</p>\n")
EYEBROW = "<p class=\"text-xs uppercase tracking-widest\">Plans</p><h2>Pricing that scales</h2>"
GOOD_REASON = "Pricing tiers are labelled in caps to match the printed rate card"


def waiver(rule="tell-eyebrow", reason=GOOD_REASON, text=EYEBROW, page="pricing.html"):
    return {"rule": rule, "page": page, "reason": reason, "evidence": {"file": "pricing.html", "text": text}}


class WaiverTests(Tree):
    files = {"pricing.html": PRICING, "brief.md": "A pricing page.\n"}

    def waivers(self, module, *items):
        self.write({"w.json": {"format": "westack-design-waivers-1", "waivers": list(items)}})
        return run(module, "waivers", self.p("w.json"))

    def rejected(self, report):
        return sorted(code for r in report.get("rejected", []) for code in r["problems"])

    def test_floor_boilerplate_and_copied_reasons_are_rejected_and_the_gate_still_fires(self):
        items = [waiver("honesty-unsourced-stat", "The pricing stat comes from the sales deck the client approved",
                        "<p class=\"stat\">10,000+ teams</p>"),
                 waiver(reason="Design choice for the pricing page"), waiver(), waiver()]
        code, report = self.waivers(dc, *items)
        self.assertEqual(code, 1)
        self.assertEqual(self.rejected(report),
                         ["floor-not-waivable", "reason-boilerplate", "reason-copied", "reason-copied"])
        code, report = run(dc, "rules", self.p("pricing.html"), "--brief", self.p("brief.md"), "--waivers", self.p("w.json"))
        self.assertEqual(sorted(f["code"] for f in report["findings"] if f["code"] != "waiver-rejected"),
                         ["honesty-unsourced-stat", "tell-eyebrow"])
        self.assertEqual(codes(report).count("waiver-rejected"), 4)
        leaky = broken(("w for w in accepted if", "w for w in accepted + rejected if"))
        report = run(leaky, "rules", self.p("pricing.html"), "--brief", self.p("brief.md"), "--waivers", self.p("w.json"))[1]
        self.assertNotIn("tell-eyebrow", codes(report))

    def test_each_rejection_has_its_control(self):
        for edit, item in ((off('rule["tier"] == "floor"'), waiver("honesty-unsourced-stat",
                            "The pricing stat comes from the sales deck the client approved", "<p class=\"stat\">10,000+ teams</p>")),
                           (off("boilerplate(reason, page)"), waiver(reason="Design choice for the pricing page")),
                           (off("not names_page(reason, page)"), waiver(reason="Tiers are labelled in caps to match the printed rate card")),
                           (off("not guard_ok"), waiver(text="<p class=\"eyebrow\">Not on the page</p><h2>x</h2>"))):
            with self.subTest(edit=edit[0]):
                self.assertEqual(self.waivers(dc, item)[0], 1)
                self.assertEqual(self.waivers(broken(edit), item)[0], 0)
        self.assertEqual(self.waivers(broken(off("reasons[key] > 1")), waiver(), waiver())[0], 0)

    def test_a_valid_waiver_lifts_a_reflex_finding_and_nothing_else(self):
        code, report = self.waivers(dc, waiver())
        self.assertEqual((code, len(report["accepted"])), (0, 1))
        report = run(dc, "rules", self.p("pricing.html"), "--brief", self.p("brief.md"), "--waivers", self.p("w.json"))[1]
        self.assertEqual(codes(report), ["honesty-unsourced-stat"])
        self.assertEqual([f["rule"] for f in report["waived"]], ["tell-eyebrow"])


BEFORE = """<html lang="en"><body>
<header id="top"><nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav></header>
<section id="hero"><h1>Close the books</h1><a href="/signup" data-testid="cta">Start</a></section>
<section id="signup"><form id="join" action="/api/join" method="post"><input name="email" type="email">
<input name="company"><button type="submit" onclick="track('join')">Join</button></form></section>
<footer id="foot"><script src="/analytics.js"></script><script>window.ready = true;</script></footer>
</body></html>
"""


class InventoryTests(Tree):
    files = {"before.html": BEFORE,
             "after.html": BEFORE.replace("<input name=\"company\">", ""),
             "moved.html": BEFORE.replace(
                 "<section id=\"hero\"><h1>Close the books</h1><a href=\"/signup\" data-testid=\"cta\">Start</a></section>\n",
                 "").replace("</section>\n<footer", "</section>\n<section id=\"hero\"><h1>Close the books</h1>"
                             "<a href=\"/signup\" data-testid=\"cta\">Start</a></section>\n<footer")}

    def test_the_wiring_is_inventoried(self):
        code, report = run(dc, "inventory", self.p("before.html"), self.p("before.html"))
        self.assertEqual(code, 0)
        self.assertEqual(report["counts"], {"link": 3, "form": 1, "field": 2, "handler": 1, "hook": 1, "script": 2})

    def test_a_deleted_field_fails_unless_recorded_as_dropped(self):
        code, report = run(dc, "inventory", self.p("before.html"), self.p("after.html"))
        self.assertEqual((code, [f["where"] for f in report["findings"]]), (1, ["field:company"]))
        self.write({"dropped.json": {"dropped": [{"key": "field:company", "reason": "the user asked to remove it",
                                                  "evidence": "turn 14"}]}})
        code, report = run(dc, "inventory", self.p("before.html"), self.p("after.html"), "--dropped", self.p("dropped.json"))
        self.assertEqual((code, report["dropped"][0]["key"]), (0, "field:company"))
        self.write({"bare.json": {"dropped": [{"key": "field:company"}]}})
        report = run(dc, "inventory", self.p("before.html"), self.p("after.html"), "--dropped", self.p("bare.json"))[1]
        self.assertEqual(sorted(codes(report)), ["drop-unreasoned", "missing"])
        control = broken(off('not (text_value(entry.get("reason")) and text_value(entry.get("evidence")))'))
        self.assertEqual(run(control, "inventory", self.p("before.html"), self.p("after.html"), "--dropped", self.p("bare.json"))[0], 0)
        control = broken(off("key not in after_items and key not in dropped_ok"))
        self.assertEqual(run(control, "inventory", self.p("before.html"), self.p("after.html"))[0], 0)

    def test_a_polish_that_moves_sections_is_flagged(self):
        code, report = run(dc, "inventory", self.p("before.html"), self.p("moved.html"), "--depth", "polish")
        self.assertEqual((code, codes(report)), (1, ["sections-moved"]))
        self.assertEqual(run(dc, "inventory", self.p("before.html"), self.p("moved.html"), "--depth", "full")[0], 0)
        control = broken(off('depth != "full" and common_before != common_after'))
        self.assertEqual(run(control, "inventory", self.p("before.html"), self.p("moved.html"), "--depth", "polish")[0], 0)


class RecordTests(Tree):
    files = {"record.md": record_md()}

    def record(self, module, *extra, name="record.md"):
        return run(module, "record", self.p(name), *extra)

    def test_a_complete_record_is_clean_and_its_derived_file_regenerates(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dc.main(["record", str(self.p("record.md")), "--emit", "css"]), 0)
        css = out.getvalue()
        self.assertTrue(css.startswith("/* generated from record.md"))
        self.assertIn("--color-primary: #1D4ED8;", css)
        self.write({"theme.css": css})
        code, report = self.record(dc, "--derived", self.p("theme.css"))
        self.assertEqual((code, report["status"]), (0, "clean"), report)
        self.write({"theme.css": css.replace("#1D4ED8", "#1E40AF")})
        code, report = self.record(dc, "--derived", self.p("theme.css"))
        self.assertEqual(codes(report), ["derived-drift"])
        self.assertNotEqual(report["derived"][0]["expected_sha256"], report["derived"][0]["actual_sha256"])
        control = broken(off("expected_hash != actual_hash"))
        self.assertEqual(self.record(control, "--derived", self.p("theme.css"))[0], 0)

    def test_a_duplicate_key_fails(self):
        text = record_md().replace('"spacing": {', '"spacing": {\n    "2": "10px",', 1)
        self.write({"dupe.md": text, "two.md": record_md(extra_blocks=['{"colors": {"accent": "#FF6A6A"}}'])})
        self.assertEqual(codes(self.record(dc, name="dupe.md")[1]), ["duplicate-key"])
        self.assertEqual(codes(self.record(dc, name="two.md")[1]), ["duplicate-key"])
        control = broken(off("key in pairs_seen"))
        self.assertEqual(codes(self.record(control, name="dupe.md")[1]), [])

    def test_a_misspelt_group_names_the_right_key_and_token_like_data_is_flagged(self):
        tokens = dict(RECORD_JSON, colours={"primary": "#112233"}, palette2={"x": "#ff0000"},
                      transitions={"easing": "ease-out", "duration": "200ms"})
        self.write({"typo.md": record_md(tokens)})
        report = self.record(dc, name="typo.md")[1]
        found = {f["code"]: f["message"] for f in report["findings"]}
        self.assertEqual(sorted(found), ["key-typo", "token-like-ignored"])
        self.assertIn("'colors'", found["key-typo"])
        self.assertIn("palette2", found["token-like-ignored"])
        self.assertNotIn("key-typo", codes(self.record(broken(off("near[0][0] <= 2")), name="typo.md")[1]))
        self.assertNotIn("token-like-ignored", codes(self.record(broken(off("token_like(value)")), name="typo.md")[1]))

    def test_an_absent_section_needs_a_declared_reason(self):
        self.write({"gap.md": record_md(sections=("Overview", "Colors", "Typography", "Layout", "Components", "Do and Don't")),
                    "contra.md": record_md(dict(RECORD_JSON, omitted={"Colors": "none yet", "Elevation": "flat"}))})
        self.assertEqual(codes(self.record(dc, name="gap.md")[1]), ["section-missing"])
        self.assertEqual(codes(self.record(dc, name="contra.md")[1]), ["omission-contradicts"])
        self.assertEqual(codes(self.record(broken(off("name not in seen and name not in omitted")), name="gap.md")[1]), [])

    def test_unresolved_and_cyclic_references_are_errors(self):
        tokens = json.loads(json.dumps(RECORD_JSON))
        tokens["colors"].update({"link": "{colors.primry}", "a": "{colors.b}", "b": "{colors.a}"})
        self.write({"refs.md": record_md(tokens)})
        found = codes(self.record(dc, name="refs.md")[1])
        self.assertIn("unresolved-ref", found)
        self.assertIn("ref-cycle", found)
        self.assertNotIn("ref-cycle", codes(self.record(broken(off("path in seen")), name="refs.md")[1]))
        self.assertNotIn("unresolved-ref", codes(self.record(broken(off("target is MISSING")), name="refs.md")[1]))

    def test_record_values_must_have_shipped_and_recur(self):
        tokens = {"format": "westack-design-record-1",
                  "colors": {"primary": "#1D4ED8", "foreground": "#111827", "accent": "#FF6A6A", "muted": "#F3F4F6"},
                  "omitted": {"Elevation": "flat"}}
        self.write({"shipped.md": record_md(tokens), "build/app.css": ":root{--color-primary:#1D4ED8}\n"
                    ".a{color:var(--color-primary)}\n.b{background:var(--color-primary)}\n.c{color:#111827}\n"
                    ".d{border-color:#111827}\n.e{background:#F3F4F6}\n"})
        report = self.record(dc, "--built", self.p("build"), name="shipped.md")[1]
        self.assertEqual(sorted((f["code"], f["where"]) for f in report["findings"]),
                         [("token-not-in-build", "colors.accent"), ("token-single-sighting", "colors.muted")])
        self.assertNotIn("token-not-in-build", codes(self.record(broken(off("uses == 0")), "--built", self.p("build"), name="shipped.md")[1]))
        control = broken(off("uses == 1"))
        self.assertNotIn("token-single-sighting", codes(self.record(control, "--built", self.p("build"), name="shipped.md")[1]))

    def test_a_new_token_and_variant_are_proposals_never_hidden(self):
        newer = json.loads(json.dumps(RECORD_JSON))
        newer["colors"]["brand"] = "#AA3355"
        newer["components"]["button-brand"] = {"backgroundColor": "{colors.brand}"}
        self.write({"old.md": record_md(), "new.md": record_md(newer)})
        code, report = self.record(dc, "--baseline", self.p("old.md"), name="new.md")
        self.assertEqual((code, report["status"]), (1, "proposals"))
        self.assertEqual([(p["kind"], p["name"]) for p in report["proposals"]],
                         [("token", "colors.brand"), ("variant", "components.button-brand")])
        control = broken(('"proposals" if proposals else "clean"', '"clean"'))
        self.assertEqual(self.record(control, "--baseline", self.p("old.md"), name="new.md")[0], 0)


def critique(**changes):
    base = {"format": "westack-design-report-1", "mode": "critique",
            "first_line": "DEGRADED: no browser this session, so DG-23 and DG-24 were not run; findings come from source.",
            "browser": "none", "phases": ["judgment", "detectors"], "captures": [],
            "findings": [{"id": "F1", "claim": "The hover button text drops to 3.68:1.", "kind": "contrast",
                          "level": "present", "rule": "DG-14: text needs 4.5:1 (thresholds.json contrast-text)",
                          "path": "record components.button-primary-hover, used by styles.css .btn:hover",
                          "correction": "darken the hover background until white text reaches 4.5:1",
                          "evidence": [{"kind": "source", "ref": "designcheck.py contrast receipt R2"}]}],
            "claimed": [{"claim": "The pricing table may lack prominence.", "kind": "prominence", "level": "claimed",
                         "evidence": [{"kind": "source", "ref": "index.html:40"}]}],
            "runtime": [{"id": "DG-23", "status": "not-run", "why": "no browser tool this session"},
                        {"id": "DG-24", "status": "not-run", "why": "no browser tool this session"},
                        {"id": "DG-26", "status": "not-run", "why": "no browser or recorder this session"}]}
    base.update(changes)
    return base


ENV = {"os": "windows-11", "browser": "chromium 140", "headless": True, "dpr": 1}


def scores(rows, maximum=None, total=None, checked_for="claude-opus-5-5"):
    criteria = [{"id": "Q%d" % n, "name": "criterion %d" % n, "weight": 1,
                 "anchors": ["a %d-point example" % 0, "a %d-point example" % 3]} for n in range(1, 11)]
    counted = [r["score"] for r in rows if r["score"] != "n/a"]
    return {"model": "claude-opus-5-5", "rubric": {"anchors_checked_for": checked_for, "criteria": criteria},
            "rows": rows, "max": 3 * len(counted) if maximum is None else maximum,
            "total": sum(counted) if total is None else total,
            "na": [r["criterion"] for r in rows if r["score"] == "n/a"]}


def rows(**special):
    out = []
    for n in range(1, 11):
        row = {"criterion": "Q%d" % n, "score": 2}
        row.update(special.get("Q%d" % n, {}))
        out.append(row)
    return out


class ReportTests(Tree):
    def report(self, module, data):
        self.write({"report.json": data})
        return run(module, "report", self.p("report.json"))

    def finding(self, **changes):
        item = json.loads(json.dumps(critique()["findings"][0]))
        item.update(changes)
        return item

    def test_a_degraded_source_only_critique_is_clean(self):
        code, report = self.report(dc, critique())
        self.assertEqual((code, report["status"]), (0, "clean"), report)

    def test_each_check_has_its_control(self):
        cases = [
            ("no-evidence", off("not evidence"), critique(findings=[self.finding(evidence=[])])),
            ("unproven", off("missing_proofs"), critique(findings=[self.finding(correction="")])),
            ("level-too-high", off('kind in RENDERED_KINDS and level != "claimed" and not rendered'),
             critique(findings=[self.finding(kind="prominence")])),
            ("runtime-without-browser", off('browser == "none" and status != "not-run"'),
             critique(runtime=[{"id": "DG-23", "status": "passed", "evidence": "looked fine"},
                               {"id": "DG-24", "status": "not-run", "why": "no browser"},
                               {"id": "DG-26", "status": "not-run", "why": "no browser"}])),
            ("runtime-unreported", off("entry is None"), critique(runtime=[{"id": "DG-23", "status": "not-run", "why": "x"}])),
            ("numeric-from-screenshot", off('kind in NUMERIC_KINDS and kinds <= {"screenshot"}'),
             critique(findings=[self.finding(kind="width", level="observed", evidence=[{"kind": "screenshot", "ref": "s1.png"}])])),
            ("motion-from-stills", off('kind == "motion" and "recording" not in kinds'),
             critique(findings=[self.finding(kind="motion", level="observed", evidence=[{"kind": "screenshot", "ref": "t0.png"},
                                                                                         {"kind": "screenshot", "ref": "t1.png"}])])),
            ("contradicted-not-dropped", off('(item.get("rendered") or {}).get("agrees") is False'),
             critique(findings=[self.finding(rendered={"agrees": False, "ref": "pixel sample P3 gives 7.1:1"})])),
            ("baseline-unlisted", off('baseline.get("changed") is True and baseline.get("file") not in listed'),
             critique(environment=ENV, baselines=[{"file": "home.png", "changed": True, "environment": ENV}])),
            ("baseline-environment-mismatch", off("differs"),
             critique(environment=ENV, baselines=[{"file": "home.png", "changed": False, "environment": dict(ENV, dpr=2)}])),
            ("banner-missing", off('degraded and not first.startswith("DEGRADED")'),
             critique(first_line="Method: source read and designcheck.py")),
            ("detector-first", off('phases.index("detectors") < phases.index("judgment")'),
             critique(phases=["detectors", "judgment"])),
            ("recapture-with-findings", off('invalid_captures and (findings_list or disposition != "recapture")'),
             critique(browser="host:browser", captures=[{"id": "C1", "file": "shot.png", "valid": False, "problem": "blank"}])),
            ("wrong-denominator", ("counted = [w for w, score in weighed if score != \"n/a\"]",
                                   "counted = [w for w, score in weighed]"),
             critique(scores=scores(rows(Q3={"score": "n/a", "reason": "no form"}, Q7={"score": "n/a", "reason": "no data"}),
                                    maximum=30))),
            ("unsure-not-lower", off("score != min(candidates)"), critique(scores=scores(rows(Q1={"score": 3, "candidates": [2, 3]})))),
            ("not-worst-instance", off("score != min(instance_scores)"),
             critique(scores=scores(rows(Q2={"score": 2, "instances": [{"where": "a", "score": 3}, {"where": "b", "score": 1}]})))),
            ("anchors-unchecked", off("checked_for != model"), critique(scores=scores(rows(), checked_for="claude-opus-4"))),
        ]
        for code, edit, data in cases:
            with self.subTest(code=code):
                self.assertIn(code, codes(self.report(dc, data)[1]))
                self.assertNotIn(code, codes(self.report(broken(edit), data)[1]))

    def test_n_a_rows_leave_the_denominator(self):
        data = critique(scores=scores(rows(Q3={"score": "n/a", "reason": "no form"}, Q7={"score": "n/a", "reason": "no data"})))
        code, report = self.report(dc, data)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["score_line"], "16/24 (n/a: Q3, Q7)")
        bad = critique(scores=scores(rows(Q3={"score": "n/a"})))
        self.assertIn("na-unreasoned", codes(self.report(dc, bad)[1]))

    def test_a_score_is_never_evidence(self):
        data = critique(findings=[self.finding(evidence=[{"kind": "score", "ref": "Q4 scored 1"}])])
        self.assertIn("score-as-evidence", codes(self.report(dc, data)[1]))
        self.assertNotIn("score-as-evidence", codes(self.report(broken(off('kinds == {"score"}')), data)[1]))

    def test_measured_numbers_recorded_motion_and_listed_baselines_pass(self):
        data = critique(environment=ENV, findings=[
            self.finding(kind="width", level="observed", evidence=[{"kind": "measurement", "ref": "bbox card-3: 276.6px"}]),
            self.finding(id="F2", kind="motion", level="observed", evidence=[{"kind": "recording", "ref": "frames F12-F40",
                                                                              "class": "sampled"}])],
            baselines=[{"file": "home.png", "changed": True, "environment": dict(ENV)}],
            proposals=[{"kind": "baseline", "name": "home.png"}])
        code, report = self.report(dc, data)
        self.assertEqual((code, report["status"]), (0, "clean"), report)


class MotionTests(Tree):
    POLICY = {"scale": "never", "overshoot": "never", "pointer_following": "allowed", "zoom_transition": "never",
              "except": {"scale": ["dock"]}, "decided_by": "user", "date": "2026-10-30",
              "reason": "the product's motion policy, recorded from the user's own list"}
    files = {"ui/app.css": ".dock-item:hover { transform: scale(1.5); }\n.card:hover { transform: scale(1.05); }\n"
                           ".sheet { transition: transform 300ms cubic-bezier(.34, 1.56, .64, 1); }\n",
             "ui/move.js": "window.addEventListener('pointermove', e => { blob.style.transform = 'translate(' + e.clientX + 'px)'; });\n",
             "brief.md": "A finance dashboard.\n",
             "media/app.css": "@media (prefers-color-scheme: dark) { .x { color: #F4F1EA; } }\n"
                              "@media print { .y { background: #D97757; } }\n",
             "media-base/app.css": ".x { background: #F4F1EA; }\n@media print { .y { background: #D97757; } }\n",
             "human/index.html": "<p class=\"uppercase\">Volume 3</p>\n<h2>Letters from the archive</h2>\n",
             "target/index.html": "<p class=\"text-xs uppercase tracking-widest\">Why teams switch</p>\n<h2>Built for the close</h2>\n"}

    def setUp(self):
        super().setUp()
        self.write({"record.md": record_md(dict(RECORD_JSON, motion=self.POLICY))})

    def rules(self, module, src, *extra):
        return run(module, "rules", self.p(src), "--brief", self.p("brief.md"), *extra)

    def test_the_project_policy_is_checked_with_its_exceptions(self):
        report = self.rules(dc, "ui", "--record", self.p("record.md"))[1]
        policy = sorted((f["rule"], f["where"].rsplit(":", 1)[1]) for f in report["findings"] if f["rule"].startswith("policy-"))
        self.assertEqual(policy, [("policy-overshoot", "3"), ("policy-scale", "2")], "the dock is excepted; pointer allowed")
        self.assertEqual([(f["rule"], f["excepted_by"]) for f in report["excepted_by_policy"]], [("policy-scale", "dock")])
        hover = sorted(f["where"].rsplit(":", 1)[1] for f in report["findings"] if f["rule"] == "motion-hover-box")
        self.assertEqual(hover, ["1", "2"], "the default holds everywhere; the dock needs a waiver on the record")
        control = broken(off("excepted_by"))
        self.assertIn(("policy-scale", "1"), [(f["rule"], f["where"].rsplit(":", 1)[1])
                                              for f in self.rules(control, "ui", "--record", self.p("record.md"))[1]["findings"]])

    def test_without_a_recorded_policy_the_policy_rules_are_not_run(self):
        report = self.rules(dc, "ui")[1]
        self.assertFalse(any(f["rule"].startswith("policy-") for f in report["findings"]))
        self.assertEqual(sorted(p["rule"] for p in report["policy_not_run"]),
                         ["policy-overshoot", "policy-pointer-following", "policy-scale"])

    def test_the_motion_policy_shape_is_checked(self):
        self.assertEqual(codes(run(dc, "record", self.p("record.md"))[1]), [])
        bad = dict(self.POLICY, scale="sometimes", wobble="never")
        del bad["decided_by"]
        self.write({"bad.md": record_md(dict(RECORD_JSON, motion=bad))})
        found = run(dc, "record", self.p("bad.md"))[1]["findings"]
        self.assertEqual(sorted(f["where"] for f in found), ["motion.decided_by", "motion.scale", "motion.wobble"])
        control = broken(off('value not in ("never", "allowed")'))
        self.assertNotIn("motion.scale", [f["where"] for f in run(control, "record", self.p("bad.md"))[1]["findings"]])

    def test_media_scoped_rules_are_never_combined(self):
        self.assertNotIn("tell-cream-terracotta", codes(self.rules(dc, "media")[1]))
        self.assertIn("tell-cream-terracotta", codes(self.rules(dc, "media-base")[1]), "base rules apply in print too")
        control = broken(("for scope, part in media_scopes(text):", 'for scope, part in [("merged", text)]:'))
        self.assertIn("tell-cream-terracotta", codes(self.rules(control, "media")[1]))

    def test_a_human_control_page_reports_false_positives_and_holds_the_rule(self):
        code, report = self.rules(dc, "target", "--control", self.p("human"))
        self.assertEqual(report["calibration"]["false_positives"], {"tell-eyebrow": 1})
        self.assertEqual([f["rule"] for f in report["review_before_gating"]], ["tell-eyebrow"])
        self.assertEqual(code, 0)
        uncalibrated = self.rules(dc, "target")[1]
        self.assertEqual(uncalibrated["calibration"]["status"], "not-run")
        control = broken(off("control_hits"))
        self.assertEqual(self.rules(control, "target", "--control", self.p("human"))[0], 1)


# ---- follow-up: DG-33 capture classes, DG-35 reference records, DG-34 and DG-36 runtime entries --------------------

def motion_finding(**changes):
    item = {"id": "F2", "claim": "The drawer opens on cubic-bezier(.3, 1.4, .6, 1), which overshoots its resting place.",
            "kind": "motion", "level": "observed", "curve": "cubic-bezier(.3, 1.4, .6, 1)",
            "rule": "the record's motion policy: overshoot never",
            "path": "drawer.css .drawer transition, started by menu.js",
            "correction": "a curve whose control points stay between 0 and 1",
            "evidence": [{"kind": "recording", "ref": "settled steps S1-S6 of the drawer opening", "class": "sampled"}]}
    item.update(changes)
    return item


BROWSED_RUNTIME = [{"id": "DG-23", "status": "not-run", "why": "not part of this review"},
                   {"id": "DG-24", "status": "not-run", "why": "not part of this review"},
                   {"id": "DG-26", "status": "passed", "evidence": "drawer recording R1"}]


class CaptureClassTests(Tree):
    """DG-33: each motion fact names its capture class, and its level never outruns what that class can show."""

    def report(self, module, *findings):
        self.write({"report.json": critique(browser="host:browser", runtime=BROWSED_RUNTIME, findings=list(findings))})
        return run(module, "report", self.p("report.json"))

    def test_a_curve_read_off_samples_is_lowered_to_claimed(self):
        code, report = self.report(dc, motion_finding())
        self.assertEqual(code, 1, report)
        self.assertIn("level-above-capture", codes(report))
        self.assertEqual(report["lowered"], [{"id": "F2", "from": "observed", "to": "claimed"}])
        exact = motion_finding(evidence=[{"kind": "recording", "ref": "the drawer's keyframes and timing from the "
                                          "animation list", "class": "exact"}])
        code, report = self.report(dc, exact)
        self.assertEqual((code, report["status"], report["lowered"]), (0, "clean", []), report)
        control = broken(('CURVE_CEILING.get(cls, "claimed") if curve else ', ""))
        report = self.report(control, motion_finding())[1]
        self.assertEqual((codes(report), report["lowered"]), ([], []), "a copy without the class check accepts it")

    def test_a_curve_named_only_in_the_claim_still_counts(self):
        bare = motion_finding()
        del bare["curve"]
        self.assertEqual(self.report(dc, bare)[1]["lowered"], [{"id": "F2", "from": "observed", "to": "claimed"}])
        control = broken((' or CURVE_RE.search(str(item.get("claim") or "")) is not None', ""))
        self.assertEqual(self.report(control, bare)[1]["lowered"], [])

    def test_recovered_source_holds_a_curve_at_present(self):
        evidence = [{"kind": "recording", "ref": "settled steps S1-S6", "class": "sampled"},
                    {"kind": "source", "ref": "drawer.css:14, recovered through the page's source map", "class": "recovered"}]
        self.assertEqual(self.report(dc, motion_finding(evidence=evidence, level="present"))[0], 0)
        report = self.report(dc, motion_finding(evidence=evidence))[1]
        self.assertEqual(report["lowered"], [{"id": "F2", "from": "observed", "to": "present"}])
        control = broken(('CURVE_CEILING = {"exact": "observed", "recovered": "present"}',
                          'CURVE_CEILING = {"exact": "observed", "recovered": "observed"}'))
        self.assertEqual(self.report(control, motion_finding(evidence=evidence))[1]["lowered"], [])

    def test_each_motion_evidence_item_names_its_class(self):
        unclassed = motion_finding(claim="The card shifts 6px on hover at a device pixel ratio of 1.",
                                   rule="DG-25 (a): hover never changes a target's box",
                                   path="styles.css .card:hover sets padding", correction="keep the padding; change colour",
                                   evidence=[{"kind": "recording", "ref": "bounding boxes B1 and B2, before and during hover"}])
        del unclassed["curve"]
        code, report = self.report(dc, unclassed)
        self.assertEqual(code, 1)
        self.assertIn("capture-class-missing", codes(report))
        self.assertEqual(report["lowered"], [{"id": "F2", "from": "observed", "to": "claimed"}])
        sampled = dict(unclassed, evidence=[dict(unclassed["evidence"][0], **{"class": "sampled"})])
        self.assertEqual(self.report(dc, sampled)[0], 0, "a box is no curve: samples hold it at observed")
        for value in ("measured", ["exact"]):
            odd = dict(unclassed, evidence=[dict(unclassed["evidence"][0], **{"class": value})])
            self.assertIn("capture-class-missing", codes(self.report(dc, odd)[1]), "an unknown class names none")
        self.assertNotIn("capture-class-missing", codes(self.report(broken(off("unclassed")), unclassed)[1]))


REFERENCE = {"goal": "make the month-end close feel settled", "source": "https://studio.example/ledger-close",
             "date": "2026-10-31", "viewport": "1440x900", "trigger": "scroll past the summary",
             "response": "the totals count up once, then hold", "class": "exact",
             "licence": "the site's content is all rights reserved, so the mechanism only",
             "cost": "one transition and no library", "why": "the motion ends on the figure people check",
             "avoid_when": "figures that update live, where a count-up would replay"}


class ReferenceRecordTests(Tree):
    """DG-35: each of a direction's references carries the whole reference record."""

    def record(self, module, refs):
        self.write({"record.md": record_md(dict(RECORD_JSON, references=refs))})
        return run(module, "record", self.p("record.md"))

    def test_a_complete_reference_is_clean(self):
        code, report = self.record(dc, [REFERENCE])
        self.assertEqual((code, codes(report)), (0, []), report)

    def test_a_reference_without_a_licence_or_a_when_not_to_use_fails(self):
        control = broken(("for key in REFERENCE_FIELDS if", 'for key in ("source",) if'))
        for field in ("licence", "avoid_when"):
            with self.subTest(field=field):
                thin = {k: v for k, v in REFERENCE.items() if k != field}
                code, report = self.record(dc, [thin])
                self.assertEqual((code, codes(report)), (1, ["reference-incomplete"]))
                self.assertIn(field, report["findings"][0]["message"])
                self.assertEqual(self.record(control, [thin])[0], 0, "a copy that checks only the URL passes it")

    def test_more_than_three_references_fail(self):
        self.assertEqual(codes(self.record(dc, [REFERENCE] * 4)[1]), ["references-count"])
        self.assertEqual(codes(self.record(dc, [REFERENCE] * 3)[1]), [])
        self.assertEqual(codes(self.record(broken(off("len(refs) > 3")), [REFERENCE] * 4)[1]), [])

    def test_a_bad_date_or_capture_class_fails(self):
        odd = dict(REFERENCE, date="last week", **{"class": "screenshot"})
        report = self.record(dc, [odd])[1]
        self.assertEqual(sorted(f["where"] for f in report["findings"]), ["references[0].class", "references[0].date"])
        for condition, where in (('text_value(ref.get("date")) and not ISO_DATE.fullmatch(ref["date"].strip())', "date"),
                                 ('text_value(ref.get("class")) and ref["class"] not in CLASS_CEILING', "class")):
            with self.subTest(field=where):
                found = [f["where"] for f in self.record(broken(off(condition)), [odd])[1]["findings"]]
                self.assertNotIn("references[0]." + where, found)

    def test_references_that_are_not_a_list_are_named(self):
        self.assertEqual(codes(self.record(dc, REFERENCE)[1]), ["references-shape"])
        self.assertNotIn("references-shape", codes(self.record(broken(off("not isinstance(refs, list)")), REFERENCE)[1]))


class ConditionalRuntimeTests(Tree):
    """DG-34 and DG-36 run only when a reference is classed or compared. Reported, they follow the browser rule, and a
    comparison counts only when both runs finish every step; an early stop is blocked at its step (DG-36)."""

    def report(self, module, entry, browser="host:browser"):
        self.write({"report.json": critique(browser=browser, runtime=critique()["runtime"] + [entry])})
        return run(module, "report", self.p("report.json"))

    def test_without_a_browser_they_are_not_run(self):
        claimed = {"id": "DG-34", "status": "passed", "evidence": "the fluid is a looping video V1"}
        self.assertIn("runtime-without-browser", codes(self.report(dc, claimed, browser="none")[1]))
        self.assertEqual(self.report(dc, dict(claimed, status="not-run", why="no browser"), browser="none")[0], 0)
        self.assertEqual(self.report(dc, claimed)[0], 0, "with a browser and its evidence it stands")
        control = broken(("for check_id in RUNTIME_IDS:", "for check_id in REQUIRED_RUNTIME:"))
        self.assertNotIn("runtime-without-browser", codes(self.report(control, claimed, browser="none")[1]))

    def test_an_early_stop_is_blocked_at_its_step(self):
        stopped = {"id": "DG-36", "status": "blocked", "steps": 5, "completed": {"build": 5, "reference": 2},
                   "step": 3, "why": "the reference timed out at step 3"}
        self.assertEqual(self.report(dc, stopped)[0], 0)
        no_step = {k: v for k, v in stopped.items() if k != "step"}
        self.assertIn("blocked-without-step", codes(self.report(dc, no_step)[1]))
        control = broken(off('status == "blocked" and not (number(entry.get("step")) and entry["step"] >= 1)'))
        self.assertNotIn("blocked-without-step", codes(self.report(control, no_step)[1]))

    def test_a_comparison_of_the_steps_it_has_is_not_a_match(self):
        partial = {"id": "DG-36", "status": "passed", "evidence": "steps 1 and 2 match", "steps": 5,
                   "completed": {"build": 5, "reference": 2}}
        self.assertIn("comparison-incomplete", codes(self.report(dc, partial)[1]))
        self.assertIn("comparison-incomplete", codes(self.report(dc, dict(partial, status="failed"))[1]))
        whole = dict(partial, completed={"build": 5, "reference": 5}, evidence="steps 1 to 5 match")
        self.assertEqual(self.report(dc, whole)[0], 0)
        control = broken(off('status in ("passed", "failed") and not finished'))
        self.assertNotIn("comparison-incomplete", codes(self.report(control, partial)[1]))


# ---- follow-up: DG-38 effects off, DG-39 elapsed-time smoothing, DG-40 invariants, DG-41 capture readiness ----------

EFFECTS = ["box-shadow", "text-shadow", "filter", "backdrop-filter", "animation", "transition"]


class EffectsOffTests(Tree):
    """DG-38: a reported effects-off check names the effects it removed; a run that skipped the injection is not one."""

    def report(self, module, entry, browser="host:browser"):
        self.write({"report.json": critique(browser=browser, runtime=critique()["runtime"] + [entry])})
        return run(module, "report", self.p("report.json"))

    def test_a_check_that_removed_nothing_is_not_a_pass(self):
        whole = {"id": "DG-38", "status": "passed", "evidence": "contrast and region gaps re-measured, M4", "removed": EFFECTS}
        skipped = {k: v for k, v in whole.items() if k != "removed"}
        partial = dict(whole, removed=[e for e in EFFECTS if e != "filter"])
        control = broken(off("missing_effects"))
        self.assertEqual(self.report(dc, whole)[0], 0, self.report(dc, whole)[1])
        for bad in (skipped, partial, dict(whole, status="failed", removed=[])):
            with self.subTest(removed=bad.get("removed")):
                self.assertIn("effects-not-removed", codes(self.report(dc, bad)[1]))
                self.assertNotIn("effects-not-removed", codes(self.report(control, bad)[1]))

    def test_without_a_browser_it_is_not_run(self):
        claimed = {"id": "DG-38", "status": "passed", "evidence": "looked fine", "removed": EFFECTS}
        control = broken(("for check_id in RUNTIME_IDS:", "for check_id in REQUIRED_RUNTIME:"))
        self.assertIn("runtime-without-browser", codes(self.report(dc, claimed, browser="none")[1]))
        self.assertEqual(self.report(dc, dict(claimed, status="not-run", why="no browser"), browser="none")[0], 0)
        self.assertNotIn("runtime-without-browser", codes(self.report(control, claimed, browser="none")[1]))


class ReadinessTests(Tree):
    """DG-41: a capture waits for readiness and fails on console errors; a timed-out wait blocks it."""

    def report(self, module, captures, status=None):
        runtime = critique()["runtime"] + ([{"id": "DG-41", "status": status, "evidence": "capture log L1"}] if status else [])
        data = critique(browser="host:browser", runtime=runtime, captures=captures)
        if any(c.get("valid") is False for c in captures):
            data.update(findings=[], disposition="recapture")
        self.write({"report.json": data})
        return run(module, "report", self.p("report.json"))

    def capture(self, **changes):
        item = {"id": "C1", "file": "home-1440.png", "valid": True, "ready": "flag", "console_errors": 0}
        item.update(changes)
        return item

    def test_a_healthy_capture_passes(self):
        for ready in ("flag", "fonts-network"):
            with self.subTest(ready=ready):
                code, report = self.report(dc, [self.capture(ready=ready)], "passed")
                self.assertEqual((code, report["status"]), (0, "clean"), report)

    def test_a_timed_out_wait_blocks_the_capture(self):
        taken = [self.capture(ready="timeout")]
        control = broken(off('ready == "timeout" and item.get("valid") is not False'))
        self.assertIn("capture-not-ready", codes(self.report(dc, taken)[1]))
        self.assertNotIn("capture-not-ready", codes(self.report(control, taken)[1]), "a copy that swallows the timeout")
        blocked = [self.capture(ready="timeout", valid=False, problem="not ready: the ready flag never set")]
        self.assertEqual(codes(self.report(dc, blocked, "blocked")[1]), [])

    def test_a_console_error_fails_the_capture(self):
        erred = [self.capture(console_errors=2)]
        control = broken(off('errors and item.get("valid") is not False'))
        self.assertIn("capture-console-errors", codes(self.report(dc, erred)[1]))
        self.assertNotIn("capture-console-errors", codes(self.report(control, erred)[1]))

    def test_the_gate_status_follows_its_captures(self):
        control = broken(off('status in ("passed", "failed") and status != expected'))
        for captures, status in (([self.capture(ready="timeout", valid=False, problem="not ready")], "passed"),
                                 ([self.capture(ready="timeout", valid=False, problem="not ready")], "failed"),
                                 ([self.capture(console_errors=1, valid=False, problem="console error")], "passed"),
                                 ([{"id": "C1", "file": "home-1440.png", "valid": True}], "passed")):
            with self.subTest(captures=captures, status=status):
                self.assertIn("readiness-status", codes(self.report(dc, captures, status)[1]))
                self.assertNotIn("readiness-status", codes(self.report(control, captures, status)[1]))
        failed = [self.capture(console_errors=1, valid=False, problem="console error")]
        self.assertEqual(codes(self.report(dc, failed, "failed")[1]), [])

    def test_an_unknown_ready_value_is_named(self):
        odd = [self.capture(ready="timed-out")]
        control = broken(off("ready is not None and ready not in READY"))
        self.assertIn("captures.C1.ready", [f["where"] for f in self.report(dc, odd)[1]["findings"]])
        self.assertNotIn("captures.C1.ready", [f["where"] for f in self.report(control, odd)[1]["findings"]])


LERP_FILES = {"lerp/tick.js": "function tick() {\n  x += (target - x) * 0.1;\n  el.style.transform = 'translateX(' + x + 'px)';\n"
                              "  requestAnimationFrame(tick);\n}\n",
              "lerp/scene.jsx": "useFrame(() => { mesh.position.lerp(goal, 0.08); });\n",
              "lerp-ok/tick.js": "function tick(now) {\n  const dt = Math.min((now - last) / 1000, 0.1); last = now;\n"
                                 "  const a = 1 - Math.exp(-dt * 8);\n  x += (target - x) * a;\n"
                                 "  requestAnimationFrame(tick);\n}\n",
              "lerp-ok/once.js": "button.onclick = () => { x += (target - x) * 0.5; render(); };\n",
              "brief.md": "A finance dashboard.\n"}


class ElapsedTimeTests(Tree):
    """DG-39: smoothing toward a target by a fixed fraction each frame is a reflex finding; by elapsed time it is not."""
    files = LERP_FILES

    def rules(self, module, src, *extra):
        return run(module, "rules", self.p(src), "--brief", self.p("brief.md"), *extra)

    def test_a_per_frame_lerp_is_found_and_an_elapsed_time_one_is_not(self):
        report = self.rules(dc, "lerp")[1]
        found = sorted((f["file"].replace("\\", "/").rsplit("/", 1)[1], f["tier"]) for f in report["findings"]
                       if f["rule"] == "motion-per-frame-lerp")
        self.assertEqual(found, [("scene.jsx", "reflex"), ("tick.js", "reflex")], report)
        self.assertNotIn("motion-per-frame-lerp", [f["rule"] for f in self.rules(dc, "lerp-ok")[1]["findings"]])
        data = json.loads((REFERENCES / "rules.json").read_text(encoding="utf-8"))
        data["rules"] = [r for r in data["rules"] if r["id"] != "motion-per-frame-lerp"]
        self.write({"no-lerp.json": data})
        self.assertNotIn("motion-per-frame-lerp", codes(self.rules(dc, "lerp", "--rules", self.p("no-lerp.json"))[1]),
                         "the control: without the rule the page passes")

    def test_a_copy_of_the_rule_that_misses_its_own_example_is_refused(self):
        data = json.loads((REFERENCES / "rules.json").read_text(encoding="utf-8"))
        rule = next(r for r in data["rules"] if r["id"] == "motion-per-frame-lerp")
        self.assertIn("correctness", rule["message"] + rule.get("note", ""), "a correctness rule, not project policy")
        self.assertNotIn("policy", rule)
        rule["pattern"] = r"\bx \+= \(target - x\) \* 0\.25\b"
        self.write({"bad-lerp.json": data})
        control = broken(off("not match(example)"))
        code, report = self.rules(dc, "lerp", "--rules", self.p("bad-lerp.json"))
        self.assertEqual((code, report["status"]), (2, "not-run"))
        self.assertIn("motion-per-frame-lerp", report["error"])
        self.assertNotEqual(self.rules(control, "lerp", "--rules", self.p("bad-lerp.json"))[1]["status"], "not-run")


INVARIANT = {"promise": "primary button text contrast is at least 4.5:1", "widths": [375, 1440],
             "states": ["rest", "hover"], "observed_by": "measurement"}
SIGNOFF = {"by": "user", "date": "2026-10-31", "captures": ["C1", "C2"]}


class InvariantTests(Tree):
    """DG-40: a direction's promises are observable invariants, and a sign-off names who accepted which captures."""

    def record(self, module, **extra):
        self.write({"record.md": record_md(dict(RECORD_JSON, **extra))})
        return run(module, "record", self.p("record.md"))

    def test_an_observable_invariant_and_a_sign_off_are_clean(self):
        code, report = self.record(dc, invariants=[INVARIANT], signoff=[SIGNOFF])
        self.assertEqual((code, codes(report)), (0, []), report)

    def test_a_promise_with_no_way_to_observe_it_is_refused(self):
        vague = {"promise": "feels premium", "widths": [1440]}
        control = broken(off("item.get(\"observed_by\") not in OBSERVED_BY"))
        for bad in (vague, dict(INVARIANT, observed_by="a model looking at the screenshot")):
            with self.subTest(item=bad):
                code, report = self.record(dc, invariants=[bad])
                self.assertEqual((code, codes(report)), (1, ["invariant-unobservable"]))
                self.assertEqual(self.record(control, invariants=[bad])[0], 0, "a copy without the observed_by check")

    def test_an_invariant_names_its_widths(self):
        control = broken(off("not widths"))
        for bad in ({k: v for k, v in INVARIANT.items() if k != "widths"}, dict(INVARIANT, widths=[]),
                    dict(INVARIANT, promise="")):
            with self.subTest(item=bad):
                self.assertEqual(codes(self.record(dc, invariants=[bad])[1]), ["invariant-incomplete"])
        self.assertEqual(self.record(control, invariants=[dict(INVARIANT, widths=[])])[0], 0)

    def test_a_sign_off_names_who_when_and_which_captures(self):
        control = broken(off("missing_signoff"))
        for field in ("by", "date", "captures"):
            with self.subTest(field=field):
                thin = {k: v for k, v in SIGNOFF.items() if k != field}
                self.assertEqual(codes(self.record(dc, signoff=[thin])[1]), ["signoff-incomplete"])
                self.assertEqual(self.record(control, signoff=[thin])[0], 0)

    def test_invariants_and_sign_offs_are_lists(self):
        self.assertEqual(sorted(codes(self.record(dc, invariants=INVARIANT, signoff=SIGNOFF)[1])),
                         ["invariants-shape", "signoff-shape"])


# ---- follow-up: DG-43 frames from time, DG-44 readouts from state, DG-45 the delivered file, DG-46 text hold ---------

class RecordedOutputRuntimeTests(Tree):
    """DG-43 (frames drawn from time alone), DG-44 (readouts move with their input) and DG-46's recorded half need a
    browser or a recorder: every report lists them not run, and a pass reported without a browser is refused."""

    def report(self, module, entry, browser="host:browser"):
        self.write({"report.json": critique(browser=browser, runtime=critique()["runtime"] + [entry])})
        return run(module, "report", self.p("report.json"))

    def test_without_a_browser_each_is_not_run(self):
        for check_id in ("DG-43", "DG-44", "DG-46"):
            with self.subTest(check=check_id):
                control = broken(('{"id": "%s",' % check_id, '{"id": "%s-unlisted",' % check_id))
                claimed = {"id": check_id, "status": "passed", "evidence": "frames F1 to F3"}
                self.assertIn("runtime-without-browser", codes(self.report(dc, claimed, browser="none")[1]))
                self.assertEqual(self.report(dc, dict(claimed, status="not-run", why="no browser"), browser="none")[0], 0)
                self.assertEqual(self.report(dc, claimed)[0], 0, "with a browser and its evidence it stands")
                self.assertNotIn("runtime-without-browser", codes(self.report(control, claimed, browser="none")[1]),
                                 "a copy that does not list it lets the claim through")


DELIVERED = {"path": "dist/tour.mp4", "sha256": sha("the encoded tour")}


class DeliveredFileTests(Tree):
    """DG-45: when a report names the delivered file, a capture marked final was read from it (its sha256)."""

    def report(self, module, captures, delivered=DELIVERED):
        data = critique(captures=captures)
        if delivered is not None:
            data["delivered"] = delivered
        self.write({"report.json": data})
        return run(module, "report", self.p("report.json"))

    def capture(self, cid, **changes):
        item = {"id": cid, "file": cid + ".png", "valid": True}
        item.update(changes)
        return item

    def test_a_final_capture_read_from_the_delivered_file_passes(self):
        captures = [self.capture("C1", source="dev server"),
                    self.capture("C2", final=True, source_sha256=DELIVERED["sha256"])]
        code, report = self.report(dc, captures)
        self.assertEqual((code, codes(report)), (0, []), report)
        self.assertEqual(self.report(dc, [self.capture("C1")], delivered=None)[0], 0, "no delivered file, no check")

    def test_final_captures_that_all_came_from_the_live_render_are_refused(self):
        control = broken(off("not any(c.get(\"source_sha256\") == digest for c in finals)"))
        for captures in ([self.capture("C1", final=True, source="dev server")],
                         [self.capture("C1", final=True, source_sha256=sha("the live render"))],
                         [self.capture("C1", source_sha256=DELIVERED["sha256"])],
                         []):
            with self.subTest(captures=captures):
                self.assertIn("capture-not-delivered", codes(self.report(dc, captures)[1]))
                self.assertNotIn("capture-not-delivered", codes(self.report(control, captures)[1]),
                                 "a copy that skips the hash comparison accepts it")

    def test_the_delivered_file_names_its_path_and_sha256(self):
        control = broken(off("not (text_value(delivered.get(\"path\")) and SHA256_RE.fullmatch(str(digest)))"))
        final = [self.capture("C1", final=True, source_sha256="ABC")]
        for bad in ({"path": "dist/tour.mp4"}, {"sha256": DELIVERED["sha256"]}, dict(DELIVERED, sha256="ABC"),
                    "dist/tour.mp4"):
            with self.subTest(delivered=bad):
                where = [f["where"] for f in self.report(dc, final, delivered=bad)[1]["findings"]]
                self.assertIn("delivered", where)
                self.assertNotIn("delivered", [f["where"] for f in self.report(control, final, delivered=bad)[1]["findings"]])


SEVEN_WORDS, THREE_WORDS = "The crank turns both gears at once", "Pistons fire twice"


class TextHoldTests(Tree):
    """DG-46: a line of text holds at least 1 s plus 0.25 s per word past three (text-hold-s in thresholds.json)."""

    def report(self, module, beats, *extra):
        self.write({"report.json": critique(text_beats=beats)})
        return run(module, "report", self.p("report.json"), *extra)

    def thresholds(self, change):
        data = json.loads((REFERENCES / "thresholds.json").read_text(encoding="utf-8"))
        change(data["thresholds"]["text-hold-s"])
        self.write({"t.json": data})
        return self.p("t.json")

    def test_the_formula(self):
        item = json.loads((REFERENCES / "thresholds.json").read_text(encoding="utf-8"))["thresholds"]["text-hold-s"]
        self.assertEqual((item["kind"], item["basis"], item["unit"]), ("per-word", "taste", "s"))
        self.assertEqual([dc.hold_needed(words, item) for words in (1, 3, 4, 7)], [1.0, 1.0, 1.25, 2.0])

    def test_a_caption_cut_short_is_found(self):
        control = broken(("needed = hold_needed(words, hold)", "needed = hold[\"base\"]"))
        short = [{"id": "T1", "text": SEVEN_WORDS, "held_s": 1.5}]
        code, report = self.report(dc, short)
        self.assertEqual((code, codes(report)), (1, ["text-hold-short"]), report)
        self.assertEqual(self.report(control, short)[0], 0, "a copy with a flat 1 s minimum passes the 1.5 s caption")
        for beats in ([{"id": "T1", "text": SEVEN_WORDS, "held_s": 2.0}], [{"id": "T1", "text": THREE_WORDS, "held_s": 1.0}]):
            with self.subTest(beats=beats):
                code, report = self.report(dc, beats)
                self.assertEqual((code, codes(report)), (0, []), report)

    def test_a_beat_names_its_text_and_hold(self):
        control = broken(('out.append(finding("report", "bad-value", where, "a text beat gives its text and held_s '
                          '(seconds on screen)"))', "pass"))  # a copy that skips a beat it cannot read
        for beat in ({"id": "T1", "text": SEVEN_WORDS}, {"id": "T1", "held_s": 2.0}, "a caption"):
            with self.subTest(beat=beat):
                self.assertIn("bad-value", codes(self.report(dc, [beat])[1]))
                self.assertNotIn("bad-value", codes(self.report(control, [beat])[1]))

    def test_the_new_kind_is_checked_when_the_thresholds_load(self):
        beats = [{"id": "T1", "text": THREE_WORDS, "held_s": 1.0}]
        for change, condition in (
                (lambda t: t["fixtures"]["fails"].update(held=2.0),
                 "holds(fails[\"words\"], fails[\"held\"], item) or not holds(passes[\"words\"], passes[\"held\"], item)"),
                (lambda t: t.update(free_words=3.5), "not hold_shape_ok(item)")):
            control = broken(off(condition))
            path = self.thresholds(change)
            with self.subTest(condition=condition):
                code, report = self.report(dc, beats, "--thresholds", path)
                self.assertEqual((code, report["status"]), (2, "not-run"), report)
                self.assertIn("text-hold-s", report["error"])
                self.assertNotEqual(self.report(control, beats, "--thresholds", path)[1]["status"], "not-run")


class AlwaysTests(Tree):
    files = {"theme.json": THEME, "record.md": record_md(), "site/index.html": SEEDED_HTML,
             "site/styles.css": SEEDED_CSS, "brief.md": "A landing page.\n", "before.html": BEFORE,
             "report.json": critique()}

    def commands(self):
        return [("tokens", self.p("site"), "--theme", self.p("theme.json")), ("contrast", self.p("record.md")),
                ("rules", self.p("site"), "--brief", self.p("brief.md")), ("record", self.p("record.md")),
                ("inventory", self.p("before.html"), self.p("before.html")), ("report", self.p("report.json")),
                ("tokens", self.p("site"), "--writing", self.p("site/tokens.json")),
                ("waivers", self.p("theme.json"))]

    def snapshot(self):
        out = {}
        for path in sorted(self.root.rglob("*")):
            info = path.stat()
            out[path.relative_to(self.root).as_posix()] = (path.is_dir(), info.st_size, info.st_mtime_ns,
                                                            None if path.is_dir() else sha(path.read_bytes()))
        return out

    def test_every_report_lists_dg23_and_dg24_as_not_run(self):
        for argv in self.commands():
            with self.subTest(command=argv[0]):
                report = run(dc, *argv)[1]
                self.assertEqual([(i["id"], i["status"]) for i in report["not_run"]],
                                 [("DG-23", "not-run"), ("DG-24", "not-run"), ("DG-26", "not-run"),
                                  ("DG-34", "not-run"), ("DG-36", "not-run"), ("DG-38", "not-run"),
                                  ("DG-39", "not-run"), ("DG-41", "not-run"), ("DG-43", "not-run"),
                                  ("DG-44", "not-run"), ("DG-46", "not-run")])
                self.assertTrue(report["claim"])
        control = broken(('out["not_run"] = [dict(item) for item in RUNTIME_NOT_RUN]', 'out["not_run"] = []'))
        self.assertEqual(run(control, *self.commands()[1])[1]["not_run"], [])

    def test_a_critique_run_leaves_the_tree_unchanged(self):
        before = self.snapshot()
        for argv in self.commands():
            run(dc, *argv)
        self.assertEqual(self.snapshot(), before)
        planted = broken(("def cmd_inventory(args):",
                          "def cmd_inventory(args):\n    pathlib.Path(args.after).write_text('planted', encoding='utf-8')"))
        for argv in self.commands():
            run(planted, *argv)
        self.assertNotEqual(self.snapshot(), before, "the control: a copy that writes is caught")

    def test_the_script_runs_nothing_writes_nothing_and_opens_no_connection(self):
        forbidden = ("urllib", "socket", "http.client", "subprocess", "os.system", "os.popen", "write_text", "write_bytes",
                     "importlib", "runpy", "exec(", "eval(", ".unlink(", "os.remove", "shutil", "open(")

        def hits(source):
            code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
            return [word for word in forbidden if word in code]
        self.assertEqual(hits(SCRIPT.read_text(encoding="utf-8")), [])
        self.assertEqual(hits("x = 1\npathlib.Path(p).write_text('planted')\n"), ["write_text"])

    def test_usage_and_unreadable_inputs(self):
        self.assertEqual(run(dc, "tokens", self.p("site"))[0], 64, "tokens needs --theme or --writing")
        self.assertEqual(run(dc, "nonsense")[0], 64)
        code, report = run(dc, "contrast", self.p("missing.md"))
        self.assertEqual((code, report["status"]), (2, "unreadable"))
        code, report = run(dc, "waivers", self.p("theme.json"))
        self.assertEqual((code, report["status"]), (2, "unreadable"), "not a waiver file")


if __name__ == "__main__":
    unittest.main()
