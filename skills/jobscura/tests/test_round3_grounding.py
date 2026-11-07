"""Isolated proficiency and direction regressions, using fictional evidence."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
grounding = importlib.import_module("grounding")


class GroundingRoundThree(unittest.TestCase):
    def claims(self, evidence, draft):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "evidence.txt"
            target = Path(directory) / "draft.txt"
            source.write_text(evidence, encoding="utf-8")
            target.write_text(draft, encoding="utf-8")
            return grounding.claims(target, [source])

    def test_usage_does_not_establish_proficiency(self):
        for level in ("Expert", "Advanced", "Fluent", "Native", "Proficient", "Mastery",
                      "Extensive experience", "Deep experience"):
            with self.subTest(level=level):
                result = self.claims("Used Kubernetes to deploy two services.", level + " in Kubernetes.")
                atoms = [a for row in result["ledger"] for a in row["atoms"] if a["kind"] == "proficiency"]
                self.assertEqual(len(atoms), 1)
                self.assertEqual(atoms[0]["status"], "not_found")
                self.assertEqual(result["status"], "review_needed")
        result = self.claims("Completed an introductory Spanish course.", "Fluent in Spanish.")
        self.assertEqual(result["status"], "review_needed")

    def test_levels_are_bound_to_the_same_skill(self):
        for source, draft, expected in (
            ("Expert in Kubernetes and proficient in Python.", "Expert in Python.", "not_found"),
            ("Fluent in French. Studied Spanish.", "Fluent in Spanish.", "not_found"),
            ("Advanced in Kubernetes.", "Expert in Kubernetes.", "not_found"),
            ("Not an expert in Kubernetes.", "Expert in Kubernetes.", "not_found"),
            ("Expert in Kubernetes.", "Expert in Kubernetes.", "supported"),
            ("Spanish: fluent.", "Fluent in Spanish.", "supported"),
            ("Deep experience in Kubernetes.", "Extensive experience in Kubernetes.", "supported"),
        ):
            with self.subTest(source=source, draft=draft):
                result = self.claims(source, draft)
                atoms = [a for row in result["ledger"] for a in row["atoms"] if a["kind"] == "proficiency"]
                self.assertEqual([a["status"] for a in atoms], [expected])

    def test_opposite_numeric_directions_are_review_flags(self):
        for source, draft in (
            ("Reduced customer churn by 15%.", "Increased customer churn by 15%."),
            ("Cut support costs by $40,000.", "Grew support costs by $40,000."),
            ("Lowered the error rate by 30%.", "Raised the error rate by 30%."),
            ("Raised the error rate by 30%.", "Lowered the error rate by 30%."),
        ):
            with self.subTest(source=source):
                result = self.claims(source, draft)
                flags = [f for row in result["ledger"] for f in row["flags"]]
                self.assertEqual([f["kind"] for f in flags], ["direction_mismatch"])
                self.assertEqual(result["status"], "review_needed")
                self.assertTrue(all(a["status"] == "supported" for row in result["ledger"]
                                    for a in row["atoms"] if a["kind"] in {"number", "percent"}))
                self.assertTrue(flags[0]["evidence"]["unit_sha"])

    def test_coordinated_skills_each_require_the_claimed_level(self):
        draft = "Expert in Kubernetes and Python."
        for source, expected in (
            ("Expert in Kubernetes.", ["supported", "not_found"]),
            ("Expert in Kubernetes and Python.", ["supported", "supported"]),
            ("Expert in Kubernetes. Expert in Python.", ["supported", "supported"]),
            ("Expert in Kubernetes and proficient in Python.", ["supported", "not_found"]),
            ("Expert in Kubernetes and used Python.", ["supported", "not_found"]),
        ):
            with self.subTest(source=source):
                result = self.claims(source, draft)
                self.assertEqual([a["status"] for row in result["ledger"] for a in row["atoms"]
                                  if a["kind"] == "proficiency"], expected)
        result = self.claims("Expert in Kubernetes and Python.", "Expert in Python.")
        self.assertEqual([a["status"] for row in result["ledger"] for a in row["atoms"]
                          if a["kind"] == "proficiency"], ["supported"])

    def test_adjacent_language_levels_do_not_cross(self):
        draft = "Fluent in Spanish, native in English."
        for source, expected in (
            (draft, ["supported", "supported"]),
            ("Native in Spanish, fluent in English.", ["not_found", "not_found"]),
            ("Fluent in Spanish.", ["supported", "not_found"]),
        ):
            with self.subTest(source=source):
                result = self.claims(source, draft)
                self.assertEqual([a["status"] for row in result["ledger"] for a in row["atoms"]
                                  if a["kind"] == "proficiency"], expected)

    def test_first_person_wrapper_is_not_a_skill_requirement(self):
        for source, draft in (
            ("Extensive experience with Kubernetes.", "I have extensive experience with Kubernetes."),
            ("I have extensive experience with Kubernetes.", "Extensive experience with Kubernetes."),
        ):
            with self.subTest(source=source):
                result = self.claims(source, draft)
                self.assertEqual([a["status"] for row in result["ledger"] for a in row["atoms"]
                                  if a["kind"] == "proficiency"], ["supported"])

    def test_neutral_occurrence_suppresses_direction_flag(self):
        for word in ("up", "down", "more", "less"):
            for source, draft in (
                ("Customer churn was " + word + " by 15%.", "Increased customer churn by 15%."),
                ("Reduced customer churn by 15%.", "Customer churn was " + word + " by 15%."),
                ("Reduced customer churn by 15%.\nCustomer churn was " + word + " by 15%.",
                 "Increased customer churn by 15%."),
            ):
                with self.subTest(source=source, draft=draft):
                    result = self.claims(source, draft)
                    self.assertFalse(any(f["kind"] == "direction_mismatch"
                                         for row in result["ledger"] for f in row["flags"]))

    def test_direction_requires_matching_context_and_value(self):
        for source in ("Reduced customer churn by 20%.", "Reduced warehouse waste by 15%.",
                       "Increased customer churn by 15%.",
                       "Reduced customer churn by 15%.\nIncreased customer churn by 15%."):
            result = self.claims(source, "Increased customer churn by 15%.")
            self.assertFalse(any(f["kind"] == "direction_mismatch"
                                 for row in result["ledger"] for f in row["flags"]))


if __name__ == "__main__":
    unittest.main()
