"""The CodeRabbit-style checks (RV items, 2026-10-30) that `diffscope.py` can see:

  RV-3   quoted snippets labelled by role; `snippets DIFF FINDINGS [--root DIR]` compares each with the cited lines,
         and a paraphrase fails
  RV-8   a vendor's severity label is kept verbatim in its own field, beside the vendor's name; never a P level
  RV-10  identity is a rule family, a root-control anchor that names no line number, and an instance key; two
         records with the same identity are an unmerged duplicate
  RV-11  a confirmed P0 or P1 is blocking whatever else is missing; a not-assessed verdict names at most three
         actions, each with what it would settle
  RV-17  a vendor's comment is a candidate: confirmed only with a westack validation, and the report counts each
         vendor's candidates, confirmed and dropped records

Run: python -B -m unittest discover -s skills/westack-review/tests -v
The script under test is loaded by path; WESTACK_REVIEW_DIFFSCOPE may point at another copy. Each check also runs
against a copy of the script with that one check edited out, and the copy must let the bad input through.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("WESTACK_REVIEW_DIFFSCOPE")
                      or pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diffscope.py").resolve()


def load(path=SCRIPT):
    key = "westack_review_rv_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


DIFF = """diff --git a/app/fetch.py b/app/fetch.py
--- a/app/fetch.py
+++ b/app/fetch.py
@@ -1,6 +1,7 @@
 import requests

 def fetch(url):
-    if not allowed(url):
+    if not allowed(url):  # allowlist checked once
         raise ValueError(url)
