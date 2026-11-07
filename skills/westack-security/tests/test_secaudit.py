"""Tests for westack-security's secaudit.py: the findings-record checker, report renderer and scope receipt.

Run from the repo root:  python -B -m unittest discover -s skills/westack-security/tests -v
SECAUDIT_UNDER_TEST=<path> points the suite at another copy. Each check is also run against a copy of the script with
that one rule removed (a broken copy): the bad record must get through there, or the test protects nothing.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("SECAUDIT_UNDER_TEST") or HERE.parent / "scripts" / "secaudit.py")
STUB = HERE / "stub_scanner.py"  # stands in for gitleaks and Betterleaks; no real scanner is installed or run


def load(path=SCRIPT, name="westack_secaudit_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sa = load()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def broken(*edits):
    """A copy of the script with each (old, new) edit applied once: the rule under test removed."""
    source = SCRIPT.read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    with tempfile.TemporaryDirectory(prefix="westack-security-broken-") as temp:
        path = pathlib.Path(temp) / "secaudit_broken.py"
        path.write_text(source, encoding="utf-8")
        return load(path, "westack_secaudit_broken_" + sha(repr(edits))[:12])


def off(condition):
    """The edit that turns one `if <condition>:` into `if False:`."""
    return ("if " + condition + ":", "if False:")


INVOICES = ("from app.db import Invoice\n\n\ndef get_invoice(request, invoice_id):\n    invoice = Invoice.load(invoice_id)\n"
            "    return invoice.to_json()\n\n\ndef list_invoices(request):\n    require_owner(request.user, request.account)\n"
            "    return Invoice.for_account(request.account)\n")
VALIDATE = 'def checked_url(url):\n    if not url.startswith("https://"):\n        raise ValueError(url)\n    return url\n'

# Rows are impact, columns demonstrated, likely, possible, unlikely, unknown: the 25 cells pinned by value.
EXPECTED = {
    "severe": ("critical", "critical", "high", "medium", "medium"),
    "high": ("high", "high", "medium", "low", "low"),
    "moderate": ("medium", "medium", "medium", "low", "low"),
    "low": ("low", "low", "low", "low", "low"),
    "minimal": ("low", "low", "low", "low", "low"),
}
LIKELIHOODS = ("demonstrated", "likely", "possible", "unlikely", "unknown")


def confirmed(**changes):
    rec = {"id": "F1", "state": "confirmed", "claim": "Any caller can read another customer's invoice by its id.",
           "rule": "authz.missing-owner-check", "anchor": "app/invoices.py::get_invoice", "instance": "GET /invoices/{id}",
           "surface": "shipped", "reach": "other-users",
           "principal": "a signed-in customer of another account", "source": "the invoice_id path parameter",
           "control": "require_owner, which list_invoices calls", "sink": "Invoice.load(invoice_id) returned as JSON",
           "path": "router to get_invoice to Invoice.load, with no owner check", "boundary": "isolation between customer accounts",
           "resource": "every customer's invoices", "result": "the local fixture returned account B's invoice to account A",
           "counterevidence": "no middleware or gateway rule filters this route", "proof_gaps": "none for the local fixture",
           "impact": "high", "demonstrated_impact": "high", "likelihood": "likely", "severity": "high", "confidence": "high",
           "snippets": [
               {"role": "entrypoint", "file": "app/invoices.py", "lines": [4, 4], "text": "def get_invoice(request, invoice_id):"},
               {"role": "sink", "file": "app/invoices.py", "lines": [5, 6],
                "text": "    invoice = Invoice.load(invoice_id)\n    return invoice.to_json()"},
               {"role": "expected-control", "file": "app/invoices.py", "lines": "10-10",
                "text": "    require_owner(request.user, request.account)"}]}
    rec.update(changes)
    return rec


def record(*records, **scope):
    base = {"target": "fixture repository", "receipt": "content sha256 0" * 1, "paths": ["."],
            "coverage": {"status": "complete", "receipt": "diffscope.py coverage: exit 0, complete, 2 reviewed"}}
    base.update(scope)
    return {"format": "westack-security-findings-1", "mode": "audit", "scope": base, "records": list(records)}


def codes(result):
    return {p["code"] for p in result["problems"]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-security-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / "repo"
        (self.root / "app").mkdir(parents=True)
        (self.root / "app" / "invoices.py").write_bytes(INVOICES.encode("utf-8"))
        (self.root / "app" / "validate.py").write_bytes(VALIDATE.encode("utf-8"))

    def check(self, data, module=None, root=True):
        return (module or sa).validate(data, str(self.root) if root else None)

    def assertCaught(self, data, code, edit, module_root=True):
        """`code` is raised for data, and a copy with `edit` lets data through (the broken-copy control)."""
        self.assertIn(code, codes(self.check(data, root=module_root)))
        self.assertNotIn(code, codes(self.check(data, broken(edit), root=module_root)),
                         "the broken copy still catches it, so the test shows nothing")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = sa.main(list(args))
            except SystemExit as exc:
                code = exc.code
        text = out.getvalue()
        return code, (json.loads(text) if text.strip() else None)

    def write_record(self, data, name="findings.json"):
        path = pathlib.Path(self.temp.name) / name
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return path


class BasicsTests(Fixture):
    def test_the_fixture_record_is_clean(self):
        self.assertEqual(self.check(record(confirmed()))["problems"], [])

    def test_without_a_root_the_snippet_comparison_is_listed_as_not_checked(self):
        result = self.check(record(confirmed()), root=False)
        self.assertEqual(result["problems"], [])
        self.assertIn("snippets", result["not_checked"])

    def test_unknown_states_and_missing_claims_are_refused(self):
        self.assertIn("bad-state", codes(self.check(record(confirmed(state="maybe")))))
        self.assertIn("claim-missing", codes(self.check(record(confirmed(claim=" ")))))
        self.assertIn("bad-id", codes(self.check(record(confirmed(), confirmed(instance="other")))))


class SeverityTableTests(Fixture):
    """SC-1: severity comes from a fixed impact-by-likelihood table and is never argued afterwards."""

    def cell(self, impact, likelihood, severity, module=None, **extra):
        rec = confirmed(impact=impact, demonstrated_impact=impact, likelihood=likelihood, severity=severity, **extra)
        if severity == "critical":
            rec["critical_evidence"] = "cross-tenant-access"
        return self.check(record(rec), module)

    def test_all_25_cells(self):
        for impact, row in EXPECTED.items():
            for likelihood, severity in zip(LIKELIHOODS, row):
                with self.subTest(impact=impact, likelihood=likelihood):
                    self.assertEqual(self.cell(impact, likelihood, severity)["problems"], [])
                    for other in ("critical", "high", "medium", "low"):
                        if other != severity:
                            self.assertIn("severity-off-table", codes(self.cell(impact, likelihood, other)))

    def test_a_copy_that_maps_high_impact_with_unknown_likelihood_one_level_up_fails_its_cell(self):
        edit = ('"high":     ("high", "high", "medium", "low", "low"),', '"high":     ("high", "high", "medium", "low", "medium"),')
        self.assertEqual(self.cell("high", "unknown", "low")["problems"], [])
        self.assertIn("severity-off-table", codes(self.cell("high", "unknown", "low", broken(edit))))

    def test_critical_needs_listed_severe_evidence(self):
        rec = confirmed(impact="severe", demonstrated_impact="severe", likelihood="demonstrated", severity="critical")
        self.assertCaught(record(rec), "critical-unsupported",
                          off('severity == "critical" and rec.get("critical_evidence") not in CRITICAL_EVIDENCE'))
        rec["critical_evidence"] = "cross-tenant-access"
        self.assertEqual(self.check(record(rec))["problems"], [])

    def test_a_self_only_xss_is_not_reported(self):
        rec = confirmed(rule="xss.reflected-self", reach="self-only", impact="moderate", demonstrated_impact="moderate",
                        severity="medium")
        self.assertCaught(record(rec), "reach-drops-out",
                          off('reach in ("self-only", "privileged-only") and rec.get("gains_privilege") is not True'))
        rec["gains_privilege"] = True
        self.assertNotIn("reach-drops-out", codes(self.check(record(rec))))

    def test_impact_is_capped_at_what_was_demonstrated(self):
        rec = confirmed(impact="severe", demonstrated_impact="moderate", severity="critical", critical_evidence="cross-tenant-access")
        self.assertCaught(record(rec), "impact-over-demonstrated", off("RANK_IMPACT[impact] > RANK_IMPACT[shown]"))

    def test_only_a_confirmed_finding_has_a_severity(self):
        note = {"id": "H1", "state": "hardening", "claim": "Session cookies lack SameSite.", "rule": "cookie.samesite",
                "anchor": "app/session.py::set_cookie", "severity": "low"}
        self.assertCaught(record(note), "severity-unconfirmed", off('state != "confirmed" and "severity" in rec'))

    def test_confidence_is_a_separate_field_that_never_moves_the_cell(self):
        for confidence in ("low", "medium", "high"):
            self.assertEqual(self.check(record(confirmed(confidence=confidence)))["problems"], [])
        self.assertIn("bad-confidence", codes(self.check(record(confirmed(confidence="0.9")))))

    def test_prompt_injection_is_rated_by_what_the_harness_let_through(self):
        # SC-21: text that only changes the model's prose is a hardening note; one that skips an approval is a finding.
        rec = confirmed(rule="prompt-injection.fetched-page", anchor="agent/fetch.py::render_page")
        self.assertCaught(record(rec), "injection-prose-only",
                          off('rule.startswith("prompt-injection") and rec.get("harness_effect") not in HARNESS_EFFECTS'))
        rec["harness_effect"] = "approval-skipped"
        self.assertEqual(self.check(record(rec))["problems"], [])
        note = {"id": "H2", "state": "hardening", "claim": "Injected page text changes the summary's tone only.",
                "rule": "prompt-injection.fetched-page", "anchor": "agent/fetch.py::summarise"}
        self.assertEqual(self.check(record(note))["problems"], [])


class AdmissionTests(Fixture):
    """GS-51 and SC-2: a finding is admitted only with the whole boundary tuple, after the class step."""
    TUPLE = ("principal", "source", "control", "sink", "path", "boundary", "resource", "result", "counterevidence", "proof_gaps")

    def test_each_tuple_field_is_required(self):
        for field in self.TUPLE:
            with self.subTest(field=field):
                rec = confirmed()
                del rec[field]
                result = self.check(record(rec))
                self.assertIn(("tuple-missing", field), {(p["code"], p["detail"]) for p in result["problems"]})

    def test_a_copy_without_the_counterevidence_field_lets_it_through(self):
        rec = confirmed()
        del rec["counterevidence"]
        edit = ('"result", "counterevidence", "proof_gaps")', '"result", "proof_gaps")')
        self.assertIn("tuple-missing", codes(self.check(record(rec))))
        self.assertNotIn("tuple-missing", codes(self.check(record(rec), broken(edit))))

    def test_an_operator_only_test_fixture_path_is_not_applicable_citing_the_class(self):
        rec = confirmed(surface="test-fixture", reach="privileged-only")
        self.assertCaught(record(rec), "class-not-reportable", off('surface != "shipped"'))
        filed = {"id": "F1", "state": "not-applicable", "claim": rec["claim"], "rule": rec["rule"], "anchor": rec["anchor"],
                 "surface": "test-fixture", "reach": "privileged-only"}
        self.assertEqual(self.check(record(filed))["problems"], [])

    def test_not_applicable_must_cite_the_class(self):
        filed = {"id": "N1", "state": "not-applicable", "claim": "Not a problem.", "rule": "x", "anchor": "a::b",
                 "surface": "shipped", "reach": "other-users"}
        self.assertCaught(record(filed), "not-applicable-unexplained",
                          off('rec.get("surface") in (None, "shipped") and rec.get("reach") not in ("self-only", "privileged-only")'))


class SnippetTests(Fixture):
    """SC-6: each confirmed finding's snippets equal the lines they cite, read from disk under ROOT."""
    EDIT = off("lines_text != expected")

    def with_snippet(self, **changes):
        rec = confirmed()
        rec["snippets"][1].update(changes)
        return record(rec)

    def test_a_paraphrased_snippet_fails_and_the_path_only_copy_passes_it(self):
        data = self.with_snippet(text="    invoice = Invoice.load(id)\n    return invoice.to_json()")
        self.assertIn("snippet-mismatch", codes(self.check(data)))
        self.assertNotIn("snippet-mismatch", codes(self.check(data, broken(self.EDIT))))

    def test_a_shifted_snippet_fails_and_the_path_only_copy_passes_it(self):
        data = self.with_snippet(lines=[6, 7])
        self.assertIn("snippet-mismatch", codes(self.check(data)))
        self.assertNotIn("snippet-mismatch", codes(self.check(data, broken(self.EDIT))))

    def test_a_missing_file_still_fails_in_the_path_only_copy(self):
        data = self.with_snippet(file="app/gone.py")
        self.assertIn("snippet-unreadable", codes(self.check(data, broken(self.EDIT))))

    def test_a_snippet_outside_root_is_refused(self):
        for bad in ("../outside.py", "/etc/passwd", "C:/Windows/win.ini", "app/../../x.py"):
            with self.subTest(file=bad):
                self.assertIn("snippet-outside-root", codes(self.check(self.with_snippet(file=bad))))

    def test_crlf_source_compares_line_by_line(self):
        (self.root / "app" / "invoices.py").write_bytes(INVOICES.replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(self.check(record(confirmed()))["problems"], [])

    def test_a_confirmed_finding_without_snippets_is_refused(self):
        self.assertIn("snippets-missing", codes(self.check(record(confirmed(snippets=[])))))


class IdentityTests(Fixture):
    """SC-12: identity is rule family, root-control anchor and an instance key per attackable sibling."""

    def test_two_controllers_missing_the_same_check_are_two_instances(self):
        first = confirmed(id="F1", instance="GET /invoices/{id}")
        second = confirmed(id="F2", instance="GET /receipts/{id}")
        self.assertEqual(self.check(record(first, second))["problems"], [])

    def test_the_same_instance_twice_is_a_duplicate(self):
        self.assertCaught(record(confirmed(id="F1"), confirmed(id="F2")), "duplicate-identity", off("key in seen_keys"))

    def test_an_anchor_never_carries_a_line_number(self):
        for anchor in ("app/invoices.py:5", "app/invoices.py#L5", "get_invoice line 5"):
            with self.subTest(anchor=anchor):
                self.assertIn("anchor-has-line", codes(self.check(record(confirmed(anchor=anchor)))))
        data = record(confirmed(anchor="app/invoices.py:5"))
        self.assertNotIn("anchor-has-line", codes(self.check(data, broken(("elif LINE_IN_ANCHOR.search(anchor):", "elif False:")))))


class TriageTests(Fixture):
    """SC-5, SC-28 and SC-11: supplied findings, abstentions and carried dismissals."""

    def test_needs_review_names_the_smallest_missing_fact(self):
        rec = {"id": "T1", "state": "needs-review", "claim": "The upload size limit may be bypassable.", "rule": "dos.upload",
               "anchor": "app/upload.py::receive"}
        self.assertCaught(record(rec), "missing-fact", off('not _text(rec.get("missing_fact"))'))

    def test_not_actionable_needs_positive_evidence(self):
        rec = {"id": "T2", "state": "not-actionable", "claim": "Scanner: SQL injection in report query.",
               "rule": "sqli.report", "anchor": "app/report.py::query", "positive_evidence": []}
        self.assertCaught(record(rec), "not-actionable-unsupported", off('not _nonempty(rec.get("positive_evidence"))'))
        rec["positive_evidence"] = ["the only caller passes a bound parameter on every shipped path (app/report.py, both configs)"]
        self.assertEqual(self.check(record(rec))["problems"], [])

    def three(self):
        a = confirmed(id="A", instance="a", impact="moderate", demonstrated_impact="moderate", likelihood="possible",
                      severity="medium", scanner_severity="CRITICAL")
        b = confirmed(id="B", instance="b", impact="high", demonstrated_impact="high", likelihood="likely", severity="high",
                      scanner_severity="LOW")
        c = confirmed(id="C", instance="c", impact="low", demonstrated_impact="low", likelihood="demonstrated", severity="low",
                      scanner_severity="HIGH")
        return record(a, b, c)

    def order(self, module, data):
        _, markdown = module.render(data, "0" * 64, str(self.root))
        return re.findall(r"^\d+\. \[\w+\] (\w+):", markdown, re.M)

    def test_findings_rank_by_exploitability_and_scanner_severity_comes_last(self):
        self.assertEqual(self.order(sa, self.three()), ["B", "A", "C"])
        scanner = 'key=lambda r: ("critical", "high", "medium", "low", "").index(str(r.get("scanner_severity", "")).lower())'
        self.assertEqual(self.order(broken(("key=_rank", scanner)), self.three()), ["A", "C", "B"])

    def test_an_abstention_is_listed_and_counted_never_clean(self):
        gap = {"id": "U1", "state": "not-assessed", "claim": "The admin export path was not traced.",
               "settle": "trace export_all from its route to the storage call"}
        data = record(confirmed(), gap)
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: partial (1 not assessed)", markdown)
        self.assertIn("## Not assessed (abstentions) (1)", markdown)
        self.assertIn("U1: The admin export path was not traced.", markdown)
        _, control = broken(off('counts["not-assessed"]')).render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", control, "the broken copy shows a clean result, which the test catches")

    def test_an_abstention_says_what_would_settle_it(self):
        gap = {"id": "U1", "state": "not-assessed", "claim": "The admin export path was not traced."}
        self.assertCaught(record(gap), "settle-missing", off('not _text(rec.get("settle"))'))

    def dismissed(self, reason="checked_url refuses every scheme but https before the fetch"):
        return {"id": "D1", "state": "dismissed", "claim": "SSRF through the webhook URL.", "rule": "ssrf.webhook",
                "anchor": "app/hooks.py::deliver", "reason": reason,
                "basis": {"role": "root-control", "file": "app/validate.py", "lines": [2, 3],
                          "text": '    if not url.startswith("https://"):\n        raise ValueError(url)'}}

    def test_a_bare_label_never_dismisses(self):
        for label in ("false positive", "FP", "won't fix", "by design."):
            with self.subTest(label=label):
                self.assertIn("dismissal-bare", codes(self.check(record(self.dismissed(label)))))
        self.assertCaught(record(self.dismissed("false positive")), "dismissal-bare", off('_bare(rec.get("reason"))'))

    def test_a_dismissal_returns_when_the_validation_it_cites_is_deleted(self):
        data = record(self.dismissed())
        self.assertEqual(self.check(data)["problems"], [])
        (self.root / "app" / "validate.py").write_text("def checked_url(url):\n    return url\n", encoding="utf-8")
        self.assertCaught(data, "dismissal-lapsed", off("basis_problem"))


def labelled(level, *checks, state="needs-review", **changes):
    """An intake record carrying a risk label combined from named independent checks."""
    rec = {"id": "K1", "state": state, "claim": "The files MCP server may read outside the project folder.",
           "rule": "intake.mcp-launcher", "anchor": ".mcp.json::files", "missing_fact": "what @acme/mcp-files 2.1.0 reads",
           "settle": "read the package at its pinned release", "positive_evidence": ["the launcher is pinned and vetted"],
           "risk": {"level": level, "checks": [{"name": "check %d" % n, "level": c} for n, c in enumerate(checks, 1)]}}
    rec.update(changes)
    return rec


class RiskTests(Fixture):
    """GS-31: a risk label keeps "could not assess" apart from low; independent checks combine by the worst concrete
    level, a check that raised counts as high, all-unknown stays unknown, and unknown asks."""

    def test_checks_combine_by_the_worst_concrete_level(self):
        self.assertEqual(self.check(record(labelled("medium", "low", "medium", "unknown")))["problems"], [])
        self.assertCaught(record(labelled("low", "low", "medium", "unknown")), "risk-off-combination",
                          ("max(concrete, key=RANK_RISK.get)", "min(concrete, key=RANK_RISK.get)"))

    def test_a_check_that_raised_counts_as_high(self):
        self.assertEqual(self.check(record(labelled("high", "low", "error")))["problems"], [])
        self.assertCaught(record(labelled("low", "low", "error")), "risk-off-combination",
                          ('"high" if level == "error" else level', '"low" if level == "error" else level'))

    def test_could_not_assess_is_never_low(self):
        self.assertEqual(self.check(record(labelled("unknown", "unknown", "unknown")))["problems"], [])
        self.assertEqual(self.check(record(labelled("high", "unknown", "high")))["problems"], [])
        self.assertCaught(record(labelled("low", "unknown", "unknown")), "risk-off-combination",
                          ('return "unknown"', 'return "low"'))

    def test_unknown_asks(self):
        for state in ("needs-review", "not-assessed"):
            self.assertEqual(self.check(record(labelled("unknown", "unknown", state=state)))["problems"], [])
        cleared = record(labelled("unknown", "unknown", state="not-actionable"))
        self.assertCaught(cleared, "risk-unknown-unasked", off('risk["level"] == "unknown" and state not in ASKING'))
        _, markdown = sa.render(record(labelled("unknown", "unknown")), "0" * 64, str(self.root))
        self.assertIn("Audit status: partial (1 need review)", markdown)

    def test_a_risk_label_names_its_checks(self):
        for bad in ({"level": "low", "checks": []}, {"level": "safe", "checks": [{"name": "a", "level": "low"}]},
                    {"level": "low", "checks": [{"name": "", "level": "low"}]},
                    {"level": "low", "checks": [{"name": "a", "level": "fine"}]}, "low"):
            with self.subTest(risk=bad):
                self.assertIn("risk-malformed", codes(self.check(record(labelled("low", "low", risk=bad)))))
        self.assertCaught(record(labelled("low", "low", risk={"level": "low", "checks": []})), "risk-malformed",
                          off("not well_formed"))

    def test_the_report_shows_each_label_with_its_checks(self):
        _, markdown = sa.render(record(labelled("unknown", "unknown", "unknown")), "0" * 64, str(self.root))
        self.assertIn("## Risk labels (1)", markdown)
        self.assertIn("- K1: unknown (check 1: unknown; check 2: unknown)", markdown)


ABSENCE = {"identifiers": ["OLD_WEBHOOK_SECRET", "1f3e9a7"], "secret": True,
           "rotated": "revoked at the provider and reissued before the history rewrite",
           "copies": [{"copy": "working tree", "probe": "Select-String -Pattern OLD_WEBHOOK_SECRET -Path app/*", "result": "absent"},
                      {"copy": "origin, fresh clone", "probe": "git cat-file -e 1f3e9a7", "result": "absent"},
                      {"copy": "CI cache", "probe": "search the cache archive for OLD_WEBHOOK_SECRET", "result": "absent"}]}


def removed(**changes):
    """A fix record that claims a committed secret is gone (WB-78: a claim of absence, probed on every copy)."""
    absence = copy.deepcopy(ABSENCE)
    absence.update(changes)
    return {"id": "X1", "state": "hardening", "claim": "The unused webhook secret was removed and its history purged.",
            "rule": "secret.committed", "anchor": "app/legacy.py::OLD_WEBHOOK_SECRET", "absence": absence}


class AbsenceTests(Fixture):
    """WB-78: a removal is a claim of absence, proved by a probe of the exact pre-change identifiers on every copy that is
    expected to fail; a hit names the survivor, and an exposed secret is rotated before history is purged."""

    def test_the_fixture_removal_is_clean(self):
        self.assertEqual(self.check(record(removed()))["problems"], [])

    def test_every_listed_copy_is_probed(self):
        self.assertIn("absence-unprobed", codes(self.check(record(removed(copies=[])))))
        skipped = removed()
        skipped["absence"]["copies"][2]["result"] = "not-run"
        self.assertCaught(record(skipped), "absence-unprobed",
                          off('not copies or any(c["result"] == "not-run" for c in copies)'))

    def test_a_probe_names_an_exact_pre_change_identifier(self):
        vague = removed()
        vague["absence"]["copies"][1]["probe"] = "git log --all looks clean"
        self.assertCaught(record(vague), "absence-probe-inexact",
                          off('not any(i in c["probe"] for i in absence["identifiers"])'))

    def test_a_hit_names_the_survivor(self):
        survivor = removed()
        survivor["absence"]["copies"][2]["result"] = "present"
        result = self.check(record(survivor))
        self.assertIn(("absence-survivor", "CI cache still holds a pre-change identifier: the removal is not done"),
                      {(p["code"], p["detail"]) for p in result["problems"]})
        self.assertCaught(record(survivor), "absence-survivor", off('c["result"] == "present"'))

    def test_an_exposed_secret_is_rotated_before_the_purge(self):
        self.assertCaught(record(removed(rotated="")), "absence-unrotated",
                          off('absence.get("secret") is True and not _text(absence.get("rotated"))'))
        self.assertEqual(self.check(record(removed(secret=False, rotated="")))["problems"], [])

    def test_a_malformed_claim_is_refused(self):
        for bad in ({"identifiers": [], "copies": []}, {"identifiers": ["x"], "copies": [{"copy": "a", "result": "absent"}]},
                    {"identifiers": ["x"], "copies": [{"copy": "a", "probe": "x", "result": "gone"}]}, "removed"):
            with self.subTest(absence=bad):
                rec = removed()
                rec["absence"] = bad
                self.assertIn("absence-malformed", codes(self.check(record(rec))))
        rec = removed()
        rec["absence"] = {"identifiers": [], "copies": []}
        self.assertCaught(record(rec), "absence-malformed", off("not shaped"))

    def test_the_report_lists_each_copy_and_its_result(self):
        _, markdown = sa.render(record(removed()), "0" * 64, str(self.root))
        self.assertIn("## Absence probes (1)", markdown)
        self.assertIn("- X1: OLD_WEBHOOK_SECRET, 1f3e9a7 probed on working tree (absent), origin, fresh clone (absent), "
                      "CI cache (absent); rotated: revoked at the provider and reissued before the history rewrite", markdown)


SEEDED_KEY = "FAKEKEY_" + "Q7mZ2xR9vL4kT8wN3pB6"  # made up; matches only the stub's own rule
GOOD_FLAGS = ("--config", "reviewed.toml", "--ignore-gitleaks-allow", "--exit-code", "2", "--redact")
REVIEWED = 'title = "reviewed by the auditor"\n'  # the auditor's own config: no allow-list


class ScanFixture(Fixture):
    """Receipts from the stub scanner, which reproduces the exit codes and log lines the brief cites; nothing real is run."""

    def setUp(self):
        super().setUp()
        self.scanned = pathlib.Path(self.temp.name) / "scanned"
        for relative, text in (("tree/app/__init__.py", "# package\n"), ("tree/app/settings.py", "API_URL = 'https://api.example'\n"),
                               ("history/README.md", "# service\n"), ("history/app/settings.py@a1b2c3", "API_KEY = '%s'\n" % SEEDED_KEY)):
            path = self.scanned / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (pathlib.Path(self.temp.name) / "reviewed.toml").write_text(REVIEWED, encoding="utf-8")

    def receipt(self, scope, flags=GOOD_FLAGS, stub_only=(), result=None, tool="betterleaks", folder=None, **extra):
        report = pathlib.Path(self.temp.name) / ("report-%s.json" % scope)
        report.write_text("[]", encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(STUB), scope, str(folder or self.scanned), *flags, *stub_only,
                               "--report-path", str(report)], capture_output=True, text=True, encoding="utf-8",
                              cwd=self.temp.name)
        receipt = {"tool": tool, "version": "1.9.0", "command": " ".join((tool, scope, ".") + tuple(flags)),
                   "config": "reviewed.toml" if "--config" in flags else ".betterleaks.toml", "scope": scope,
                   "exit": proc.returncode, "log": proc.stdout,
                   "report_findings": len(json.loads(report.read_text(encoding="utf-8"))), "result": result}
        if scope == "git":
            receipt.update(shallow=False, refs="all local refs (git log --all)")
        receipt.update(extra)
        return receipt


