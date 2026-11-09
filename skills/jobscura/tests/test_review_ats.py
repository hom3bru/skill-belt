"""Review regressions for English labels and word-gapped letterspacing."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ats_lint as ats


class ReviewATS(unittest.TestCase):
    def test_short_styled_english_labels(self):
        cases = {"PROFESSIONAL SUMMARY": "summary", "Career Summary": "summary",
                 "Core Competencies": "skills", "Key Skills": "skills", "Skills Summary": "skills",
                 "Technical Expertise": "skills", "Areas of Expertise": "skills",
                 "Education History": "education", "Leadership Experience": "experience",
                 "Research Experience": "experience", "Volunteer Experience": "experience",
                 "Selected Projects": "projects", "Professional Certifications": "certifications",
                 "Skills & Abilities": "skills"}
        for heading, expected in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(ats.section_of(heading), expected)
        self.assertIsNone(ats.section_of("History"))
        text = "SKILLS SUMMARY\nPython\nPROFESSIONAL EXPERIENCE\nEngineer 2020 - 2024\nEDUCATION"
        findings, facts = ats.Findings(), {}
        ats.text_checks(text, findings, facts)
        self.assertNotIn("nonstandard_section_headings", [x["id"] for x in findings.items])
        self.assertIn("skills", [x["read_as"] for x in ats.parse_preview(text)["sections"]])

    def test_letterspacing_preserves_word_gaps(self):
        text = "W O R K   E X P E R I E N C E"
        self.assertEqual(ats.heading_text(text), "WORK EXPERIENCE")
        self.assertEqual(ats.section_of(text), "experience")
        self.assertEqual(ats.section_of("E X P É R I E N C E   P R O F E S S I O N N E L L E"), "experience")
        findings, facts = ats.Findings(), {}
        ats.text_checks(text, findings, facts)
        self.assertIn("letter_spaced_headings", [x["id"] for x in findings.items])


if __name__ == "__main__":
    unittest.main()