-    return requests.get(url, allow_redirects=False)
+    response = requests.get(url, allow_redirects=True)
+    return response
"""
HEAD_FILE = "import requests\n\ndef fetch(url):\n    if not allowed(url):  # allowlist checked once\n" \
            "        raise ValueError(url)\n    response = requests.get(url, allow_redirects=True)\n    return response\n"
ROUTES = "from app.fetch import fetch\n\n\ndef proxy(request):\n    return fetch(request.args['url'])\n"

CONTROL = {"role": "control", "file": "app/fetch.py", "line": 4, "text": "if not allowed(url):  # allowlist checked once"}
SINK = {"role": "sink", "file": "app/fetch.py", "line": 6, "text": "response = requests.get(url, allow_redirects=True)"}
OLD_SINK = {"role": "sink", "file": "app/fetch.py", "line": 6, "side": "old",
            "text": "    return requests.get(url, allow_redirects=False)"}
ENTRY = {"role": "entrypoint", "file": "app/routes.py", "line": 4, "text": "def proxy(request):"}
P1 = {"id": "F1", "state": "confirmed", "claim": "Re-check the host after each redirect", "file": "app/fetch.py",
      "line": 6, "severity": "P1", "consequence": "an allowed host can redirect the fetch to an internal address",
      "trigger": "an allowed URL that answers 302 to http://169.254.169.254/", "evidence": "traced: snippets below",
      "snippets": [ENTRY, CONTROL, SINK]}
P3 = {"id": "F2", "state": "confirmed", "claim": "Name the response", "file": "app/fetch.py", "line": 7,
      "severity": "P3", "consequence": "a reader has to look twice"}
VENDOR = {"id": "V1", "state": "needs-validation", "claim": "Handle a missing url argument", "file": "app/fetch.py",
          "line": 3, "vendor": "coderabbit", "vendor_severity": "Minor"}
VENDOR_DROPPED = {"id": "V2", "state": "dropped", "claim": "Add a docstring", "vendor": "coderabbit",
                  "vendor_severity": "Nitpick", "stage": "exclusion 8", "reason": "taste", "evidence": "no rule quoted"}
VENDOR_CONFIRMED = {"id": "V3", "state": "confirmed", "claim": "Follow redirects only to allowed hosts",
                    "file": "app/fetch.py", "line": 6, "severity": "P2", "consequence": "redirects escape the allowlist",
                    "vendor": "coderabbit", "vendor_severity": "Major",
                    "validation": "survived: a fresh-context validator traced the redirect path"}
UNVALIDATED = {"id": "F5", "state": "not-validated", "claim": "Race in the cache", "file": "app/cache.py", "line": 40,
               "reason": "the validator timed out"}


def problems(report):
    return [(e.get("id"), e.get("field")) for e in report["errors"]]


def ident(family, anchor, instance=None):
    out = {"family": family, "anchor": anchor}
    if instance is not None:
        out["instance"] = instance
    return out


class VendorFields(unittest.TestCase):
    """RV-8 and RV-17."""

    def setUp(self):
        self.m = load()

    def test_a_minor_vendor_label_stays_verbatim_beside_the_vendor_and_is_validated_like_any_other(self):
        report = self.m.check_findings([VENDOR, VENDOR_DROPPED, VENDOR_CONFIRMED])
        self.assertEqual(report["status"], "valid", report["errors"])
        # the vendor's label is no P level: a candidate still may not carry a severity
        self.assertIn(("V1", "severity"), problems(self.m.check_findings([dict(VENDOR, severity="P3")])))

    def test_a_vendor_label_without_the_vendor_or_an_empty_label_is_refused(self):
        unattributed = {k: v for k, v in VENDOR.items() if k != "vendor"}
        self.assertIn(("V1", "vendor_severity"), problems(self.m.check_findings([unattributed])))
        self.assertIn(("V1", "vendor_severity"), problems(self.m.check_findings([dict(VENDOR, vendor_severity=" ")])))
        self.assertIn(("V1", "vendor"), problems(self.m.check_findings([dict(VENDOR, vendor="")])))
        missing_label = {k: v for k, v in VENDOR.items() if k != "vendor_severity"}
        self.assertEqual(self.m.check_findings([missing_label])["status"], "valid", "missing means unknown")

    def test_a_vendor_finding_is_confirmed_only_with_a_westack_validation(self):
        bare = {k: v for k, v in VENDOR_CONFIRMED.items() if k != "validation"}
        self.assertIn(("V3", "validation"), problems(self.m.check_findings([bare])))
        own = {k: v for k, v in bare.items() if k not in ("vendor", "vendor_severity")}
        self.assertEqual(self.m.check_findings([own])["status"], "valid", "westack's own findings keep the old rule")

    def test_the_report_counts_each_vendors_candidates_confirmed_and_dropped(self):
        report = self.m.check_findings([VENDOR, VENDOR_DROPPED, VENDOR_CONFIRMED, P3])
        self.assertEqual(report["vendors"], {"coderabbit": {"candidates": 3, "confirmed": 1, "dropped": 1,
                                                            "needs-validation": 1, "not-validated": 0,
                                                            "dropped_share": 0.333}})
        self.assertEqual(self.m.check_findings([P3])["vendors"], {})


class Identity(unittest.TestCase):
    """RV-10."""

    def setUp(self):
        self.m = load()

    def test_two_handlers_missing_one_check_are_two_instances(self):
        a = dict(P3, id="F7", identity=ident("missing-authz", "require_owner()", "GET /orders/{id}"))
        b = dict(P3, id="F8", line=9, identity=ident("missing-authz", "require_owner()", "DELETE /orders/{id}"))
        self.assertEqual(self.m.check_findings([a, b])["status"], "valid")

    def test_the_same_identity_twice_is_an_unmerged_duplicate_unless_one_was_dropped_as_such(self):
        a = dict(P3, id="F7", identity=ident("missing-authz", "require_owner()", "GET /orders/{id}"))
        b = dict(P3, id="F8", line=9, identity=ident("missing-authz", "require_owner()", "GET /orders/{id}"))
        self.assertIn(("F8", "identity"), problems(self.m.check_findings([a, b])))
        dup = {"id": "F8", "state": "dropped", "claim": "Same check missing", "stage": "exclusion 11",
               "reason": "duplicate of F7", "evidence": "same control, same handler",
               "identity": ident("missing-authz", "require_owner()", "GET /orders/{id}")}
        self.assertEqual(self.m.check_findings([a, dup])["status"], "valid")

    def test_an_anchor_with_a_line_number_is_refused(self):
        for anchor in ("app/fetch.py:6", "fetch.py line 6", "app/fetch.py#L6"):
            with self.subTest(anchor=anchor):
                rec = dict(P3, identity=ident("ssrf", anchor))
                self.assertIn(("F2", "identity"), problems(self.m.check_findings([rec])))
        self.assertIn(("F2", "identity"), problems(self.m.check_findings([dict(P3, identity={"family": "ssrf"})])))
        self.assertEqual(self.m.check_findings([dict(P3, identity=ident("ssrf", "allowed()"))])["status"], "valid")


class Verdict(unittest.TestCase):
    """RV-11."""

    def setUp(self):
        self.m = load()

    def test_a_confirmed_p1_with_ci_missing_is_blocking_not_not_assessed(self):
        plan = [{"action": "run the CI suite", "settles": "whether the redirect test exists and passes"}]
        held = {"verdict": "not-assessed", "evidence_plan": plan, "findings": [P1, UNVALIDATED]}
        self.assertIn((None, "verdict"), problems(self.m.check_findings(held)))
        self.assertIn((None, "verdict"), problems(self.m.check_findings({"verdict": "not-assessed", "findings": [P1]})))
        self.assertEqual(self.m.check_findings({"verdict": "blocking", "findings": [P1, UNVALIDATED]})["status"], "valid")

    def test_not_assessed_names_at_most_three_actions_each_with_what_it_settles(self):
        one = {"action": "run the migration on a copy", "settles": "whether the backfill locks the table"}
        ok = {"verdict": "not-assessed", "evidence_plan": [one] * 3, "findings": [UNVALIDATED]}
        self.assertEqual(self.m.check_findings(ok)["status"], "valid", self.m.check_findings(ok)["errors"])
        self.assertIn((None, "evidence_plan"), problems(self.m.check_findings(dict(ok, evidence_plan=[one] * 4))))
        self.assertIn((None, "evidence_plan"),
                      problems(self.m.check_findings(dict(ok, evidence_plan=[{"action": "rerun CI"}]))))
        self.assertIn((None, "evidence_plan"), problems(self.m.check_findings(dict(ok, evidence_plan=[]))))

    def test_an_evidence_plan_belongs_only_to_a_not_assessed_verdict(self):
        one = {"action": "run CI", "settles": "whether the suite passes"}
        data = {"verdict": "blocking", "evidence_plan": [one], "findings": [P1]}
        self.assertIn((None, "evidence_plan"), problems(self.m.check_findings(data)))


class SnippetShape(unittest.TestCase):
    """RV-3, the shape half: checked by `findings`."""

    def setUp(self):
        self.m = load()

    def test_labelled_snippets_are_accepted(self):
        self.assertEqual(self.m.check_findings([P1])["status"], "valid", self.m.check_findings([P1])["errors"])

    def test_an_unknown_role_or_a_snippet_without_text_or_place_is_refused(self):
        for bad in (dict(SINK, role="helper"), {k: v for k, v in SINK.items() if k != "text"},
                    {k: v for k, v in SINK.items() if k != "line"}, dict(SINK, side="both"), dict(SINK, note="x"),
                    "requests.get(url)"):
            with self.subTest(snippet=bad):
                self.assertIn(("F1", "snippets"), problems(self.m.check_findings([dict(P1, snippets=[bad])])))
        self.assertIn(("F1", "snippets"), problems(self.m.check_findings([dict(P1, snippets="see above")])))


class SnippetText(unittest.TestCase):
    """RV-3, the text half: `snippets` compares each quote with the cited lines."""

    def setUp(self):
        self.m = load()
        self.tmp = tempfile.TemporaryDirectory(prefix="westack-rv-")
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "head"
        (self.root / "app").mkdir(parents=True)
        (self.root / "app" / "fetch.py").write_text(HEAD_FILE, encoding="utf-8")
        (self.root / "app" / "routes.py").write_text(ROUTES, encoding="utf-8")
        self.files = self.m.parse(DIFF)

    def run_check(self, snippets, root=True):
        return self.m.snippets(self.files, [dict(P1, snippets=snippets)], self.root if root else None)

    def test_quotes_of_the_new_and_old_side_and_of_an_untouched_file_match(self):
        report = self.run_check([ENTRY, CONTROL, SINK, OLD_SINK])
        self.assertEqual(report["status"], "verified", report)
        self.assertEqual([s["verdict"] for s in report["snippets"]], ["matches"] * 4)

    def test_a_paraphrased_quote_differs(self):
        report = self.run_check([dict(SINK, text="requests.get follows redirects now")])
        self.assertEqual((report["status"], report["snippets"][0]["verdict"]), ("mismatch", "differs"))

    def test_a_quote_cited_at_the_wrong_line_differs(self):
        report = self.run_check([dict(SINK, line=7)])
        self.assertEqual(report["snippets"][0]["verdict"], "differs")

    def test_a_multi_line_quote_matches_line_by_line_whatever_its_indent(self):
        both = {"role": "sink", "file": "app/fetch.py", "line": 6,
                "text": "response = requests.get(url, allow_redirects=True)\r\nreturn response"}
        self.assertEqual(self.run_check([both])["status"], "verified")

    def test_outside_the_diff_without_a_root_is_not_checkable_never_verified(self):
        report = self.run_check([ENTRY], root=False)
        self.assertEqual((report["status"], report["snippets"][0]["verdict"]), ("inconclusive", "not-checkable"))

    def test_a_file_that_is_not_there_or_a_path_that_leaves_the_root_is_not_found(self):
        for path in ("app/missing.py", "../outside.py", "/etc/passwd"):
            with self.subTest(path=path):
                report = self.run_check([dict(ENTRY, file=path)])
                self.assertEqual((report["status"], report["snippets"][0]["verdict"]), ("mismatch", "not-found"))

    def test_no_snippets_at_all_is_not_run(self):
        report = self.m.snippets(self.files, [P3], self.root)
        self.assertEqual(report["status"], "not-run")

    def test_the_report_says_what_a_match_does_not_show(self):
        self.assertIn("not that the path it describes is reachable", self.run_check([CONTROL])["claim"])


class SnippetCli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "head" / "app").mkdir(parents=True)
            (tmp / "head" / "app" / "routes.py").write_text(ROUTES, encoding="utf-8")
            diff = tmp / "diff.txt"
            diff.write_bytes(DIFF.encode("utf-8"))
            good, bad, none = tmp / "good.json", tmp / "bad.json", tmp / "none.json"
            good.write_text(json.dumps([P1]), encoding="utf-8")
            bad.write_text(json.dumps([dict(P1, snippets=[dict(SINK, text="it follows redirects")])]), encoding="utf-8")
            none.write_text(json.dumps([P3]), encoding="utf-8")
            ok = self.run_cli("snippets", diff, good, "--root", tmp / "head")
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            body = json.loads(ok.stdout)
            self.assertEqual((body["status"], body["diff_sha256"]), ("verified", hashlib.sha256(diff.read_bytes()).hexdigest()))
            self.assertEqual(self.run_cli("snippets", diff, bad, "--root", tmp / "head").returncode, 1)
            self.assertEqual(self.run_cli("snippets", diff, good).returncode, 2, "an entrypoint outside the diff, no root")
            self.assertEqual(self.run_cli("snippets", diff, none).returncode, 2)
            self.assertEqual(self.run_cli("snippets", tmp / "missing.txt", good).returncode, 2)
            self.assertEqual(self.run_cli("snippets", diff).returncode, 64)


class BrokenCopies(unittest.TestCase):
    """Each copy has one check edited out of the script's source and must accept the input the check refuses."""

    def broken(self, tmp, pattern, replacement):
        source = SCRIPT.read_text(encoding="utf-8")
        edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
        self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
        self.assertNotEqual(edited, source)
        target = pathlib.Path(tmp) / "diffscope_broken.py"
        target.write_text(edited, encoding="utf-8")
        return load(target)

    def both(self, pattern, replacement, run):
        """(result on a broken copy, result on the real script)."""
        with tempfile.TemporaryDirectory() as tmp:
            broken = run(self.broken(tmp, pattern, replacement))
        return broken, run(load())

    def test_without_the_vendor_label_rule_an_unattributed_label_passes(self):
        unattributed = [{k: v for k, v in VENDOR.items() if k != "vendor"}]
        broken, real = self.both(r'^(\s+)if "vendor_severity" in rec and not _text\(rec\.get\("vendor"\)\):$',
                                 r"\1if False:", lambda m: m.check_findings(unattributed)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_vendor_validation_rule_a_vendor_comment_counts_as_a_finding(self):
        bare = [{k: v for k, v in VENDOR_CONFIRMED.items() if k != "validation"}]
        broken, real = self.both(r"^VENDOR_CONFIRMED_NEEDS = .*$", "VENDOR_CONFIRMED_NEEDS = ()",
                                 lambda m: m.check_findings(bare)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_anchor_rule_a_line_number_anchor_passes(self):
        rec = [dict(P3, identity=ident("ssrf", "app/fetch.py:6"))]
        broken, real = self.both(r"^LINE_IN_ANCHOR = .*$", 'LINE_IN_ANCHOR = re.compile(r"(?!x)x")',
                                 lambda m: m.check_findings(rec)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_duplicate_rule_an_unmerged_duplicate_passes(self):
        same = ident("missing-authz", "require_owner()", "GET /orders/{id}")
        recs = [dict(P3, id="F7", identity=same), dict(P3, id="F8", identity=same)]
        broken, real = self.both(r"^IDENTITY_UNIQUE_AMONG = .*$", "IDENTITY_UNIQUE_AMONG = ()",
                                 lambda m: m.check_findings(recs)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_blocking_rule_a_confirmed_p1_can_be_held_at_not_assessed(self):
        held = {"verdict": "not-assessed", "findings": [P1, UNVALIDATED]}
        broken, real = self.both(r"^HELD_ONLY_WITHOUT = .*$", "HELD_ONLY_WITHOUT = ()",
                                 lambda m: m.check_findings(held)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_cap_a_fourth_action_passes(self):
        one = {"action": "run CI", "settles": "whether the suite passes"}
        data = {"verdict": "not-assessed", "evidence_plan": [one] * 4, "findings": [UNVALIDATED]}
        broken, real = self.both(r"^EVIDENCE_PLAN_MAX = .*$", "EVIDENCE_PLAN_MAX = 99",
                                 lambda m: m.check_findings(data)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_verdict_rule_an_evidence_plan_rides_on_a_blocking_verdict(self):
        one = {"action": "run CI", "settles": "whether the suite passes"}
        data = {"verdict": "blocking", "evidence_plan": [one], "findings": [P1]}
        broken, real = self.both(r"^EVIDENCE_PLAN_VERDICTS = .*$", 'EVIDENCE_PLAN_VERDICTS = ("blocking", "not-assessed")',
                                 lambda m: m.check_findings(data)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_without_the_role_list_an_unlabelled_snippet_passes(self):
        rec = [dict(P1, snippets=[dict(SINK, role="helper")])]
        broken, real = self.both(r'^(\s+)if item\.get\("role"\) not in SNIPPET_ROLES:$', r"\1if False:",
                                 lambda m: m.check_findings(rec)["status"])
        self.assertEqual((broken, real), ("valid", "invalid"))

    def test_a_copy_that_checks_the_place_only_passes_a_paraphrase(self):
        def run(m):
            return m.snippets(m.parse(DIFF), [dict(P1, snippets=[dict(SINK, text="it follows redirects")])], None)["status"]
        broken, real = self.both(r"^def _same\(quoted, cited\):\n    return .*$",
                                 "def _same(quoted, cited):\n    return True", run)
        self.assertEqual((broken, real), ("verified", "mismatch"))

    def test_a_copy_without_the_root_fence_reads_outside_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            (base / "head").mkdir()
            (base / "outside.py").write_text("def proxy(request):\n", encoding="utf-8")
            snippet = {"role": "entrypoint", "file": "../outside.py", "line": 1, "text": "def proxy(request):"}

            def run(m):
                return m.snippets(m.parse(DIFF), [dict(P1, snippets=[snippet])], base / "head")["status"]
            broken, real = self.both(r"^(\s+)if root != target and root not in target\.parents:$", r"\1if False:", run)
        self.assertEqual((broken, real), ("verified", "mismatch"))


if __name__ == "__main__":
    unittest.main()
