"""SS-06: reviewer output is checked against a small typed schema by `diffscope.py findings`.

The rules under test, in the order the schema states them:
  - P0 and P1 need a demonstrated trigger (the trigger and the evidence for it);
  - each record state allows only its own fields, and a candidate has no severity before it is confirmed;
  - the overall verdict is blocking, none-found or not-assessed, never an approval, and none-found is not allowed
    while any candidate is unconfirmed or not validated (and it names the scope assessed);
  - malformed output fails the review (exit 1, or exit 2 when it cannot be read at all), the raw bytes are bound by
    their SHA-256 so the raw text can be kept, and the checker never approves.

Run: python -B -m unittest discover -s skills/westack-review/tests -v
The script under test is loaded by path; WESTACK_REVIEW_DIFFSCOPE may point at another copy. Each rule also runs
against a deliberately broken copy of the script (made here by editing one line of its source) and must be missed
there, which shows the test can see the rule.
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
    key = "westack_review_findings_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


CONFIRMED_P1 = {"id": "F1", "state": "confirmed", "claim": "Reject empty page size", "file": "src/pager.py",
                "line": 15, "introduced": "patch", "severity": "P1",
                "consequence": "page_slice drops the last item for every caller",
                "trigger": "page_slice(range(5), 1, 5)", "evidence": "receipt r3: returned 4 items, expected 5",
                "fix": "use items[start:end]"}
CONFIRMED_P3 = {"id": "F2", "state": "confirmed", "claim": "Stale docstring", "file": "src/pager.py", "line": 9,
                "severity": "P3", "consequence": "the docstring names a removed argument"}
CANDIDATE = {"id": "F3", "state": "needs-validation", "claim": "Page size is not clamped for negatives",
             "file": "src/pager.py", "line": 12, "trigger": "page_slice(items, 1, -1)"}
DROPPED = {"id": "F4", "state": "dropped", "claim": "Name could be shorter", "stage": "exclusion 8",
           "reason": "taste", "evidence": "no project rule quoted"}
UNVALIDATED = {"id": "F5", "state": "not-validated", "claim": "Race in the cache", "file": "src/cache.py",
               "line": 40, "reason": "the validator timed out"}
GOOD = [CONFIRMED_P1, CONFIRMED_P3, CANDIDATE, DROPPED, UNVALIDATED]


def problems(report):
    return [(e.get("id"), e.get("field")) for e in report["errors"]]


class FindingsSchema(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def check(self, data):
        return self.m.check_findings(data)

    def test_a_well_formed_file_is_valid_and_counted_by_state(self):
        report = self.check({"verdict": "blocking", "findings": GOOD})
        self.assertEqual(report["status"], "valid", report["errors"])
        self.assertEqual(report["counts"], {"confirmed": 2, "needs-validation": 1, "dropped": 1, "not-validated": 1})
        self.assertEqual(report["errors"], [])

    def test_a_bare_list_is_accepted_without_a_verdict(self):
        self.assertEqual(self.check(GOOD)["status"], "valid")

    def test_severity_on_a_candidate_is_refused_and_named(self):
        bad = dict(CANDIDATE, severity="P1")
        report = self.check([bad])
        self.assertEqual(report["status"], "invalid")
        self.assertIn(("F3", "severity"), problems(report))

    def test_every_field_that_needs_confirmation_is_refused_on_a_candidate_and_on_a_drop(self):
        for field, value in (("fix", "x"), ("rationale", "x"), ("validation", "survived"), ("adjudication", "open")):
            with self.subTest(field=field):
                self.assertIn(("F3", field), problems(self.check([dict(CANDIDATE, **{field: value})])))
        self.assertIn(("F4", "severity"), problems(self.check([dict(DROPPED, severity="P2")])))
        self.assertIn(("F5", "severity"), problems(self.check([dict(UNVALIDATED, severity="P2")])))

    def test_p0_and_p1_need_a_trigger_and_the_evidence_for_it(self):
        for level in ("P0", "P1"):
            for missing in ("trigger", "evidence"):
                with self.subTest(level=level, missing=missing):
                    rec = {k: v for k, v in dict(CONFIRMED_P1, severity=level).items() if k != missing}
                    report = self.check([rec])
                    self.assertEqual(report["status"], "invalid")
                    self.assertIn(("F1", missing), problems(report))
        blank = dict(CONFIRMED_P1, trigger="   ")
        self.assertIn(("F1", "trigger"), problems(self.check([blank])))

    def test_p2_and_p3_do_not_need_a_trigger(self):
        self.assertEqual(self.check([CONFIRMED_P3])["status"], "valid")
        self.assertEqual(self.check([dict(CONFIRMED_P3, severity="P2")])["status"], "valid")

    def test_a_confirmed_finding_needs_severity_location_and_consequence(self):
        for missing in ("severity", "consequence", "claim", "id"):
            with self.subTest(missing=missing):
                rec = {k: v for k, v in CONFIRMED_P3.items() if k != missing}
                self.assertEqual(self.check([rec])["status"], "invalid")
        noloc = {k: v for k, v in CONFIRMED_P3.items() if k not in ("file", "line")}
        self.assertIn(("F2", "location"), problems(self.check([noloc])))
        self.assertEqual(self.check([dict(noloc, heading="3. Rollout")])["status"], "valid")

    def test_unknown_state_severity_level_field_and_enum_values_are_refused(self):
        self.assertIn(("F1", "state"), problems(self.check([dict(CONFIRMED_P1, state="approved")])))
        self.assertIn(("F1", "severity"), problems(self.check([dict(CONFIRMED_P1, severity="P4")])))
        self.assertIn(("F1", "introduced"), problems(self.check([dict(CONFIRMED_P1, introduced="somewhere")])))
        self.assertIn(("F1", "confidence"), problems(self.check([dict(CONFIRMED_P1, confidence=0.9)])))
        self.assertIn(("F1", "line"), problems(self.check([dict(CONFIRMED_P1, line=0)])))

    def test_duplicate_ids_and_non_object_records_are_refused(self):
        self.assertEqual(self.check([CONFIRMED_P3, dict(CONFIRMED_P3)])["status"], "invalid")
        self.assertEqual(self.check(["F1: looks wrong"])["status"], "invalid")
        self.assertEqual(self.check({"findings": "none"})["status"], "invalid")
        self.assertEqual(self.check(42)["status"], "invalid")

    def test_the_verdict_is_blocking_none_found_or_not_assessed_and_never_an_approval(self):
        for word in ("approve", "approved", "lgtm", "pass", "clean"):
            with self.subTest(word=word):
                report = self.check({"verdict": word, "findings": [CONFIRMED_P3]})
                self.assertEqual(report["status"], "invalid")
                self.assertIn((None, "verdict"), problems(report))
        for word, findings in {"blocking": [CONFIRMED_P1], "none-found": [], "not-assessed": [UNVALIDATED]}.items():
            report = self.check({"verdict": word, "scope": "x", "findings": findings})
            self.assertEqual(report["status"], "valid", (word, report["errors"]))

    def test_blocking_needs_a_confirmed_p0_or_p1(self):
        report = self.check({"verdict": "blocking", "findings": [CONFIRMED_P3]})
        self.assertIn((None, "verdict"), problems(report))
        self.assertEqual(self.check({"verdict": "blocking", "findings": [CONFIRMED_P1]})["status"], "valid")

    def test_none_found_needs_the_scope_and_no_open_candidate(self):
        ok = self.check({"verdict": "none-found", "scope": "src/pager.py, 1 file", "findings": [DROPPED]})
        self.assertEqual(ok["status"], "valid", ok["errors"])
        self.assertIn((None, "scope"), problems(self.check({"verdict": "none-found", "findings": []})))
        for open_record in (CANDIDATE, UNVALIDATED, CONFIRMED_P3):
            with self.subTest(state=open_record["state"]):
                report = self.check({"verdict": "none-found", "scope": "src", "findings": [open_record]})
                self.assertIn((None, "verdict"), problems(report))

    def test_the_report_never_says_approved(self):
        text = json.dumps(self.check({"verdict": "none-found", "scope": "src", "findings": [DROPPED]})).lower()
        self.assertNotIn("approved", text)
        self.assertIn("not an approval", text)


class FindingsCli(unittest.TestCase):
    def run_cli(self, path):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), "findings", str(path)],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_exit_codes_and_the_raw_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            good = tmp / "good.json"
            good.write_text(json.dumps({"verdict": "blocking", "findings": GOOD}), encoding="utf-8")
            bad = tmp / "bad.json"
            bad.write_text(json.dumps([dict(CANDIDATE, severity="P1")]), encoding="utf-8")
            raw = tmp / "raw.txt"
            raw.write_bytes(b"The reviewer said: looks fine to me.\n")
            ok = self.run_cli(good)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertEqual(json.loads(ok.stdout)["status"], "valid")
            self.assertEqual(json.loads(ok.stdout)["raw_sha256"], hashlib.sha256(good.read_bytes()).hexdigest())
            refused = self.run_cli(bad)
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(json.loads(refused.stdout)["errors"][0]["field"], "severity")
            unreadable = self.run_cli(raw)
            self.assertEqual(unreadable.returncode, 2)
            body = json.loads(unreadable.stdout)
            self.assertEqual((body["status"], body["raw_sha256"]), ("unreadable", hashlib.sha256(raw.read_bytes()).hexdigest()))
            self.assertEqual(self.run_cli(tmp / "missing.json").returncode, 2)


class BrokenCopies(unittest.TestCase):
    """Each copy has one rule edited out of the script's source and must accept the input the rule exists to refuse."""

    def broken(self, tmp, pattern, replacement):
        source = SCRIPT.read_text(encoding="utf-8")
        edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
        self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
        self.assertNotEqual(edited, source)
        target = pathlib.Path(tmp) / "diffscope_broken.py"
        target.write_text(edited, encoding="utf-8")
        return load(target)

    def test_without_the_unconfirmed_field_rule_a_candidate_with_severity_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^UNCONFIRMED_FORBIDDEN = .*$", "UNCONFIRMED_FORBIDDEN = ()")
            self.assertEqual(broken.check_findings([dict(CANDIDATE, severity="P1")])["status"], "valid")
        self.assertEqual(load().check_findings([dict(CANDIDATE, severity="P1")])["status"], "invalid")

    def test_without_the_trigger_rule_a_p1_with_no_trigger_passes(self):
        bare = {k: v for k, v in CONFIRMED_P1.items() if k not in ("trigger", "evidence")}
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^TRIGGER_REQUIRED = .*$", "TRIGGER_REQUIRED = ()")
            self.assertEqual(broken.check_findings([bare])["status"], "valid")
        self.assertEqual(load().check_findings([bare])["status"], "invalid")

    def test_with_approve_in_the_verdict_list_an_approval_passes(self):
        data = {"verdict": "approve", "findings": [CONFIRMED_P3]}
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^VERDICTS = .*$", 'VERDICTS = ("blocking", "none-found", "not-assessed", "approve")')
            self.assertNotIn((None, "verdict"), problems(broken.check_findings(data)))
        self.assertIn((None, "verdict"), problems(load().check_findings(data)))

    def test_without_the_all_clear_rule_none_found_passes_over_an_unvalidated_candidate(self):
        data = {"verdict": "none-found", "scope": "src", "findings": [UNVALIDATED]}
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, r"^NO_ALL_CLEAR_WITH = .*$", "NO_ALL_CLEAR_WITH = ()")
            self.assertNotIn((None, "verdict"), problems(broken.check_findings(data)))
        self.assertIn((None, "verdict"), problems(load().check_findings(data)))


if __name__ == "__main__":
    unittest.main()
