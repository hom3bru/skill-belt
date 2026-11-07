"""Tests for westack-qa's live DX audit: qacheck.py's developer-experience record check and the plan-versus-live
comparison. Local files only.

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

PERSONA = {"who": "a developer adding the tool to one project", "goal": "a first result today",
           "environment": "Windows 11, Python 3.12", "knows": "git and Python"}
SCORES = {"getting-started": 6, "api-cli": 7, "errors": 7, "docs": 6, "upgrade": 4, "environment": 7,
          "community": 2, "measurement": 3}


def plan(**over):
    dims = [{"id": k, "score": v, "evidence": "inferred", "gap": "a 10 does more"} for k, v in SCORES.items()]
    r = {"format": qacheck.DX_FORMAT, "kind": "plan", "product": "example CLI", "persona": dict(PERSONA),
         "tthw": {"minutes": 4, "tier": "competitive", "evidence": "inferred", "steps": ["read", "install", "run"]},
         "dimensions": dims}
    r.update(over)
    r["overall"] = qacheck.dx_overall(r["dimensions"])
    return r


def live(scores=None, steps=None):
    scores = dict(SCORES, **(scores or {}))
    steps = steps or [{"step": "read the install section", "minutes": 1.5, "evidence": "tested", "ref": "README.md:47"},
                      {"step": "dry run", "minutes": 0.5, "evidence": "tested", "ref": "install.py ... exit 0"},
                      {"step": "apply", "minutes": 1, "evidence": "inferred", "ref": "README.md:51 (not run: no grant)"}]
    dims = [{"id": k, "score": v, "evidence": "tested", "gap": "a 10 does more", "refs": ["cmd --help exit 0"]}
            for k, v in scores.items()]
    r = {"format": qacheck.DX_FORMAT, "kind": "live", "product": "example CLI", "persona": dict(PERSONA),
         "tthw": {"minutes": round(sum(s["minutes"] for s in steps), 1), "evidence": qacheck.dx_weakest(
             [s["evidence"] for s in steps]), "steps": steps},
         "dimensions": dims}
    r["tthw"]["tier"] = qacheck.dx_tier(r["tthw"]["minutes"])
    r["overall"] = qacheck.dx_overall(dims)
    return r


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = qacheck.main(list(args))
    return code, out.getvalue()


class RecordTests(unittest.TestCase):
    def test_plan_and_live_samples_are_valid(self):
        self.assertEqual(qacheck.validate(plan()), [])
        self.assertEqual(qacheck.validate(live()), [])

    def test_every_dimension_exactly_once(self):
        r = live()
        r["dimensions"] = [d for d in r["dimensions"] if d["id"] != "errors"]
        r["overall"] = qacheck.dx_overall(r["dimensions"])
        self.assertIn("dimension errors must appear exactly once (found 0)", qacheck.validate(r))

    def test_live_steps_carry_marks_and_add_up(self):
        r = live()
        r["tthw"]["evidence"] = "tested"
        self.assertIn("tthw.evidence is 'tested'; the step marks make it 'partial'", qacheck.validate(r))
        r = live()
        r["tthw"]["minutes"] = 2.5
        r["tthw"]["tier"] = qacheck.dx_tier(2.5)
        self.assertIn("tthw.minutes is 2.5; the steps add up to 3.0", qacheck.validate(r))
        r = live()
        r["tthw"]["steps"][0]["evidence"] = "measured"
        self.assertIn("tthw step 1: evidence must be one of tested, partial, inferred", qacheck.validate(r))
        r = live()
        r["tthw"]["steps"] = ["read", "run"]
        self.assertIn("tthw step 1: a live step is an object with step, minutes, evidence and ref", qacheck.validate(r))

    def test_a_live_score_needs_refs_and_a_plan_runs_nothing(self):
        r = live()
        r["dimensions"][3]["refs"] = []
        self.assertIn("dimension docs: a live score needs refs (a command and its exit code, a screenshot hash or "
                      "a file:line)", qacheck.validate(r))
        p = plan()
        p["dimensions"][0]["evidence"] = "tested"
        self.assertIn("a plan review ran nothing: every mark is inferred", qacheck.validate(p))

    def test_weakest_mark(self):
        self.assertEqual(qacheck.dx_weakest(["tested", "tested"]), "tested")
        self.assertEqual(qacheck.dx_weakest(["inferred", "inferred"]), "inferred")
        self.assertEqual(qacheck.dx_weakest(["tested", "inferred"]), "partial")
        self.assertEqual(qacheck.dx_weakest(["partial"]), "partial")
        self.assertIsNone(qacheck.dx_weakest([]))


class CompareTests(unittest.TestCase):
    def test_a_drop_of_two_is_tolerated_three_alerts(self):
        code, result = qacheck.dx_compare(plan(), live({"docs": 4}))
        self.assertEqual((code, result["status"], result["alerts"]), (0, "as-planned", []))
        code, result = qacheck.dx_compare(plan(), live({"docs": 3}))
        self.assertEqual((code, result["status"], result["alerts"]), (1, "fell-short", ["docs"]))
        row = next(r for r in result["dimensions"] if r["id"] == "docs")
        self.assertEqual((row["plan"], row["live"], row["delta"], row["alert"]), (6, 3, -3, True))

    def test_a_worse_hello_world_tier_alerts(self):
        slow = [{"step": "read", "minutes": 4, "evidence": "tested", "ref": "README.md:47"},
                {"step": "install", "minutes": 3, "evidence": "tested", "ref": "exit 0"}]
        code, result = qacheck.dx_compare(plan(), live(steps=slow))
        self.assertEqual(code, 1)
        self.assertEqual(result["alerts"], ["tthw"])
        self.assertEqual((result["tthw"]["plan_tier"], result["tthw"]["live_tier"], result["tthw"]["delta"]),
                         ("competitive", "needs-work", 3))

    def test_unlike_records_are_refused(self):
        other = live()
        other["product"] = "another CLI"
        code, result = qacheck.dx_compare(plan(), other)
        self.assertEqual((code, result["status"]), (2, "refused"))
        code, result = qacheck.dx_compare(live(), plan())
        self.assertEqual(code, 2)
        bad = live()
        bad["overall"] = 9.9
        code, result = qacheck.dx_compare(plan(), bad)
        self.assertEqual((code, result["status"]), (1, "invalid"))

    def test_the_threshold_lives_in_thresholds_json(self):
        self.assertEqual(qacheck.thresholds()["dx"]["alert_drop"], 2)

    def test_the_control_a_threshold_raised_past_any_drop_misses_the_fall(self):
        t = copy.deepcopy(qacheck.thresholds())
        t["dx"]["alert_drop"] = 99
        code, result = qacheck.dx_compare(plan(), live({"docs": 0, "errors": 0}), t)
        self.assertEqual((code, result["alerts"]), (0, []), "the broken threshold misses what the real one finds")
        code, result = qacheck.dx_compare(plan(), live({"docs": 0, "errors": 0}))
        self.assertEqual(result["alerts"], ["errors", "docs"])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, l = Path(tmp, "plan.json"), Path(tmp, "live.json")
            p.write_text(json.dumps(plan()), encoding="utf-8")
            l.write_text(json.dumps(live({"api-cli": 3})), encoding="utf-8")
            self.assertEqual(run("validate", str(l))[0], 0)
            code, out = run("dx", str(p), str(l))
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["alerts"], ["api-cli"])
            self.assertEqual(run("dx", str(p))[0], 64)


if __name__ == "__main__":
    unittest.main()
