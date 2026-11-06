"""DS-4 (dsh-superagent, 2026-10-31): a pull request that changes what users see carries a before and an after capture of
the same scenario, viewport, theme and state, each labelled with its revision. `shipgate.py --body FILE` reads the saved
PR body; no browser runs and no image is opened. One capture is one line:

    - before: ![alt](shots/before.png) | scenario: checkout | viewport: 1280x800 | theme: light | state: empty | revision: 3d453ea

Findings (level decide, steps pr and merge): `ui-evidence-missing` (a UI change with no capture line), `ui-evidence-after-only`
and `ui-evidence-before-only` (a capture with no partner), `ui-evidence-mismatch` (a stated scenario, viewport, theme or
state differs), `ui-evidence-unlabelled` (a label, the revision included, is missing) and `ui-evidence-unknown` (the change
is a UI change but no body was saved).

Run: python -B -m unittest discover -s skills/westack-ship/tests -v
SHIPGATE_UNDER_TEST=<path> points the suite at another copy. Every rule also runs against a copy of the script with that one
condition edited out; the copy must let the bad body through. Each copy is built before its assertions.
"""
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("SHIPGATE_UNDER_TEST") or HERE.parent / "scripts" / "shipgate.py")


def load(path=SCRIPT):
    key = "westack_ship_ui_evidence_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OID = "a" * 40
STATUS = "# branch.oid %s\n# branch.head feature\n# branch.upstream origin/feature\n# branch.ab +0 -0\n" % OID
REMOTES = "origin\t/tmp/remote.git (fetch)\norigin\t/tmp/remote.git (push)\n"
RECEIPTS = {"format": "westack-checks-1", "kind": "diff", "verdict": "no-new-failures", "exit_code": 0,
            "new_failures": [], "preexisting_failures": []}

def diff_of(*paths):
    return "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1,1 +1,1 @@\n-old\n+new\n" % ((p,) * 4) for p in paths)


def capture(kind, revision, image=True, **labels):
    """One capture line; a label given as None is left out, and so is the revision when it is None."""
    view = dict(scenario="checkout, empty cart", viewport="1280x800", theme="light", state="signed out")
    view.update(labels)
    parts = (["![%s](shots/%s.png)" % (kind, kind)] if image else []) + ["%s: %s" % (k, v) for k, v in view.items() if v]
    if revision:
        parts.append("revision: " + revision)
    return "- %s: %s" % (kind, " | ".join(parts))


CSS_DIFF, PY_DIFF = diff_of("web/checkout.css"), diff_of("src/billing.py")
BEFORE, AFTER = capture("before", "3d453ea"), capture("after", "9f8e7d6")


def body(*lines):
    return "## Why\nThe cart total was hidden.\n\n## UI evidence\n" + "\n".join(lines) + "\n\n## Risk\nLow.\n"


def ids(report, level=None):
    return {f["id"] for f in report["findings"] if f["id"].startswith("ui-evidence") and level in (None, f["level"])}


EMPTY_REPO = tempfile.TemporaryDirectory(prefix="westack-ui-evidence-repo-")


class Gate(unittest.TestCase):
    def setUp(self):
        self.sg = load()

    def gate(self, pr_body, diff=CSS_DIFF, module=None, **extra):
        args = dict(status=STATUS, remotes=REMOTES, pr=[], rules={"feature": ["none"]}, repo=EMPTY_REPO.name, diff=diff,
                    receipts=RECEIPTS, default_branch="main", grant=["pr"], body=pr_body)
        args.update(extra)
        return (module or self.sg).gate(**args)


