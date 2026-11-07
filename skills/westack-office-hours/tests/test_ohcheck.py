"""Tests for westack-office-hours' scripts/ohcheck.py. Local files only.

Run from the repo root:  python -B -m unittest discover -s skills/westack-office-hours/tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import ohcheck  # noqa: E402

GOOD = (HERE.parent / "evals" / "fixtures" / "design-good.md").read_text(encoding="utf-8")


class DocTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        home_patch = patch.object(ohcheck.Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def profile(self, data):
        folder = self.home / ".claude"
        folder.mkdir(exist_ok=True)
        (folder / "skill-belt-profile.json").write_text(json.dumps(data), encoding="utf-8")

    def test_configured_user_name_records_the_choice(self):
        self.profile({"user_name": "Alex Rivera"})
        self.assertEqual(ohcheck.check_doc(GOOD.replace("The user chose", "Alex Rivera chose")), [])

    def test_missing_profile_keeps_the_neutral_owner(self):
        self.assertEqual(ohcheck.check_doc(GOOD), [])
        self.assertIn("Choice must record", " ".join(ohcheck.check_doc(GOOD.replace("The user chose", "Someone chose"))))

    def test_explicit_legacy_alias_keeps_an_old_record_valid(self):
        self.profile({"user_name": "Alex Rivera", "legacy_user_names": ["Former Owner"]})
        self.assertEqual(ohcheck.check_doc(GOOD.replace("The user chose", "Former Owner chose")), [])

    def test_an_unconfigured_old_name_is_not_an_owner(self):
        self.profile({"user_name": "Alex Rivera"})
        self.assertIn("Choice must record", " ".join(ohcheck.check_doc(GOOD.replace("The user chose", "Former Owner chose"))))

    def test_profile_names_are_literal_and_case_insensitive(self):
        self.profile({"user_name": "A. Example"})
        self.assertEqual(ohcheck.check_doc(GOOD.replace("The user chose", "a. example chose")), [])
        self.assertIn("Choice must record", " ".join(ohcheck.check_doc(GOOD.replace("The user chose", "Ax Example chose"))))

    def test_configured_owner_still_requires_a_choice(self):
        self.profile({"user_name": "Alex Rivera"})
        text = GOOD.replace('The user chose the weekly report and said "start with the list, add owners from CODEOWNERS".',
                            "Weekly report is recommended by Alex Rivera.")
        self.assertIn("Choice must record", " ".join(ohcheck.check_doc(text)))

    def test_invalid_profile_is_reported_without_its_values(self):
        for data in ([], {"user_name": 42}, {"legacy_user_names": "Former Owner"},
                     {"legacy_user_names": [42]}):
            with self.subTest(profile=data):
                self.profile(data)
                self.assertEqual(ohcheck.check_doc(GOOD), ["local user profile is unreadable or invalid"])

    def test_cli_uses_the_local_profile(self):
        self.profile({"user_name": "Alex Rivera"})
        document = self.home / "design.md"
        document.write_text(GOOD.replace("The user chose", "Alex Rivera chose"), encoding="utf-8")
        self.assertEqual(ohcheck.main(["doc", str(document)]), 0)

    def test_the_good_fixture_has_the_shape(self):
        self.assertEqual(ohcheck.check_doc(GOOD), [])

    def test_no_mode_line(self):
        self.assertEqual(ohcheck.check_doc(GOOD.replace("Mode: builder\n", "")),
                         ["the document needs a 'Mode: demand' or 'Mode: builder' line"])

    def test_demand_mode_needs_its_own_sections(self):
        problems = " | ".join(ohcheck.check_doc(GOOD.replace("Mode: builder", "Mode: demand")))
        for name in ("Demand evidence", "Status quo", "Who and the narrowest wedge"):
            self.assertIn(name, problems)

    def test_one_approach_and_a_missing_field(self):
        one = GOOD.split("### Live dashboard")[0] + "## Recommendation" + GOOD.split("## Recommendation")[1]
        self.assertIn("at least two approaches", " ".join(ohcheck.check_doc(one)))
        self.assertIn("has no Risk", " ".join(ohcheck.check_doc(GOOD.replace("- Risk: Med\n", ""))))

    def test_premises_must_be_marked(self):
        text = GOOD.replace("1. Flakes are concentrated in a few tests (agreed).", "1. Flakes are concentrated.")
        self.assertIn("premise not marked", " ".join(ohcheck.check_doc(text)))

    def test_the_choice_is_the_users_not_the_recommendation(self):
        text = GOOD.replace('The user chose the weekly report and said "start with the list, add owners from CODEOWNERS".',
                            "Weekly report.")
        self.assertIn("Choice must record that the user chose", " ".join(ohcheck.check_doc(text)))
        text = GOOD.replace("Weekly report: it ships", "A report: it ships")
        self.assertIn("recommendation names none", " ".join(ohcheck.check_doc(text)))

    def test_hedges_are_refused(self):
        text = GOOD.replace("## Open questions", "That could work, but.\n\n## Open questions")
        self.assertIn("'that could work'", " ".join(ohcheck.check_doc(text)))

    def test_cli(self):
        good = HERE.parent / "evals" / "fixtures" / "design-good.md"
        self.assertEqual(ohcheck.main(["doc", str(good)]), 0)
        self.assertEqual(ohcheck.main(["nope"]), 64)


if __name__ == "__main__":
    unittest.main()
