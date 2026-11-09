"""A4 regressions; runnable unchanged against an isolated base scripts directory."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ats_lint as ats


class Round2ATS(unittest.TestCase):
    def check_text(self, text):
        findings, facts = ats.Findings(), {}
        ats.text_checks(text, findings, facts)
        return {item["id"]: item for item in findings.items}, facts

    def test_locale_resumes_and_english_control(self):
        resumes = {
            "en": ("EXPERIENCE", "EDUCATION", "SKILLS"),
            "es": ("EXPERIENCIA", "EDUCACI\u00d3N", "HABILIDADES"),
            "fr": ("EXP\u00c9RIENCE PROFESSIONNELLE", "FORMATION", "COMP\u00c9TENCES"),
            "pt": ("EXPERI\u00caNCIA", "EDUCA\u00c7\u00c3O", "COMPET\u00caNCIAS"),
            "de": ("BERUFSERFAHRUNG", "AUSBILDUNG", "F\u00c4HIGKEITEN"),
            "it": ("ESPERIENZA", "ISTRUZIONE", "ABILIT\u00c0"),
        }
        for lang, headings in resumes.items():
            with self.subTest(lang=lang):
                text = "Jane Doe\njane@example.com\n{}\nEngineer 2020 - 2024\n{}\nUniversity, Bachelor\n{}\nPython".format(*headings)
                findings, facts = self.check_text(text)
                self.assertNotIn("nonstandard_section_headings", findings)
                preview = ats.parse_preview(text)
                self.assertEqual([s["read_as"] for s in preview["sections"]],
                                 ["experience", "education", "skills"])
                self.assertEqual(len(preview["experience_entries"]), 1)
                self.assertEqual(facts["standard_sections"], ["education", "experience", "skills"])

    def test_explicit_language_cli_and_invalid_language(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.txt"
            path.write_text("EXPERIENCIA\nEDUCACI\u00d3N\nHABILIDADES", encoding="utf-8")
            command = [sys.executable, "-B", str(Path(ats.__file__)), str(path), "--lang"]
            spanish = subprocess.run(command + ["es"], capture_output=True, text=True)
            self.assertEqual(spanish.returncode, 0, spanish.stderr)
            self.assertEqual(json.loads(spanish.stdout)["facts"]["standard_sections"],
                             ["education", "experience", "skills"])
            english = subprocess.run(command + ["en"], capture_output=True, text=True)
            self.assertEqual(json.loads(english.stdout)["facts"]["standard_sections"], [])
            invalid = subprocess.run(command + ["xx"], capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)

    def test_complete_headings_and_all_joiners(self):
        for line in ("experience in product engineering", "Experience In Product Engineering",
                     "EXPERIENCE IN PRODUCT ENGINEERING", "My Skills", "Skills: Python"):
            with self.subTest(prose=line):
                self.assertIsNone(ats.section_of(line))
                self.assertEqual(self.check_text(line)[1]["standard_sections"], [])
        for joiner in ("&", "and", "y", "et", "e", "und"):
            with self.subTest(joiner=joiner):
                text = "experience {} education\nskills".format(joiner)
                self.assertEqual(ats.section_of(text.splitlines()[0]), "experience")
                self.assertEqual(self.check_text(text)[1]["standard_sections"],
                                 ["education", "experience", "skills"])
        self.assertIsNone(ats.section_of("Experience and product engineering"))

    def test_garbled_classes_and_cid_denominator(self):
        findings, facts = self.check_text("(cid:12)(cid:34)(cid:56)\ufffd\ufffd\ue001\U000f0001\U00100001")
        self.assertEqual(findings["garbled_glyphs"]["severity"], "blocker")
        self.assertEqual(facts["garbled_glyphs"], {
            "classes": {"cid": 3, "replacement": 2, "private_use": 3},
            "visible_characters": 8, "ratio": 1.0})
        self.assertIn("private_use_glyphs", findings)

    def test_ligature_thresholds_and_private_use_floor(self):
        for length, severity in ((200, "warning"), (20, "blocker")):
            with self.subTest(length=length):
                findings, facts = self.check_text("\ufb03" + "a" * (length - 1) + " \n\t")
                self.assertEqual(findings["garbled_glyphs"]["severity"], severity)
                self.assertEqual(facts["garbled_glyphs"]["classes"], {"ligature": 1})
        findings, _ = self.check_text("\ue000" + "a" * 1000)
        self.assertIn("private_use_glyphs", findings)
        self.assertNotIn("garbled_glyphs", findings)
        findings, facts = self.check_text(" \n\t")
        self.assertEqual(facts["garbled_glyphs"]["ratio"], 0.0)
        self.assertNotIn("garbled_glyphs", findings)

    def test_letter_spaced_headings_normalized_and_warned(self):
        text = "E X P E R I E N C E:\nEngineer 2020 - 2024\nE D U C A C I \u00d3 N\nHABILIDADES"
        findings, facts = self.check_text(text)
        self.assertIn("letter_spaced_headings", findings)
        self.assertNotIn("nonstandard_section_headings", findings)
        self.assertEqual([s["title"] for s in ats.parse_preview(text)["sections"]],
                         ["EXPERIENCE", "EDUCACI\u00d3N", "HABILIDADES"])
        self.assertIsNone(ats.section_of("S K I L"))
        self.assertIsNone(ats.section_of("e x p e r i e n c e"))
        self.assertEqual(facts["standard_sections"], ["education", "experience", "skills"])


if __name__ == "__main__":
    unittest.main()
