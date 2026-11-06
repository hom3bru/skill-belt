"""Tests for westack-qa's scripts/qacheck.py (score, validate, diff, compare, expect). Local files only.

Run from the repo root:  python -B -m unittest discover -s skills/westack-qa/tests
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import qacheck  # noqa: E402

ALL = ["console", "links", "visual", "functional", "ux", "performance", "content", "accessibility"]
ENV = {"os": "Windows 11", "browser": "Chromium 140", "headless": False, "viewport": "1280x800", "device_pixel_ratio": 1}


def report(**over):
    r = {
        "format": qacheck.REPORT_FORMAT, "mode": "full", "target": "http://127.0.0.1:8765/", "grant": "local fixture",
        "driver": "host browser pane", "environment": dict(ENV), "pages": [{"url": "/", "status": 200}],
        "tested": list(ALL),
        "console_errors": [{"message": "ReferenceError: a", "source": "/app.js", "page": "/"},
                           {"message": "TypeError: b", "source": "/app.js", "page": "/about"}],
        "links": {"checked": 5, "broken": [{"url": "/missing", "status": 404, "page": "/"}]},
        "issues": [
            {"id": "QA-1", "title": "Save button does nothing", "severity": "high", "category": "functional", "page": "/",
             "evidence": ["snapshot diff: no change after click"]},
            {"id": "QA-2", "title": "Image without alt text", "severity": "medium", "category": "accessibility",
             "page": "/about", "evidence": ["img[src='team.png'] has no alt"]},
        ],
        "runtime": [{"id": "browser", "status": "passed"}],
    }
    r.update(over)
    r.setdefault("score", qacheck.compute_score(r))
    if "score" not in over:
        r["score"] = qacheck.compute_score(r)
    return r


class ScoreTests(unittest.TestCase):
    def test_the_worked_example(self):
        # console 2 errors -> 70, links 1 broken -> 85, functional high -> 85, accessibility medium -> 92, rest 100:
        # (70*15 + 85*10 + 100*10 + 85*20 + 100*15 + 100*10 + 100*5 + 92*15) / 100 = 89.8 -> 90
        s = qacheck.compute_score(report())
        self.assertEqual(s["categories"], {"console": 70, "links": 85, "visual": 100, "functional": 85, "ux": 100,
                                           "performance": 100, "content": 100, "accessibility": 92})
        self.assertEqual((s["status"], s["value"], s["provisional"]), ("scored", 90, False))

    def test_untested_categories_are_left_out_and_the_score_is_provisional(self):
        s = qacheck.compute_score(report(tested=["console", "links"], console_errors=[],
                                         links={"checked": 4, "broken": [{"url": "/a"}, {"url": "/b"}]}, issues=[]))
        self.assertEqual((s["value"], s["provisional"], s["categories"]), (88, True, {"console": 100, "links": 70}))

    def test_nothing_tested_is_not_scored(self):
        s = qacheck.compute_score(report(tested=[]))
        self.assertEqual((s["status"], s["value"]), ("not scored", None))

    def test_half_rounds_up(self):
        s = qacheck.compute_score(report(tested=["visual", "links"], issues=[]))
        self.assertEqual(s["value"], 93, "92.5 rounds up; Python's round() would give 92")

    def test_console_buckets_at_their_edges(self):
        t = qacheck.thresholds()
        self.assertEqual([qacheck.console_score(n, t) for n in (0, 1, 3, 4, 10, 11, 50)], [100, 70, 70, 40, 40, 10, 10])

    def test_floors_at_zero(self):
        crit = [{"id": f"C{i}", "title": "crash", "severity": "critical", "category": "functional", "page": "/",
                 "evidence": ["x"]} for i in range(5)]
        s = qacheck.compute_score(report(issues=crit, links={"checked": 9, "broken": [{"url": f"/{i}"} for i in range(7)]}))
        self.assertEqual((s["categories"]["functional"], s["categories"]["links"]), (0, 0))

    def test_an_unconfirmed_issue_is_listed_but_not_scored(self):
        issues = report()["issues"] + [{"id": "QA-3", "title": "Flicker once", "severity": "critical", "category": "visual",
                                        "page": "/", "evidence": ["seen once"], "confirmed": False}]
        self.assertEqual(qacheck.compute_score(report(issues=issues))["categories"]["visual"], 100)

    def test_console_and_link_issues_do_not_deduct_twice(self):
        issues = report()["issues"] + [{"id": "QA-4", "title": "Broken link to /missing", "severity": "high",
                                        "category": "links", "page": "/", "evidence": ["HEAD /missing 404"]}]
        self.assertEqual(qacheck.compute_score(report(issues=issues))["categories"]["links"], 85)


class ValidateTests(unittest.TestCase):
    def test_a_good_report_is_valid(self):
        self.assertEqual(qacheck.validate(report()), [])

    def test_a_score_that_disagrees_with_the_rubric_is_refused(self):
        r = report()
        r["score"] = dict(r["score"], value=95)
        self.assertTrue(any("score.value" in e for e in qacheck.validate(r)))

    def test_a_degraded_report_has_no_score_and_runs_nothing(self):
        r = report(driver=None, degraded=True, tested=[], issues=[], console_errors=[], environment={},
                   links={"checked": 0, "broken": []}, runtime=[{"id": "browser", "status": "not-run", "why": "no browser tool answered"}])
        self.assertEqual(qacheck.validate(r), [])
        self.assertEqual(r["score"]["status"], "not scored")

    def test_no_driver_with_results_is_refused(self):
        r = report(driver=None, degraded=True)
        errors = " | ".join(qacheck.validate(r))
        self.assertIn("every runtime check is not-run", errors)
        self.assertIn("nothing was tested", errors)

    def test_shape_errors_are_named(self):
        r = report()
        r["issues"].append(dict(r["issues"][0]))
        r["issues"].append({"id": "QA-9", "title": "x", "severity": "fatal", "category": "visual", "page": "/", "evidence": []})
        r["console_errors"].append(dict(r["console_errors"][0]))
        r["score"] = qacheck.compute_score(r)
        errors = " | ".join(qacheck.validate(r))
        for phrase in ("QA-1 is repeated", "QA-9: severity", "QA-9: evidence", "deduplicated"):
            self.assertIn(phrase, errors)

    def test_an_issue_in_an_untested_category_is_refused(self):
        r = report(tested=["console", "links", "functional"])
        self.assertTrue(any("not among the tested" in e for e in qacheck.validate(r)))

    def test_a_regression_report_names_its_baseline(self):
        self.assertTrue(any("baseline" in e for e in qacheck.validate(report(mode="regression"))))


class CompareDiffExpectTests(unittest.TestCase):
    def test_compare_lists_fixed_new_and_the_delta(self):
        base = report()
        cur_issues = [base["issues"][1], {"id": "QA-7", "title": "Menu overlaps logo", "severity": "low",
                                          "category": "visual", "page": "/", "evidence": ["screenshot sha256 ..."]}]
        cur = report(issues=cur_issues)
        code, result = qacheck.compare(base, cur)
        self.assertEqual(code, qacheck.EXIT_OK)
        self.assertEqual((result["fixed"], result["new"]), (["QA-1"], ["QA-7"]))
        self.assertEqual(result["score_delta"], cur["score"]["value"] - base["score"]["value"])

    def test_compare_refuses_different_coverage_or_environment(self):
        code, result = qacheck.compare(report(), report(tested=["console", "links"], issues=[]))
        self.assertEqual((code, result["status"]), (qacheck.EXIT_UNSURE, "refused"))
        env = dict(ENV, device_pixel_ratio=2)
        self.assertEqual(qacheck.compare(report(), report(environment=env))[0], qacheck.EXIT_UNSURE)

    def test_snapshot_diff_shows_the_change(self):
        out = qacheck.snapshot_diff("- button \"Save\"\n- text \"Draft\"\n", "- button \"Save\"\n- text \"Saved\"\n")
        self.assertIn('-- text "Draft"', out)
        self.assertIn('+- text "Saved"', out)
        self.assertEqual(qacheck.snapshot_diff("a\n", "a\n"), "")

    def test_expect_finds_planted_defects_and_names_a_missing_one(self):
        wanted = {"defects": [{"id": "d1", "category": "functional", "page": "/", "match": ["save button"]},
                              {"id": "d2", "category": "accessibility", "page": "/about", "match": ["alt"]}]}
        self.assertEqual(qacheck.expect(report(), wanted), [])
        wanted["defects"].append({"id": "d3", "category": "content", "page": "/", "match": ["lorem"]})
        problems = qacheck.expect(report(), wanted)
        self.assertEqual(len(problems), 1)
        self.assertIn("d3", problems[0])

    def test_expect_refuses_a_report_with_no_driver(self):
        r = report(driver=None, degraded=True, tested=[], issues=[], console_errors=[], environment={},
                   links={"checked": 0, "broken": []}, runtime=[{"id": "browser", "status": "not-run", "why": "none"}])
        self.assertTrue(any("no driver" in p for p in qacheck.expect(r, {"defects": []})))


def fix(n, status="verified", files=("app.js",), **over):
    f = {"issue": {"id": f"QA-{n}", "title": f"issue {n}", "category": "functional", "page": "/"}, "status": status,
         "files": list(files), "recheck": ["probe passed"], "test": f"tests/test_{n}.py"}
    if status in ("best-effort", "deferred"):
        f["why"] = "needs a signed-in session"
    f.update(over)
    return f


def looped(fixes, issues=None, **loop_over):
    loop = {"edit_grant": "src/ only", "fixes": fixes}
    loop.update(loop_over)
    return report(issues=report()["issues"] if issues is None else issues, fix_loop=loop)


class FixLoopTests(unittest.TestCase):
    def decide(self, *fixes, issues=None):
        return qacheck.loop_decision(looped(list(fixes), issues))

    def test_a_short_clean_loop_continues(self):
        self.assertEqual(self.decide(fix(1), fix(2))["decision"], "continue")

    def test_two_reverts_stop(self):
        d = self.decide(fix(1, "reverted"), fix(2), fix(3, "reverted"))
        self.assertEqual(d["decision"], "stop")
        self.assertIn("2 reverts", d["stop"])

    def test_one_revert_asks(self):
        self.assertEqual(self.decide(fix(1), fix(2, "reverted"))["decision"], "ask")

    def test_an_unrelated_file_stops(self):
        d = self.decide(fix(1, unrelated_files=["README.md"]))
        self.assertEqual(d["decision"], "stop")

    def test_every_fifth_fix_asks_and_test_only_commits_do_not_count(self):
        five = [fix(n) for n in range(1, 6)]
        self.assertEqual(self.decide(*five)["decision"], "ask")
        four_and_tests = [fix(n) for n in range(1, 5)] + [fix(9, test_only=True)]
        self.assertEqual(self.decide(*four_and_tests)["decision"], "continue")

    def test_two_wide_fixes_in_a_row_stop(self):
        wide = [f"f{i}.js" for i in range(6)]
        self.assertEqual(self.decide(fix(1, files=wide), fix(2, files=wide))["decision"], "stop")
        self.assertEqual(self.decide(fix(1, files=wide), fix(2), fix(3, files=wide))["decision"], "continue")

    def test_only_low_issues_left_stops(self):
        low = [{"id": "QA-8", "title": "typo", "severity": "low", "category": "content", "page": "/", "evidence": ["x"]}]
        self.assertIn("only low issues remain", self.decide(fix(1), issues=low)["stop"])

    def test_the_hard_cap_stops(self):
        d = self.decide(*[fix(n) for n in range(1, 51)])
        self.assertIn("the hard cap of 50 fixes", d["stop"])

    def test_fix_records_are_validated(self):
        bad = [fix(1, recheck=[]), fix(2, "best-effort", why=""), fix(3, status="done"), fix(4, test=None),
               fix(5, commit="abc123")]
        errors = " | ".join(qacheck.validate(looped(bad, edit_grant="")))
        for phrase in ("edit_grant", "re-check evidence", "best-effort says why", "status must be one of",
                       "test_missing", "commit without commit_grant"):
            self.assertIn(phrase, errors)
        self.assertEqual(qacheck.validate(looped([fix(1), fix(2, test=None, test_missing="no runner in this project")])), [])

    def test_expect_fixed_needs_a_verified_fix_and_the_issue_gone(self):
        wanted = {"fixed": [{"id": "d1", "category": "functional", "page": "/", "match": ["save button"]}]}
        save = report()["issues"][0]
        remaining = [report()["issues"][1]]
        good = looped([{**fix(1), "issue": save}], issues=remaining)
        self.assertEqual(qacheck.expect(good, wanted), [])
        still_there = looped([{**fix(1), "issue": save}])
        self.assertTrue(any("still appears" in p for p in qacheck.expect(still_there, wanted)))
        best_effort = looped([{**fix(1, "best-effort"), "issue": save}], issues=remaining)
        self.assertTrue(any("no verified fix" in p for p in qacheck.expect(best_effort, wanted)))


BASE = {"pages": [{"url": "/", "console_errors": ["old error"], "broken": ["/gone"], "load_ms": 400}]}


def check(**page):
    p = {"url": "/", "loaded": True, "console_errors": ["old error"], "broken": ["/gone"], "load_ms": 420}
    p.update(page)
    return {"pages": [p]}


class MonitorTests(unittest.TestCase):
    def run_checks(self, *checks):
        return qacheck.monitor(BASE, {"checks": list(checks)})

    def test_baseline_problems_are_not_alerts(self):
        r = self.run_checks(check(), check(), check())
        self.assertEqual((r["status"], r["alerts"], r["observations"]), ("healthy", [], []))

    def test_a_new_error_alerts_only_on_the_second_consecutive_check(self):
        new = check(console_errors=["old error", "TypeError: boom"])
        r = self.run_checks(check(), new, new)
        self.assertEqual(len(r["alerts"]), 1)
        a = r["alerts"][0]
        self.assertEqual((a["severity"], a["first_seen"], a["confirmed_at"]), ("high", 2, 3))
        self.assertIn("TypeError: boom", a["message"])
        self.assertEqual(r["status"], "degraded")

    def test_a_one_check_blip_is_an_observation(self):
        r = self.run_checks(check(), check(console_errors=["old error", "blip"]), check())
        self.assertEqual(r["alerts"], [])
        self.assertEqual(r["observations"][0]["kind"], "transient")
        self.assertEqual(self.run_checks(check(), check(console_errors=["x"]))["observations"][0]["kind"], "pending")

    def test_severities(self):
        down = check(loaded=False)
        self.assertEqual(self.run_checks(down, down)["alerts"][0]["severity"], "critical")
        self.assertEqual(self.run_checks(down, down)["status"], "broken")
        slow = check(load_ms=801)
        self.assertEqual(self.run_checks(slow, slow)["alerts"][0]["severity"], "medium")
        self.assertEqual(self.run_checks(check(load_ms=800), check(load_ms=800))["alerts"], [], "exactly 2x is not over")
        link = check(broken=["/gone", "/pricing"])
        self.assertEqual(self.run_checks(link, link)["alerts"][0]["severity"], "low")

    def test_a_resolved_incident_keeps_its_alert(self):
        new = check(console_errors=["old error", "boom"])
        r = self.run_checks(new, new, check())
        self.assertEqual((r["alerts"][0]["resolved_at"], r["status"]), (3, "degraded"))

    def test_expect_on_a_monitor_result(self):
        new = check(console_errors=["old error", "monitorBreak is not defined"])
        r = self.run_checks(check(), new, new)
        wanted = {"alerts": [{"severity": "high", "page": "/", "match": ["monitorBreak"], "confirmed_at": 3}],
                  "no_alert_before": 3, "status": "degraded"}
        self.assertEqual(qacheck.expect(r, wanted), [])
        wanted["alerts"][0]["confirmed_at"] = 2
        self.assertTrue(qacheck.expect(r, wanted))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = qacheck.main(list(args))
        return code, out.getvalue()

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad, base = Path(tmp, "good.json"), Path(tmp, "bad.json"), Path(tmp, "base.json")
            good.write_text(json.dumps(report()), encoding="utf-8")
            broken = report()
            broken["score"] = dict(broken["score"], value=1)
            bad.write_text(json.dumps(broken), encoding="utf-8")
            base.write_text(json.dumps(report(tested=["console"], issues=[])), encoding="utf-8")
            self.assertEqual(self.run_cli("validate", str(good))[0], 0)
            self.assertEqual(self.run_cli("validate", str(bad))[0], 1)
            self.assertEqual(self.run_cli("compare", str(base), str(good))[0], 2)
            self.assertEqual(self.run_cli("score", str(good))[0], 0)
            self.assertEqual(self.run_cli("nonsense")[0], 64)
            self.assertEqual(self.run_cli("validate", str(Path(tmp, "absent.json")))[0], 64)

    def test_the_fixture_expectations_are_well_formed(self):
        wanted = json.loads((HERE.parent / "evals" / "fixtures" / "planted-defects.json").read_text(encoding="utf-8"))
        site = HERE.parent / "evals" / "fixtures" / "site"
        self.assertGreaterEqual(len(wanted["defects"]), 3)
        for d in wanted["defects"]:
            with self.subTest(defect=d["id"]):
                self.assertTrue((site / d["page"].lstrip("/")).is_file(), "the page that plants it exists")
                self.assertIn(d["category"], qacheck.thresholds()["weights"])
                self.assertTrue(d["match"])


if __name__ == "__main__":
    unittest.main()
