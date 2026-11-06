"""westack-design's package limits and evaluation data: page sizes, the description, the routing cases the build
must cover, and the files each case expects a run to open (DG-32)."""
import json
import pathlib
import re
import unittest

SKILL = pathlib.Path(__file__).resolve().parent.parent
SKILL_WORDS, REFERENCE_WORDS, DESCRIPTION_CHARS = 1200, 900, 450


def words(path):
    return len(path.read_text(encoding="utf-8").split())


def over(count, cap):
    return count > cap


class SizeTests(unittest.TestCase):
    def test_skill_md_and_each_prose_reference_stay_under_their_caps(self):
        self.assertFalse(over(words(SKILL / "SKILL.md"), SKILL_WORDS), words(SKILL / "SKILL.md"))
        for path in sorted((SKILL / "references").glob("*.md")):
            with self.subTest(page=path.name):
                self.assertFalse(over(words(path), REFERENCE_WORDS), words(path))
        self.assertTrue(over(words(SKILL / "SKILL.md") + SKILL_WORDS, SKILL_WORDS), "the control: a padded page fails")

    def test_the_description_fits_and_names_the_three_siblings_it_is_not_for(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        description = re.search(r'^description: "(.*)"$', text, re.M).group(1)
        self.assertLessEqual(len(description), DESCRIPTION_CHARS)
        for sibling in ("westack-review", "westack-build", "westack-verify"):
            self.assertRegex(description, r"(?i)\bnot\b[^.]*" + sibling)
        self.assertNotRegex(description, r"(?i)\b(?:gstack|impeccable|hallmark|frontend-design)\b")


class EvalDataTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((SKILL / "evals" / "trigger-cases.json").read_text(encoding="utf-8"))["cases"]

    def test_the_done_cases_route_where_the_brief_says(self):
        expect = {c["prompt"].split(":")[0].split(".")[0].lower(): c["expect"] for c in self.cases}
        self.assertEqual(expect["critique this landing page"], "westack-design")
        self.assertEqual(expect["review this design doc before we build it"], "westack-review")
        self.assertEqual(expect["add a settings screen with a dark-mode toggle"], "westack-build")
        a11y = next(c for c in self.cases if c["prompt"].startswith("Is this page accessible"))
        self.assertEqual((a11y["expect"], a11y["pending_until_built"]), ("westack-a11y", "westack-a11y"))

    def test_the_split_is_fixed_and_every_design_case_names_files_that_exist(self):
        self.assertEqual({c["split"] for c in self.cases}, {"dev", "held-out"})
        for case in (c for c in self.cases if c["expect"] == "westack-design"):
            with self.subTest(case=case["id"]):
                self.assertTrue(case["needs_reference"])
                for relative in case["needs_reference"]:
                    self.assertTrue((SKILL / relative).is_file(), relative)

    def test_the_task_cases_cover_the_degraded_report_and_the_seeded_removal(self):
        campaign = json.loads((SKILL / "evals" / "tasks" / "campaign.json").read_text(encoding="utf-8"))
        cases = {c["id"]: c for c in campaign["cases"]}
        original = {"critique-landing", "seeded-removal"}
        self.assertLessEqual(original, set(cases))
        self.assertEqual([cid for cid in cases if cid not in original and "added" not in cases[cid]], [],
                         "a case beyond the original two says when it was added (held out)")
        patterns = [c["check"]["pattern"] for c in cases["critique-landing"]["rubric"]["criteria"]]
        self.assertTrue(any("DEGRADED" in p for p in patterns) and any("not[- ]run" in p for p in patterns))
        good = cases["critique-landing"]["calibration"]["good"][0]["text"]
        self.assertTrue(all(re.search(p, good) for p in patterns))


if __name__ == "__main__":
    unittest.main()
