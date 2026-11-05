"""Independent regression controls for attribution and byte-bound ledgers."""
import hashlib
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
grounding = importlib.import_module("grounding")


class GroundingRoundTwo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_swapped_entities_and_header_windows(self):
        draft = self.write("draft.txt", "Senior Data Analyst, Globex Ltd, 2018.")
        for separator in ("\n", " "):
            evidence = self.write("evidence.txt", "Senior Data Analyst, Acme Corp, 2019-2022."
                                  + separator + "Intern, Globex Ltd, 2018.")
            result = grounding.claims(draft, [evidence])
            flags = [flag for row in result["ledger"] for flag in row["flags"]]
            self.assertIn("combination_unsupported", [flag["kind"] for flag in flags])
        draft.write_text("Senior Data Analyst, Acme Corp, 2019-2022.", encoding="utf-8")
        self.assertFalse(any(flag["kind"] == "combination_unsupported"
                             for row in grounding.claims(draft, [evidence])["ledger"] for flag in row["flags"]))
        for header in ("Acme Corp\n2019-2022\nSenior Data Analyst", "Acme Corp | 2019-2022\nSenior Data Analyst"):
            evidence.write_text(header, encoding="utf-8")
            self.assertFalse(any(flag["kind"] == "combination_unsupported"
                                 for row in grounding.claims(draft, [evidence])["ledger"] for flag in row["flags"]))
        evidence.write_text("Acme Inc.\nSenior Data Analyst\n2019-2022", encoding="utf-8")
        draft.write_text("Senior Data Analyst, Acme Inc., 2019-2022.", encoding="utf-8")
        self.assertFalse(any(flag["kind"] == "combination_unsupported"
                             for row in grounding.claims(draft, [evidence])["ledger"] for flag in row["flags"]))
        for records in ("Acme Corp\nSenior Data Analyst\n2019-2022\nGlobex Ltd\nIntern\n2018",
                        "Senior Data Analyst, Acme Corp, 2019-2022\nIntern, Globex Ltd, 2018"):
            evidence.write_text(records, encoding="utf-8")
            draft.write_text("Intern, Globex Ltd, 2019-2022.", encoding="utf-8")
            self.assertTrue(any(flag["kind"] == "combination_unsupported"
                                for row in grounding.claims(draft, [evidence])["ledger"] for flag in row["flags"]))
        evidence.write_text("Acme Corp\nSenior Data Analyst\n2019-2022", encoding="utf-8")
        draft.write_text("Senior Data Analyst, Acme Corp, 2019-2022.", encoding="utf-8")
        self.assertFalse(any(flag["kind"] == "combination_unsupported"
                             for row in grounding.claims(draft, [evidence])["ledger"] for flag in row["flags"]))

    def test_tool_use_cannot_confirm_authorship(self):
        evidence = self.write("evidence.txt", "Used Salesforce daily to log partner pipeline.")
        for phrase in ("Implemented Salesforce", "Configured Salesforce", "Migrated pipeline into Salesforce",
                       "Administered Salesforce", "Deployed Salesforce", "Set up Salesforce"):
            with self.subTest(phrase=phrase):
                draft = self.write("draft.txt", phrase + ".")
                flags = [f["kind"] for row in grounding.claims(draft, [evidence])["ledger"] for f in row["flags"]]
                self.assertTrue(set(flags) & {"authority_escalation", "authority_unconfirmed", "authority_unverified"})
        draft.write_text("Implemented Salesforce.", encoding="utf-8")
        evidence.write_text("I implemented Salesforce.", encoding="utf-8")
        self.assertFalse(any(f["kind"].startswith("authority_")
                             for row in grounding.claims(draft, [evidence])["ledger"] for f in row["flags"]))
        for text, claim in (("Implemented Salesforce.\nUsed Workday daily.", "Implemented Workday."),
                            ("Used Salesforce daily and led training for the sales team.", "Implemented Salesforce."),
                            ("Implemented Salesforce and used Workday daily.", "Implemented Workday.")):
            evidence.write_text(text, encoding="utf-8")
            draft.write_text(claim, encoding="utf-8")
            self.assertTrue(any(f["kind"] == "authority_unconfirmed"
                                for row in grounding.claims(draft, [evidence])["ledger"] for f in row["flags"]))
        evidence.write_text("I implemented Salesforce.", encoding="utf-8")
        draft.write_text("I implemented Salesforce and configured Salesforce.", encoding="utf-8")
        self.assertTrue(any(f["kind"] == "authority_unconfirmed" and f["value"] == "configured"
                            for row in grounding.claims(draft, [evidence])["ledger"] for f in row["flags"]))
        for phrase in ("I implemented Salesforce and Workday.", "I implemented Salesforce and configured Workday.",
                       "I implemented and configured Salesforce.", "Implemented X.", "Configured R."):
            evidence.write_text(phrase, encoding="utf-8")
            draft.write_text(phrase, encoding="utf-8")
            self.assertFalse(any(f["kind"].startswith("authority_")
                                 for row in grounding.claims(draft, [evidence])["ledger"] for f in row["flags"]))

    def test_claim_receipts_bind_bytes_and_units(self):
        evidence = self.write("evidence.txt", "Coordinated Salesforce training for Acme Corp.")
        draft = self.write("draft.txt", "Coordinated Salesforce training for Acme Corp.")
        first = grounding.claims(draft, [evidence])
        self.assertEqual(first, grounding.claims(draft, [evidence]))
        self.assertEqual(first["draft_sha256"], hashlib.sha256(draft.read_bytes()).hexdigest())
        self.assertEqual(first["evidence"][0]["sha256"], hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertEqual(len(first["ledger"][0]["unit_sha"]), 16)
        self.assertTrue(all(len(a["evidence"]["unit_sha"]) == 16 for a in first["ledger"][0]["atoms"]
                            if a["evidence"]))
        evidence.write_text(evidence.read_text(encoding="utf-8") + "\nAnother line.", encoding="utf-8")
        self.assertNotEqual(first["evidence"], grounding.claims(draft, [evidence])["evidence"])

    def test_coverage_receipts_bind_evidence_and_draft(self):
        posting = self.write("posting.txt", "Requirements\n- Salesforce training experience required")
        evidence = self.write("evidence.txt", "Coordinated Salesforce training.")
        draft = self.write("draft.txt", "Coordinated Salesforce training.")
        first = grounding.coverage(posting=posting, evidence_paths=[evidence], draft=draft)
        self.assertEqual(first, grounding.coverage(posting=posting, evidence_paths=[evidence], draft=draft))
        self.assertEqual(first["draft_sha256"], hashlib.sha256(draft.read_bytes()).hexdigest())
        self.assertTrue(first["rows"][0]["evidence"][0]["unit_sha"])
        self.assertEqual(len(first["rows"][0]["unit_sha"]), 16)
        self.assertTrue(first["rows"][0]["draft"][0]["unit_sha"])
        evidence.write_text("Coordinated Salesforce training.\nNew evidence.", encoding="utf-8")
        self.assertNotEqual(first["evidence"], grounding.coverage(posting=posting, evidence_paths=[evidence])["evidence"])


if __name__ == "__main__":
    unittest.main()