class SecretScanTests(ScanFixture):
    """SC-27 and SC-33 to SC-35: a secret-scan receipt, its exit code and log read together, both scopes, redaction on and
    live validation off."""

    def scanned_record(self, *receipts):
        return record(confirmed(), secret_scans=list(receipts))

    def test_the_tree_scan_misses_a_deleted_key_and_the_history_scan_finds_it(self):
        tree, history = self.receipt("dir", result="clean"), self.receipt("git", result="findings")
        self.assertEqual((tree["exit"], history["exit"]), (0, 2))
        data = self.scanned_record(tree, history)
        self.assertEqual(self.check(data)["problems"], [])
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", markdown)
        self.assertIn("## Secret scans (2)", markdown)
        self.assertIn("- betterleaks 1.9.0, git: findings (exit 2; config reviewed.toml)", markdown)
        self.assertNotIn(SEEDED_KEY, json.dumps(data) + markdown)

    def test_one_scope_alone_is_partial(self):
        data = self.scanned_record(self.receipt("dir", result="clean"))
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: partial (secret scan: git history not scanned)", markdown)
        _, control = broken(off('"git" not in done')).render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", control, "the tree-only copy reads clean, which the test catches")

    def test_a_partial_scan_reads_not_run_never_clean(self):
        partial = self.receipt("git", stub_only=("--partial",), result="clean")
        self.assertEqual((partial["exit"], partial["report_findings"]), (1, 0))
        self.assertIn("no leaks found in partial scan", partial["log"])
        trusting = ('    log = scan.get("log") or ""\n',
                    '    return "findings" if scan.get("report_findings") else "clean"\n')
        self.assertCaught(self.scanned_record(self.receipt("dir", result="clean"), partial), "scan-misread", trusting)
        honest = self.scanned_record(self.receipt("dir", result="clean"), dict(partial, result="not-run"))
        self.assertEqual(self.check(honest)["problems"], [])
        _, markdown = sa.render(honest, "0" * 64, str(self.root))
        self.assertIn("secret scan not-run: betterleaks git", markdown)

    def test_the_findings_exit_code_is_set_apart_from_failure(self):
        default = self.receipt("git", flags=("--redact",), result="not-run")
        self.assertEqual(default["exit"], 1, "with the default, findings and failures both exit 1")
        self.assertCaught(self.scanned_record(self.receipt("dir", result="clean"), default), "scan-exit-ambiguous",
                          off("not EXIT_TWO.search(command)"))

    def test_output_is_redacted(self):
        loud = self.receipt("git", flags=("--exit-code", "2"), result="findings")
        data = self.scanned_record(self.receipt("dir", result="clean"), loud)
        self.assertCaught(data, "scan-unredacted", off('not redact or redact.group(1) == "0"'))
        self.assertIn(SEEDED_KEY, json.dumps(data), "without --redact the key is in the receipt; a grep catches it")
        zero = self.receipt("git", flags=("--exit-code", "2", "--redact=0"), result="findings")
        self.assertIn("scan-unredacted", codes(self.check(self.scanned_record(self.receipt("dir", result="clean"), zero))))

    def test_live_validation_stays_off(self):
        probing = self.receipt("git", flags=GOOD_FLAGS + ("--validation",), result="findings")
        data = self.scanned_record(self.receipt("dir", result="clean"), probing)
        self.assertCaught(data, "scan-validation", off("_validation_on(command)"))
        off_flag = self.receipt("git", flags=GOOD_FLAGS + ("--validation=false",), result="findings")
        self.assertEqual(self.check(self.scanned_record(self.receipt("dir", result="clean"), off_flag))["problems"], [])

    def test_a_receipt_names_tool_version_command_config_and_scope(self):
        bare = self.receipt("dir", result="clean")
        del bare["config"]
        self.assertCaught(self.scanned_record(bare, self.receipt("git", result="findings")), "scan-malformed",
                          off("not complete_receipt"))
        for change in ({"scope": "tree"}, {"exit": "0"}, {"result": "ok"}, {"version": ""}):
            with self.subTest(change=change):
                self.assertIn("scan-malformed", codes(self.check(self.scanned_record(dict(bare, config="x", **change)))))

    def test_validation_on_by_default_needs_its_off_switch(self):
        """SC-35 amended: TruffleHog, Kingfisher and detect-secrets validate unless told not to. Only command lines are
        asserted here; no scanner of these three is stubbed or run."""

        def run(tool, command):
            return {"tool": tool, "version": "x", "command": command, "config": "built-in default", "scope": "dir",
                    "exit": 0, "log": "", "result": "not-run"}

        probing = (run("trufflehog", "trufflehog filesystem . --fail --no-update"), run("kingfisher", "kingfisher scan ."),
                   run("detect-secrets", "detect-secrets scan --all-files"))
        quiet = (run("trufflehog", "trufflehog filesystem . --fail --no-verification --no-update"),
                 run("kingfisher", "kingfisher scan . --no-validate"), run("detect-secrets", "detect-secrets scan -n"),
                 run("detect-secrets", "detect-secrets scan --no-verify"))
        for receipt in probing:
            with self.subTest(command=receipt["command"]):
                self.assertCaught(self.scanned_record(receipt), "scan-validation",
                                  off('_validates_by_default(scan.get("tool"), command)'))
        for receipt in quiet:
            with self.subTest(command=receipt["command"]):
                self.assertNotIn("scan-validation", codes(self.check(self.scanned_record(receipt))))

    def test_a_shallow_clone_reads_partial(self):
        """SC-34 addition: the deleted key sits below the clone's depth, so the shallow history scan reads clean."""
        shallow = pathlib.Path(self.temp.name) / "shallow"
        for relative, text in (("tree/app/__init__.py", "# package\n"), ("history/README.md", "# service\n")):
            (shallow / relative).parent.mkdir(parents=True, exist_ok=True)
            (shallow / relative).write_text(text, encoding="utf-8")
        history = self.receipt("git", result="clean", folder=shallow, shallow=True, refs="main (depth 1)")
        self.assertEqual(history["exit"], 0)
        data = self.scanned_record(self.receipt("dir", result="clean", folder=shallow), history)
        self.assertEqual(self.check(data)["problems"], [])
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("secret scan: betterleaks git from a shallow clone", markdown)
        self.assertIn("Audit status: partial", markdown)
        _, control = broken(('s.get("scope") == "git" and s.get("shallow") is True', "False")).render(
            data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", control, "a copy that trusts the shallow history reads clean")

    def test_a_history_receipt_records_shallow_and_refs(self):
        for missing in ("shallow", "refs"):
            receipt = self.receipt("git", result="findings")
            del receipt[missing]
            with self.subTest(missing=missing):
                self.assertCaught(self.scanned_record(self.receipt("dir", result="clean"), receipt), "scan-malformed",
                                  off('scan.get("scope") == "git" and not history_fields'))
        self.assertIn("scan-malformed", codes(self.check(self.scanned_record(
            self.receipt("dir", result="clean"), self.receipt("git", result="findings", shallow="no")))))


LITERAL = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


class AllowListTests(Fixture):
    """SC-36: suppress by fingerprint or path, never by the secret's value; an audit flags a literal high-entropy value in
    the recorded scanner config's allow-list."""

    def scan(self, config=".betterleaks.toml"):
        return {"tool": "betterleaks", "version": "1.9.0", "scope": "dir", "exit": 0, "log": "INF no leaks found\n",
                "command": "betterleaks dir . --config %s --ignore-gitleaks-allow --exit-code 2 --redact" % config,
                "config": config, "result": "clean"}

    def configured(self, text):
        # The project's own config, read by the auditor and then passed with --config: a record anchored at the file
        # says it was reviewed (SC-38); its allow-list entries are judged on their own (SC-36).
        (self.root / ".betterleaks.toml").write_text(text, encoding="utf-8")
        reviewed = {"id": "S0", "state": "not-actionable", "claim": "The project's own Betterleaks config was reviewed.",
                    "rule": "secret.target-suppression", "anchor": ".betterleaks.toml",
                    "positive_evidence": "read in full before it was passed with --config"}
        return record(confirmed(), reviewed, secret_scans=[self.scan()])

    def test_a_literal_value_in_the_allow_list_is_flagged_without_printing_it(self):
        data = self.configured("[allowlist]\ndescription = \"fixtures\"\nregexes = ['''(?i)example''', '''%s''']\n"
                               "paths = ['''docs/''']\n" % LITERAL)
        result = self.check(data)
        self.assertIn(("allowlist-literal", ".betterleaks.toml: allowlist.regexes[1] is a literal high-entropy value; "
                       "suppress it by fingerprint or path"), {(p["code"], p["detail"]) for p in result["problems"]})
        self.assertNotIn(LITERAL, json.dumps(result))
        self.assertCaught(data, "allowlist-literal", off("config_path is not None and config_path.is_file()"))

    def test_patterns_paths_and_the_newer_table_form(self):
        self.assertEqual(self.check(self.configured("[allowlist]\nregexes = ['''(?i)example''', '''^test-[0-9]+$''']\n"
                                                    "paths = ['''docs/9f86d081884c7d659a2f''']\n"))["problems"], [])
        data = self.configured("[[allowlists]]\nstopwords = ['''%s''']\n[[rules]]\nid = \"x\"\n[[rules.allowlists]]\n"
                               "regexes = ['''%s''']\n" % (LITERAL, LITERAL[:24]))
        self.assertEqual(sum(p["code"] == "allowlist-literal" for p in self.check(data)["problems"]), 2)

    def test_a_record_anchored_at_the_entry_settles_it(self):
        data = self.configured("[allowlist]\nregexes = ['''%s''']\n" % LITERAL)
        self.assertIn("allowlist-literal", codes(self.check(data)))
        data["records"].append({"id": "S1", "state": "hardening", "claim": "The scanner config allow-lists a token by its value.",
                                "rule": "secret.allowlist-literal", "anchor": ".betterleaks.toml::allowlist.regexes[0]"})
        self.assertEqual(self.check(data)["problems"], [])

    def test_an_unparsable_config_is_reported(self):
        self.assertIn("scan-config-unreadable", codes(self.check(self.configured("[allowlist\nregexes = ["))))

    def test_a_config_outside_the_root_or_a_built_in_default_is_not_read(self):
        self.assertEqual(self.check(record(confirmed(), secret_scans=[self.scan("built-in default")]))["problems"], [])


SETTINGS = "history/app/settings.py@a1b2c3"


def suppressed_target(folder, ignore_file=True):
    """A project that hides the seeded key three ways (SC-38): an allow-list in its own .betterleaks.toml, a fingerprint in
    its .betterleaksignore and an inline betterleaks:allow comment on the key's line."""
    for relative, text in (("tree/app/__init__.py", "# package\n"), ("history/README.md", "# service\n"),
                           (SETTINGS, "API_KEY = '%s'  # betterleaks:allow\n" % SEEDED_KEY),
                           (".betterleaks.toml", "[allowlist]\npaths = ['''history/app/settings''']\n")):
        path = pathlib.Path(folder) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if ignore_file:
        (pathlib.Path(folder) / ".betterleaksignore").write_text("%s:fake-key:1\n" % SETTINGS, encoding="utf-8")


class TargetSuppressionTests(ScanFixture):
    """SC-38: the scanned project never configures its own scan. The stub honours the target's config, ignore file and
    inline allow comments as Betterleaks 1.9.0 does; `suppressions` lists them and `check` wants each reviewed."""

    def setUp(self):
        super().setUp()
        suppressed_target(self.root)

    def anchored(self):
        return [{"id": "T%d" % n, "state": "needs-review", "claim": "The project suppresses a secret-scan finding itself.",
                 "rule": "secret.target-suppression", "anchor": anchor, "missing_fact": "whether the suppressed value is live"}
                for n, anchor in enumerate((".betterleaks.toml", ".betterleaksignore", SETTINGS + "::betterleaks:allow"), 1)]

    def target_record(self, *receipts, anchored=True):
        data = record(confirmed(), *(self.anchored() if anchored else ()), secret_scans=list(receipts))
        return data

    def test_a_bare_run_obeys_the_project_reads_clean_and_is_caught(self):
        bare = self.receipt("git", flags=("--exit-code", "2", "--redact"), result="clean", folder=self.root)
        self.assertEqual(bare["exit"], 0, "the project's own config, ignore file and comment hide the key")
        self.assertIn("no leaks found", bare["log"])
        data = self.target_record(self.receipt("dir", result="clean", folder=self.root), bare)
        self.assertCaught(data, "scan-target-config", off("not CONFIG_FLAG.search(command)"))
        self.assertCaught(data, "scan-inline-allow", off("not INLINE_OFF.search(command)"))

    def test_the_reviewed_run_still_obeys_the_ignore_file_so_it_is_listed(self):
        reviewed = self.receipt("git", result="clean", folder=self.root)
        self.assertEqual(reviewed["exit"], 0, "no flag stops the project's ignore file")
        copy = pathlib.Path(self.temp.name) / "copy-without-ignore-file"
        suppressed_target(copy, ignore_file=False)
        found = self.receipt("git", result="findings", folder=copy)
        self.assertEqual(found["exit"], 2)
        self.assertIn("leaks found: 1", found["log"])
        self.assertEqual(self.check(self.target_record(self.receipt("dir", result="clean", folder=self.root),
                                                       reviewed))["problems"], [])

    def test_check_wants_each_project_suppression_reviewed(self):
        data = self.target_record(self.receipt("dir", result="clean", folder=self.root),
                                  self.receipt("git", result="clean", folder=self.root), anchored=False)
        details = [p["detail"] for p in self.check(data)["problems"] if p["code"] == "suppression-unreviewed"]
        self.assertEqual(len(details), 3, details)
        self.assertTrue(any(d.startswith(SETTINGS + " (line 1)") for d in details), details)
        self.assertNotIn(SEEDED_KEY, json.dumps(self.check(data)))
        self.assertCaught(data, "suppression-unreviewed", off("anchor not in anchors"))

    def test_suppressions_lists_all_three_and_never_the_line(self):
        code, listing = self.run_cli("suppressions", str(self.root))
        self.assertEqual((code, listing["status"]), (1, "findings"))
        self.assertEqual({(f["path"], f["kind"]) for f in listing["files"]},
                         {(".betterleaks.toml", "config"), (".betterleaksignore", "ignore")})
        self.assertEqual([(m["path"], m["line"], m["marker"]) for m in listing["markers"]],
                         [(SETTINGS, 1, "betterleaks:allow")])
        self.assertNotIn(SEEDED_KEY, json.dumps(listing))
        no_files = broken(off("pattern.fullmatch(name)")).suppressions(self.root)
        self.assertEqual(no_files["files"], [], "a copy that skips the file names misses the config and ignore file")
        no_markers = broken(("found = _file_markers(path)", "found = []")).suppressions(self.root)
        self.assertEqual(no_markers["markers"], [], "a copy that skips the comments misses the inline allow")

    def test_every_name_and_marker_in_the_table(self):
        folder = pathlib.Path(self.temp.name) / "many"
        for relative, text in ((".gitleaks.toml", ""), (".gitleaksignore", ""), ("kingfisher.yaml", ""),
                               (".secrets.baseline", "{}"), (".secretlintignore", ""), (".secretlintrc.json", "{}"),
                               ("sub/.betterleaksignore", ""), (".git/.gitleaks.toml", ""), ("README.md", "# plain\n"),
                               ("a.py", "x = 1  # gitleaks:allow\ny = 2  # trufflehog:ignore\n"),
                               ("b.py", "s = 'v'  # pragma: allowlist secret\n# pragma: allowlist nextline secret\nt = 1\n"),
                               ("c.js", "// secretlint-disable-next-line\nconst k = 1\n")):
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        listing = sa.suppressions(folder)
        self.assertEqual({(f["path"], f["kind"], f["tools"]) for f in listing["files"]},
                         {(".gitleaks.toml", "config", "betterleaks, gitleaks"),
                          (".gitleaksignore", "ignore", "betterleaks, gitleaks"), ("kingfisher.yaml", "config", "kingfisher"),
                          (".secrets.baseline", "baseline", "detect-secrets"), (".secretlintignore", "ignore", "secretlint"),
                          (".secretlintrc.json", "config", "secretlint"), ("sub/.betterleaksignore", "ignore", "betterleaks")})
        self.assertEqual([(m["path"], m["line"], m["marker"], m["tools"]) for m in listing["markers"]],
                         [("a.py", 1, "gitleaks:allow", "betterleaks, gitleaks"), ("a.py", 2, "trufflehog:ignore", "trufflehog"),
                          ("b.py", 1, "pragma: allowlist secret", "detect-secrets"),
                          ("b.py", 2, "pragma: allowlist nextline secret", "detect-secrets"),
                          ("c.js", 1, "secretlint-disable", "secretlint")])
        clean = pathlib.Path(self.temp.name) / "clean"
        (clean / "app").mkdir(parents=True)
        (clean / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(self.run_cli("suppressions", str(clean))[:1], (0,))
        self.assertEqual(self.run_cli("suppressions", str(clean))[1]["status"], "clean")

    def test_a_comment_across_a_read_boundary_is_found_once(self):
        folder = pathlib.Path(self.temp.name) / "big"
        folder.mkdir()
        size = sa.MARKER_CHUNK
        (folder / "big.txt").write_bytes(b"a\n" + b"x" * (size - 8) + b"gitleaks:allow\n" + b"z\n")
        self.assertEqual([(m["line"], m["marker"]) for m in sa.suppressions(folder)["markers"]], [(2, "gitleaks:allow")])
        no_overlap = broken(("carry = data[-MARKER_OVERLAP:]", "carry = b''"))
        self.assertEqual(no_overlap.suppressions(folder)["markers"], [], "without the overlap the comment is split and lost")

    def test_an_unreadable_file_is_reported_never_passed(self):
        def deny(path):
            raise OSError("denied")
        data = self.target_record(self.receipt("dir", result="clean", folder=self.root),
                                  self.receipt("git", result="clean", folder=self.root))
        original = sa._file_markers
        sa._file_markers = deny
        try:
            self.assertIn("suppressions-unread", codes(self.check(data)))
            code, listing = self.run_cli("suppressions", str(self.root))
            self.assertEqual(code, 1, "files were still listed")
            self.assertTrue(listing["unread"])
        finally:
            sa._file_markers = original
        control = broken(off('listing["unread"]'))
        control._file_markers = deny
        self.assertNotIn("suppressions-unread", codes(self.check(data, control)))


AUTH_TEXT = ("GET /v1/charges HTTP/1.1\nAuthorization: Bearer abc.def.ghi\nCookie: a=1; b=2\nX-Api-Key: zz9top\n"
             "run --password=hunter2 user=ann\nauthor=Ann Lee\nkeyboard=qwerty\ncurl -H \"Authorization: Basic dXNlcjpw\" /x\n")
AUTH_JSON = {"apiKey": 1234, "author": "Ann", "keyboard": "qwerty", "count": 3,
             "headers": {"Authorization": "Bearer abc.def.ghi", "Cookie": "sid=abc; theme=dark"},
             "nested": {"client_secret": {"a": 1}}, "items": [{"token": "t1"}, {"note": "password=hunter2"}]}


class RedactTests(Fixture):
    """SC-37: scrub a receipt, note or brief before it is written: auth headers keep the scheme, cookies their names, and
    values under secret-named keys become <redacted>, numbers too, matched by whole name parts."""

    def redact(self, content, module=None, name="input.txt"):
        path = pathlib.Path(self.temp.name) / name
        path.write_bytes((content if isinstance(content, str) else json.dumps(content)).encode("utf-8"))
        if module is not None:
            return module.redact_text(path.read_bytes().decode("utf-8"))
        code, report = self.run_cli("redact", str(path))
        return code, report

    def test_text_keeps_schemes_and_cookie_names_and_drops_values(self):
        code, report = self.redact(AUTH_TEXT)
        self.assertEqual((code, report["status"], report["kind"]), (1, "redacted", "text"))
        text = report["text"]
        for kept in ("Authorization: Bearer <redacted>", "Cookie: a=<redacted>; b=<redacted>", "X-Api-Key: <redacted>",
                     "--password=<redacted> user=ann", "author=Ann Lee", "keyboard=qwerty",
                     "\"Authorization: Basic <redacted>\" /x", "GET /v1/charges HTTP/1.1"):
            self.assertIn(kept, text)
        for gone in ("abc.def.ghi", "hunter2", "zz9top", "dXNlcjpw"):
            self.assertNotIn(gone, json.dumps(report))

    def test_json_redacts_numbers_and_containers_under_secret_names(self):
        code, report = self.redact(AUTH_JSON, name="input.json")
        self.assertEqual((code, report["kind"]), (1, "json"))
        out = json.loads(report["text"])
        self.assertEqual(out["apiKey"], "<redacted>")
        self.assertEqual((out["author"], out["keyboard"], out["count"]), ("Ann", "qwerty", 3))
        self.assertEqual(out["headers"], {"Authorization": "Bearer <redacted>", "Cookie": "sid=<redacted>; theme=<redacted>"})
        self.assertEqual(out["nested"]["client_secret"], "<redacted>")
        self.assertEqual(out["items"], [{"token": "<redacted>"}, {"note": "password=<redacted>"}])

    def test_a_copy_that_redacts_strings_only_leaks_the_number(self):
        leaky = broken(("    if value is None:\n", "    if not isinstance(value, str):\n"))
        text, _ = self.redact(AUTH_JSON, leaky, name="input.json")
        self.assertEqual(json.loads(text)["apiKey"], 1234, "the broken copy leaks it, which the test catches")

    def test_a_copy_that_matches_substrings_blanks_author(self):
        loose = broken(("any(part in SECRET_PARTS for part in parts)",
                        "any(fragment in str(name).lower() for fragment in SECRET_PARTS)"))
        text, _ = self.redact(AUTH_TEXT, loose)
        self.assertIn("author=<redacted>", text, "the substring copy blanks author, which the test catches")
        self.assertIn("keyboard=<redacted>", text)

    def test_nothing_to_redact_is_clean_and_unchanged(self):
        code, report = self.redact("user=ann\ncount: 3\n")
        self.assertEqual((code, report["status"], report["redactions"], report["text"]), (0, "clean", 0, "user=ann\ncount: 3\n"))

    def test_the_scrubbed_copy_is_written_whole_and_bad_input_is_refused(self):
        source = pathlib.Path(self.temp.name) / "receipt.txt"
        source.write_bytes(AUTH_TEXT.encode("utf-8"))
        out = pathlib.Path(self.temp.name) / "scrubbed.txt"
        out.write_bytes(b"old contents that must go\n")
        code, report = self.run_cli("redact", str(source), "--out", str(out))
        self.assertEqual((code, report["out"]), (1, str(out)))
        self.assertEqual(out.read_bytes().decode("utf-8"), report["text"])
        self.assertNotIn("hunter2", out.read_bytes().decode("utf-8"))
        self.assertIn("names", report)
        self.assertNotIn("hunter2", json.dumps(report["names"]))
        junk = pathlib.Path(self.temp.name) / "junk.bin"
        junk.write_bytes(b"\xc3\x28 not utf-8")
        self.assertEqual(self.run_cli("redact", str(junk))[0], 2)
        self.assertEqual(self.run_cli("redact", str(pathlib.Path(self.temp.name) / "missing.txt"))[0], 2)
        self.assertEqual(self.run_cli("redact")[0], 64)
        self.assertRegex(report["claim"], r"does not show")


class ReportTests(Fixture):
    """SC-14: the report is generated by code from the validated record; GS-50: partial scope says partial."""

    def test_a_record_with_problems_is_refused_not_rendered(self):
        data = record(confirmed(severity="low"))
        result, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIsNone(markdown)
        _, rendered = broken(off("report_problems")).render(data, "0" * 64, str(self.root))
        self.assertIsNotNone(rendered, "a copy that renders anyway is caught")

    def test_a_hand_edit_disappears_on_regeneration(self):
        source = self.write_record(record(confirmed()))
        out = pathlib.Path(self.temp.name) / "report.md"
        code, report = self.run_cli("report", str(source), "--root", str(self.root), "--out", str(out))
        self.assertEqual((code, report["status"]), (0, "rendered"))
        first = out.read_bytes()
        self.assertEqual(sha(first), report["markdown_sha256"])
        out.write_bytes(first.replace(b"[high]", b"[low]"))
        self.assertEqual(self.run_cli("report", str(source), "--root", str(self.root), "--out", str(out))[0], 0)
        self.assertEqual(out.read_bytes(), first)
        keep = ("def _write_out(path, text):\n", "def _write_out(path, text):\n    if os.path.exists(path):\n        return\n")
        out.write_bytes(first.replace(b"[high]", b"[low]"))
        control = broken(keep)
        _, markdown = control.render(record(confirmed()), "0" * 64, str(self.root))
        control._write_out(str(out), markdown)
        self.assertIn(b"[low]", out.read_bytes(), "the broken copy keeps the hand edit, which the test catches")

    def test_the_report_names_the_record_it_came_from(self):
        source = self.write_record(record(confirmed()))
        _, report = self.run_cli("report", str(source), "--root", str(self.root))
        self.assertIn("record sha256 " + sha(source.read_bytes()), report["markdown"].splitlines()[0])
        self.assertIn("never edit it", report["markdown"].splitlines()[0])

    def test_no_confirmed_findings_never_reads_as_secure(self):
        _, markdown = sa.render(record(), "0" * 64, str(self.root))
        self.assertIn("This does not say the system is secure.", markdown)

    def test_coverage_not_run_makes_the_audit_partial(self):
        data = record(confirmed(), coverage={"status": "not-run"})
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: partial (coverage not-run)", markdown)
        _, control = broken(off('coverage != "complete"')).render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", control)

    def test_a_path_scoped_run_says_partial(self):
        data = record(confirmed(), paths=["app"])
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: partial (path-scoped run: app)", markdown)
        _, control = broken(off("scoped")).render(data, "0" * 64, str(self.root))
        self.assertIn("Audit status: complete", control)

    def test_complete_coverage_names_its_receipt(self):
        data = record(confirmed(), coverage={"status": "complete"})
        self.assertCaught(data, "coverage-unreceipted", off('coverage.get("status") == "complete" and not _text(coverage.get("receipt"))'))

    def test_a_considered_but_excluded_block_needs_its_reason(self):
        data = record(confirmed(), excluded=[{"what": "vendor/", "reason": ""}])
        self.assertCaught(data, "exclusion-unreasoned", off('not _text(item.get("reason"))'))
        data["scope"]["excluded"][0]["reason"] = "third-party code pinned by hash; vetted in intake"
        _, markdown = sa.render(data, "0" * 64, str(self.root))
        self.assertIn("## Considered and excluded (1, counted as unchecked)", markdown)

    def test_rejected_records_are_kept_with_their_reason(self):
        rejected = {"id": "R1", "state": "rejected", "claim": "Open redirect on /login.", "rule": "redirect.login",
                    "anchor": "app/login.py::next_url", "reason": "next_url is matched against a fixed path list"}
        _, markdown = sa.render(record(confirmed(), rejected), "0" * 64, str(self.root))
        self.assertIn("## Rejected (kept) (1)", markdown)
        self.assertIn("next_url is matched against a fixed path list", markdown)
        rejected["reason"] = ""
        self.assertCaught(record(rejected), "rejection-unreasoned", off('state == "rejected" and not _text(rec.get("reason"))'))


class ScopeTests(Fixture):
    """SC-13: the scope receipt covers staged and untracked content, never .git, never remote credentials."""

    def make(self):
        root = pathlib.Path(self.temp.name) / "scoped"
        (root / ".git" / "refs" / "heads").mkdir(parents=True)
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (root / ".git" / "refs" / "heads" / "main").write_text("a" * 40 + "\n", encoding="utf-8")
        (root / ".git" / "config").write_text('[remote "origin"]\n\turl = https://alice:s3cr3t-token@git.example/x.git\n',
                                              encoding="utf-8")
        (root / "a.txt").write_text("tracked\n", encoding="utf-8")
        (root / "b.txt").write_text("untracked\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "dep.js").write_text("x\n", encoding="utf-8")
        return root

    def test_touching_an_untracked_file_changes_the_digest(self):
        root = self.make()
        first = sa.scope(root, tracked={"a.txt"})
        self.assertEqual(first["untracked"], ["b.txt", "node_modules/dep.js"])
        (root / "b.txt").write_text("untracked, changed\n", encoding="utf-8")
        self.assertNotEqual(sa.scope(root, tracked={"a.txt"})["content_sha256"], first["content_sha256"])
        control = broken(("hashed = walked", "hashed = {p: h for p, h in walked.items() if tracked is None or p in tracked}"))
        before = control.scope(root, tracked={"a.txt"})["content_sha256"]
        (root / "b.txt").write_text("untracked, changed again\n", encoding="utf-8")
        self.assertEqual(control.scope(root, tracked={"a.txt"})["content_sha256"], before,
                         "the tracked-only copy misses the untracked change, which the test catches")

    def test_git_metadata_and_remote_credentials_never_enter_the_receipt(self):
        root = self.make()
        report = sa.scope(root)
        self.assertNotIn("s3cr3t", json.dumps(report))
        before = report["content_sha256"]
        (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        self.assertEqual(sa.scope(root)["content_sha256"], before)
        control = broken(('dirs[:] = sorted(d for d in dirs if d != ".git")', "dirs[:] = sorted(dirs)"))
        first = control.scope(root)["content_sha256"]
        (root / ".git" / "config").write_text("[core]\n\tbare = false\n", encoding="utf-8")
        self.assertNotEqual(control.scope(root)["content_sha256"], first)

    def test_the_revision_is_read_from_git_files(self):
        root = self.make()
        self.assertEqual(sa.scope(root)["revision"], "a" * 40)
        (root / ".git" / "HEAD").write_text("ref: refs/heads/../../escape\n", encoding="utf-8")
        self.assertIsNone(sa.scope(root)["revision"])

    def test_excluded_patterns_are_counted_and_left_out(self):
        root = self.make()
        report = sa.scope(root, excludes=("node_modules/*",))
        self.assertEqual(report["excluded"], [{"pattern": "node_modules/*", "files": 1}])
        self.assertEqual(report["files"], 2)

    def test_the_scope_command_takes_saved_ls_files_output(self):
        root = self.make()
        listing = pathlib.Path(self.temp.name) / "tracked.bin"
        listing.write_bytes(b"a.txt\0")
        code, report = self.run_cli("scope", str(root), "--tracked", str(listing), "--exclude", "node_modules/*")
        self.assertEqual((code, report["untracked"], report["untracked_count"]), (0, ["b.txt"], 1))


class CliTests(Fixture):
    def test_exit_codes(self):
        good = self.write_record(record(confirmed()))
        bad = self.write_record(record(confirmed(severity="low")), "bad.json")
        junk = pathlib.Path(self.temp.name) / "junk.json"
        junk.write_text("{not json", encoding="utf-8")
        other = self.write_record({"format": "something-else", "records": []}, "other.json")
        self.assertEqual(self.run_cli("check", str(good), str(self.root))[0], 0)
        code, report = self.run_cli("check", str(bad), str(self.root))
        self.assertEqual((code, report["status"]), (1, "findings"))
        for path in (junk, other):
            self.assertEqual(self.run_cli("check", str(path), str(self.root))[0], 2)
        self.assertEqual(self.run_cli("check", str(good), str(self.root / "missing"))[0], 2)
        self.assertEqual(self.run_cli("report", str(bad))[0], 1)
        self.assertEqual(self.run_cli("scope", str(self.root / "missing"))[0], 2)
        self.assertEqual(self.run_cli("suppressions", str(self.root))[0], 0)
        self.assertEqual(self.run_cli("suppressions", str(self.root / "missing"))[0], 2)
        self.assertEqual(self.run_cli("suppressions")[0], 64)
        self.assertEqual(self.run_cli()[0], 64)
        self.assertEqual(self.run_cli("check", str(good))[0], 64)

    def test_every_report_says_what_passing_does_not_show(self):
        good = self.write_record(record(confirmed()))
        for args in (("check", str(good), str(self.root)), ("report", str(good)), ("scope", str(self.root)),
                     ("suppressions", str(self.root))):
            with self.subTest(mode=args[0]):
                claim = self.run_cli(*args)[1]["claim"]
                self.assertRegex(claim, r"does not show|never says the system is secure|no stronger than")

    def test_a_record_saved_as_utf16_is_read(self):
        path = pathlib.Path(self.temp.name) / "utf16.json"
        path.write_bytes(json.dumps(record(confirmed())).encode("utf-16"))
        self.assertEqual(self.run_cli("check", str(path), str(self.root))[0], 0)

    def test_the_script_runs_nothing_opens_no_network_and_writes_only_the_out_file(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("subprocess", "socket", "urllib", "http.client", "os.system", "Popen", "requests", "shutil"):
            self.assertNotIn(banned, source)
        writes = re.findall(r"open\([^)]*[\"'][wax]b?[\"']|write_text|write_bytes|os\.replace|os\.rename|unlink|rmdir|mkdir",
                            source)
        self.assertEqual(writes, ['open(path, "w"'])


if __name__ == "__main__":
    unittest.main()