class Evidence(Gate):
    def test_a_before_and_an_after_of_the_same_view_pass(self):
        report = self.gate(body(BEFORE, AFTER))
        self.assertEqual(ids(report), set(), report["findings"])
        self.assertEqual(report["ui_evidence"]["status"], "complete")
        self.assertEqual(report["steps"]["pr"]["status"], "clear")

    def test_an_after_alone_is_flagged_and_the_pr_step_needs_a_decision(self):
        report = self.gate(body(AFTER))
        self.assertEqual(ids(report), {"ui-evidence-after-only"})
        self.assertEqual(ids(report, "decide"), {"ui-evidence-after-only"})
        self.assertEqual((report["steps"]["pr"]["status"], report["exit_code"]), ("needs-decision", 1))
        self.assertEqual(report["ui_evidence"]["status"], "incomplete")

    def test_a_before_alone_is_flagged_too(self):
        self.assertEqual(ids(self.gate(body(BEFORE))), {"ui-evidence-before-only"})

    def test_a_capture_line_without_an_image_is_no_capture(self):
        self.assertEqual(ids(self.gate(body(capture("before", "3d453ea", image=False), AFTER))), {"ui-evidence-after-only"})

    def test_captures_at_another_viewport_theme_state_or_scenario_are_a_mismatch(self):
        for field, value in (("viewport", "375x812"), ("theme", "dark"), ("state", "signed in"), ("scenario", "cart page")):
            with self.subTest(field=field):
                report = self.gate(body(BEFORE, capture("after", "9f8e7d6", **{field: value})))
                self.assertEqual(ids(report), {"ui-evidence-mismatch"}, report["findings"])
                mismatch = next(f for f in report["findings"] if f["id"] == "ui-evidence-mismatch")
                self.assertIn(field, " ".join(mismatch["evidence"]))

    def test_a_capture_with_no_revision_or_another_missing_label_is_unlabelled(self):
        for label, line in (("revision", capture("before", None)), ("viewport", capture("before", "3d453ea", viewport=None)),
                            ("theme", capture("before", "3d453ea", theme=None))):
            with self.subTest(label=label):
                report = self.gate(body(line, AFTER))
                self.assertEqual(ids(report), {"ui-evidence-unlabelled"}, report["findings"])
                unlabelled = next(f for f in report["findings"] if f["id"] == "ui-evidence-unlabelled")
                self.assertIn(label, " ".join(unlabelled["evidence"]))

    def test_pairs_are_read_in_order(self):
        second = (capture("before", "3d453ea", scenario="cart page", viewport="375x812"),
                  capture("after", "9f8e7d6", scenario="cart page", viewport="375x812"))
        self.assertEqual(ids(self.gate(body(BEFORE, AFTER, *second))), set())
        self.assertEqual(ids(self.gate(body(BEFORE, AFTER, second[0]))), {"ui-evidence-before-only"})

    def test_bullets_bold_and_case_do_not_hide_a_capture(self):
        loose = ["* **Before:** " + BEFORE.split(": ", 1)[1], "AFTER: " + AFTER.split(": ", 1)[1]]
        report = self.gate(body(*loose))
        self.assertEqual((ids(report), report["ui_evidence"]["status"]), (set(), "complete"), report["findings"])

    def test_prose_that_starts_with_before_or_after_is_not_a_capture(self):
        report = self.gate(body("Before: the button was blue.", "After: it is green, see https://example.com/spec"),
                           diff=PY_DIFF)
        self.assertEqual((ids(report), report["ui_evidence"]["status"]), (set(), "not-applicable"), report["findings"])

class WhenItApplies(Gate):
    def test_a_ui_change_with_no_capture_line_is_missing_evidence(self):
        report = self.gate("## Why\nRestyled the cart.\n", diff=CSS_DIFF)
        self.assertEqual(ids(report, "decide"), {"ui-evidence-missing"})

    def test_a_change_with_no_ui_file_and_no_flag_owes_nothing(self):
        report = self.gate("## Why\nFixed a rounding error.\n", diff=PY_DIFF)
        self.assertEqual((ids(report), report["ui_evidence"]["status"]), (set(), "not-applicable"))

    def test_the_flag_makes_any_change_a_ui_change(self):
        report = self.gate("## Why\nChanged a server-rendered label.\n", diff=PY_DIFF, ui_change=True)
        self.assertEqual(ids(report), {"ui-evidence-missing"})

    def test_a_ui_change_with_no_saved_body_is_unknown_not_clean(self):
        report = self.gate(None, diff=CSS_DIFF, ui_change=True)
        self.assertEqual(ids(report, "unknown"), {"ui-evidence-unknown"})
        self.assertEqual((report["steps"]["pr"]["status"], report["exit_code"]), ("cannot-tell", 2))

    def test_without_a_body_or_the_flag_nothing_is_checked(self):
        report = self.gate(None, diff=CSS_DIFF)
        self.assertEqual((ids(report), report["ui_evidence"]["status"]), (set(), "not-checked"))

    def test_the_report_says_it_opens_no_image(self):
        self.assertIn("opens no image", json.dumps(self.gate(body(BEFORE, AFTER))["ui_evidence"]))

    def test_every_ui_extension_counts(self):
        for name in ("a.css", "a.scss", "a.sass", "a.less", "a.html", "a.htm", "a.vue", "a.svelte", "a.jsx", "a.tsx", "a.astro",
                     "A.CSS"):
            with self.subTest(name=name):
                self.assertIn("ui-evidence-missing", ids(self.gate("no captures\n", diff=diff_of("web/" + name))))
        self.assertEqual(ids(self.gate("no captures\n", diff=diff_of("web/notes.md", "src/a.py"))), set())


