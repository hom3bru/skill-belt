"""Tests for westack-review's scripts/dxcheck.py (the developer-experience record). Local files only.

Run from the repo root:  python -B -m unittest discover -s skills/westack-review/tests
"""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "dxcheck.py"
FIXTURE = json.loads((HERE.parent / "evals" / "fixtures" / "dx-plan.json").read_text(encoding="utf-8"))


def load(path=SCRIPT, name="westack_dxcheck_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dx = load()


class RecordTests(unittest.TestCase):
    def test_the_fixture_plan_record_is_valid(self):
        self.assertEqual(dx.check(FIXTURE), [])

    def test_every_dimension_exactly_once(self):
        r = copy.deepcopy(FIXTURE)
        r["dimensions"] = [d for d in r["dimensions"] if d["id"] != "errors"]
        r["overall"] = dx.overall(r["dimensions"])
        self.assertIn("dimension errors must appear exactly once (found 0)", dx.check(r))

    def test_a_plan_cannot_claim_tested(self):
        r = copy.deepcopy(FIXTURE)
        r["dimensions"][0]["evidence"] = "tested"
        self.assertIn("a plan review ran nothing: every mark is inferred", dx.check(r))
        r["kind"] = "live"
        self.assertEqual(dx.check(r), [])

    def test_tiers_scores_gaps_persona_overall(self):
        self.assertEqual([dx.tier_for(m) for m in (1.9, 2, 5, 5.5, 10, 11)],
                         ["champion", "competitive", "competitive", "needs-work", "needs-work", "red-flag"])
        r = copy.deepcopy(FIXTURE)
        r["tthw"]["tier"] = "champion"
        r["dimensions"][1]["score"] = 11
        r["dimensions"][2]["gap"] = ""
        r["persona"]["who"] = ""
        errors = " | ".join(dx.check(r))
        for phrase in ("4 minutes is 'competitive'", "whole number from 0 to 10", "what a 10 looks like",
                       "persona.who", "overall is 5.2"):
            self.assertIn(phrase, errors)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp, "dx.json")
            good.write_text(json.dumps(FIXTURE), encoding="utf-8")
            self.assertEqual(dx.main(["record", str(good)]), 0)
            self.assertEqual(dx.main(["record", str(Path(tmp, "none.json"))]), 64)

    def test_the_control_a_copy_without_the_dimension_check_misses_a_dropped_dimension(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "        if ids.count(d) != 1:"
        self.assertEqual(source.count(old), 1)
        with tempfile.TemporaryDirectory() as tmp:
            broken_path = Path(tmp, "dxcheck_broken.py")
            broken_path.write_text(source.replace(old, "        if False:"), encoding="utf-8")
            broken = load(broken_path, "westack_dxcheck_broken")
            r = copy.deepcopy(FIXTURE)
            r["dimensions"] = [d for d in r["dimensions"] if d["id"] != "errors"]
            r["overall"] = broken.overall(r["dimensions"])
            self.assertEqual(broken.check(r), [], "the broken copy misses what the real check finds")
            self.assertNotEqual(dx.check(r), [])


if __name__ == "__main__":
    unittest.main()
