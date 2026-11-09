"""Independent review regressions for local proficiency and direction binding."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
grounding = importlib.import_module("grounding")


class GroundingRoundThreeReview(unittest.TestCase):
    def claims(self, evidence, draft):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "evidence.txt", Path(directory) / "draft.txt"
            source.write_text(evidence, encoding="utf-8")
            target.write_text(draft, encoding="utf-8")
            return grounding.claims(target, [source])

    def levels(self, result):
        return [atom["status"] for row in result["ledger"] for atom in row["atoms"]
                if atom["kind"] == "proficiency"]

    def flags(self, result):
        return [flag["kind"] for row in result["ledger"] for flag in row["flags"]]

    def test_r1_preposed_levels_stay_in_their_list_item(self):
        for source in ("Languages: Spanish (fluent), French (basic).", "Spanish: fluent, French: basic.",
                       "Spanish - fluent, French - basic.", "Spanish (fluent) and French (basic)."):
            with self.subTest(source=source):
                self.assertEqual(self.levels(self.claims(source, "Fluent in Spanish.")), ["supported"])
                self.assertEqual(self.levels(self.claims(source, "Fluent in French.")), ["not_found"])
        for source, draft, expected in (
            ("English (native), German (fluent).", "Native German speaker.", "not_found"),
            ("English (native), German (fluent).", "Native English speaker.", "supported"),
            ("Kubernetes (expert), Terraform (beginner).", "Expert in Terraform.", "not_found"),
            ("Python - advanced, Go - beginner", "Advanced Go developer.", "not_found"),
        ):
            with self.subTest(source=source, draft=draft):
                self.assertEqual(self.levels(self.claims(source, draft)), [expected])
                if expected == "not_found":
                    self.assertEqual(self.claims(source, draft)["status"], "review_needed")

    def test_non_proficiency_senses_do_not_create_levels(self):
        for text in ("Built a native app for customer reporting.", "Built cloud-native applications.",
                     "Advanced to team lead for customer reporting.",
                     "Served as an expert witness in 12 commercial disputes."):
            with self.subTest(text=text):
                self.assertEqual(grounding.proficiency_atoms(text), [])

    def test_trailing_participle_is_not_another_skill(self):
        for text in ("Expert in Python, building dashboards.", "Expert in Python building dashboards."):
            with self.subTest(text=text):
                atoms = grounding.proficiency_atoms(text)
                self.assertEqual([a["skill"] for a in atoms], [{"python"}])
                self.assertEqual(self.levels(self.claims("Expert in Python.", text)), ["supported"])
        for source, draft in (
            ("Expert in Kubernetes.", "Expert in Kubernetes, having run production clusters for five years."),
            ("Languages: Spanish (fluent), French (basic).", "I am fluent in Spanish, which I use daily with clients."),
            ("Advanced Excel: pivot tables, VBA macros.", "Advanced Excel skills, including pivot tables and VBA macros."),
        ):
            with self.subTest(draft=draft):
                self.assertEqual(self.levels(self.claims(source, draft)), ["supported"])

    def test_two_letter_go_skill_has_a_proficiency_atom(self):
        for source, expected in (("Used Go to deploy services.", "not_found"),
                                 ("Expert in Go.", "supported"), ("Go (expert).", "supported")):
            with self.subTest(source=source):
                self.assertEqual(self.levels(self.claims(source, "Expert in Go.")), [expected])
        self.assertEqual(self.levels(self.claims("Advanced Go developer.", "Advanced Go developer.")), ["supported"])

    def test_relative_clause_direction_does_not_describe_main_object(self):
        for source in ("Customer churn, which increased workload, was 15%.",
                       "Customer churn that increased workload was 15%."):
            with self.subTest(source=source):
                self.assertNotIn("direction_mismatch", self.flags(self.claims(source, "Reduced customer churn by 15%.")))
        self.assertNotIn("direction_mismatch", self.flags(self.claims(
            "Lowered the ticket backlog from 500 to 50.",
            "Grew the team that cleared a ticket backlog of 500.")))

    def test_infinitive_direction_does_not_describe_main_object(self):
        source = "Customer churn required work to increase retention by 15%."
        self.assertNotIn("direction_mismatch", self.flags(self.claims(source, "Reduced customer churn by 15%.")))
        self.assertNotIn("direction_mismatch", self.flags(self.claims(
            "Cut release time by 50% to ship 3 releases per month.", "Increased releases to 3 per month.")))

    def test_prevention_is_not_an_asserted_increase(self):
        source = "Kept customer churn from increasing by 15%."
        self.assertNotIn("direction_mismatch", self.flags(self.claims(source, "Reduced customer churn by 15%.")))

    def test_negated_direction_is_neutral_in_either_document(self):
        for text in ("Did not increase customer churn by 15%.", "Never increased customer churn by 15%.",
                     "Didn’t increase customer churn by 15%."):
            for source, draft in ((text, "Reduced customer churn by 15%."),
                                  ("Reduced customer churn by 15%.", text)):
                with self.subTest(source=source, draft=draft):
                    self.assertNotIn("direction_mismatch", self.flags(self.claims(source, draft)))


if __name__ == "__main__":
    unittest.main()