class Cli(unittest.TestCase):
    def run_main(self, argv):
        sg, out = load(), io.StringIO()
        with redirect_stdout(out):
            code = sg.main(argv)
        return code, out.getvalue()

    def test_body_and_ui_change_flags_reach_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            for name, text in (("status.txt", STATUS), ("remotes.txt", REMOTES), ("diff.txt", CSS_DIFF),
                               ("after.md", body(AFTER)), ("both.md", body(BEFORE, AFTER)), ("none.md", "Restyled.\n")):
                (tmp / name).write_text(text, encoding="utf-8")
            (tmp / "receipts.json").write_text(json.dumps(RECEIPTS), encoding="utf-8")
            (tmp / "pr.json").write_text("[]", encoding="utf-8")
            base = ["--status", str(tmp / "status.txt"), "--remotes", str(tmp / "remotes.txt"), "--diff", str(tmp / "diff.txt"),
                    "--pr", str(tmp / "pr.json"), "--rules", "feature=none", "--repo", str(tmp), "--receipts",
                    str(tmp / "receipts.json"), "--default-branch", "main", "--grant", "pr"]
            code, text = self.run_main(base + ["--body", str(tmp / "both.md")])
            self.assertEqual(json.loads(text)["ui_evidence"]["status"], "complete", text)
            code, text = self.run_main(base + ["--body", str(tmp / "after.md")])
            self.assertEqual(code, 1)
            self.assertIn("ui-evidence-after-only", text)
            code, text = self.run_main(base)
            self.assertEqual((code, json.loads(text)["ui_evidence"]["status"]), (0, "not-checked"), text)
            code, text = self.run_main(base + ["--ui-change"])
            self.assertEqual(code, 2)
            self.assertIn("ui-evidence-unknown", text)
            self.assertIn(hashlib.sha256((tmp / "after.md").read_bytes()).hexdigest(),
                          self.run_main(base + ["--body", str(tmp / "after.md")])[1], "the body is hashed like every input")


class BrokenCopies(Gate):
    """One condition of the check edited out of a copy; the copy must pass the body the condition exists to refuse."""

    def broken(self, tmp, pattern, replacement):
        source = SCRIPT.read_text(encoding="utf-8")
        edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
        self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
        self.assertNotEqual(edited, source)
        target = pathlib.Path(tmp) / "shipgate_broken.py"
        target.write_text(edited, encoding="utf-8")
        return load(target)

    def caught(self, tmp, pattern, replacement, pr_body, code, **extra):
        copy = self.broken(tmp, pattern, replacement)
        self.assertIn(code, ids(self.gate(pr_body, **extra)), "the real check must flag it first")
        return ids(self.gate(pr_body, module=copy, **extra))

    def test_a_copy_that_accepts_any_image_passes_an_after_only_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = self.caught(tmp, r"^    if len\(after\) != len\(before\):$", "    if False:", body(AFTER),
                               "ui-evidence-after-only")
        self.assertNotIn("ui-evidence-after-only", seen)
        self.assertNotIn("ui-evidence-before-only", seen)

    def test_a_copy_that_does_not_compare_the_views_passes_a_viewport_mismatch(self):
        mismatched = body(BEFORE, capture("after", "9f8e7d6", viewport="375x812"))
        with tempfile.TemporaryDirectory() as tmp:
            seen = self.caught(tmp, r"^        if differing:$", "        if False:", mismatched, "ui-evidence-mismatch")
        self.assertNotIn("ui-evidence-mismatch", seen)

    def test_a_copy_that_skips_the_label_check_passes_a_capture_with_no_revision(self):
        unlabelled = body(capture("before", None), AFTER)
        with tempfile.TemporaryDirectory() as tmp:
            seen = self.caught(tmp, r"^        if absent:$", "        if False:", unlabelled, "ui-evidence-unlabelled")
        self.assertNotIn("ui-evidence-unlabelled", seen)

    def test_a_copy_that_never_asks_for_evidence_passes_a_ui_change_with_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = self.caught(tmp, r"^        if needed:$", "        if False:", "Restyled the cart.\n", "ui-evidence-missing")
        self.assertNotIn("ui-evidence-missing", seen)

    def test_a_copy_that_treats_no_body_as_no_evidence_owed_passes_an_unread_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = self.caught(tmp, r"^    if body is None and forced:$", "    if False:", None, "ui-evidence-unknown", ui_change=True)
        self.assertNotIn("ui-evidence-unknown", seen)


class Discipline(unittest.TestCase):
    def test_the_script_still_runs_nothing(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import subprocess", "os.system", "eval(", "exec(", "urllib", "socket", "shutil.rmtree"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
