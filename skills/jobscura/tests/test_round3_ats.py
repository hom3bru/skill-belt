"""Isolated J1-J4 regressions using fictional identifiers and offline fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ats_lint as ats


class Round3ATS(unittest.TestCase):
    def report(self, text, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.txt"
            path.write_text(text, encoding="utf-8")
            return ats.lint(path, **kwargs)

    def test_sensitive_identifiers_and_preview_redaction(self):
        values = ["4111 1111 1111 1111", "GB82 WEST 1234 5698 7654 32", "123-45-6789",
                  "2000-01-02", "X1234567"]
        text = "Jane Example\n" + "\n".join(values[:3]) + "\nDOB: " + values[3] + "\nPassport number: " + values[4]
        text += "\nExperience\nEngineer 2020 - 2024 " + values[0] + "\nEducation\nUniversity " + values[1]
        result = self.report(text)
        evidence = next(f["evidence"] for f in result["findings"] if f["id"] == "sensitive_identifier_in_document")
        self.assertEqual({e["kind"] for e in evidence}, {"payment_card", "iban", "ssn", "date_of_birth", "passport"})
        serialized = json.dumps(result)
        for value in values:
            self.assertNotIn(value, serialized)
        # Analysis ran on the original text, before masking.
        self.assertTrue(result["facts"]["has_phone"])
        self.assertEqual(len(result["facts"]["parse_preview"]["experience_entries"]), 1)

    def test_identifier_validation_and_label_boundaries(self):
        self.assertTrue(ats.sensitive_identifiers("123-45-6789"))
        text = "4111111111111112\nGB83 WEST 1234 5698 7654 32\n000-12-3456\n666-12-3456\n900-12-3456\n123-00-3456\n123-12-0000\n111-11-1111\n123-45 6789\nmydob: 2000-01-02\npassportable 1234567"
        result = self.report(text)
        self.assertNotIn("sensitive_identifier_in_document", {f["id"] for f in result["findings"]})

    def test_label_values_context_and_chronology_dates(self):
        dates = ("2000-01-02", "02/01/2000", "2 January 2000", "January 2, 2000",
                 "2  Jan  2000")
        for value in dates:
            with self.subTest(value=value):
                result = self.report("DOB: " + value + "\nExperience\n" + value + " Role 2020 - 2024", as_of="2026-11-05")
                self.assertIn("sensitive_identifier_in_document", {f["id"] for f in result["findings"]})
                self.assertNotIn(" ".join(value.split()), json.dumps(result))
        clean = self.report("Passport experience 2020\nPassport processing 2021\nDOB experience 2020\nExperience\nRole 2031 - Present", as_of="2026-11-05")
        self.assertNotIn("sensitive_identifier_in_document", {f["id"] for f in clean["findings"]})
        chronology = next(f for f in clean["findings"] if f["id"] == "chronology")
        self.assertEqual(chronology["evidence"]["as_of"], "2026-11-05")

    def test_identifier_separators_and_excerpt_context(self):
        for value in ("4111111111111111", "4111-1111-1111-1111", "123 45 6789", "SSN: 123456789",
                      "GB82WEST12345698765432", "GB82 WEST 1234 5698 7654 32"):
            with self.subTest(value=value):
                # Put the identifier before the excerpt boundary and its label after it.
                result = self.report("Experience\n" + value + " " + "Engineer " * 30 + "2020 - 2024\nEducation\nUniversity " + value)
                self.assertIn("sensitive_identifier_in_document", {f["id"] for f in result["findings"]})
                self.assertNotIn(value.removeprefix("SSN: "), json.dumps(result))
        result = self.report("IBAN: GB82 WEST 1234 5698 7654 32 USD")
        self.assertNotIn("GB82 WEST 1234 5698 7654 32", json.dumps(result))

    def test_metadata_and_filename_are_masked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "4111111111111111.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Jane Example</w:t></w:r></w:p></w:body></w:document>')
                archive.writestr("docProps/core.xml", '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>4111111111111111</dc:creator></cp:coreProperties>')
            self.assertNotIn("4111111111111111", json.dumps(ats.lint(path)))

    def test_all_placeholders_and_forbidden_terms(self):
        for value in ("[Company Name]", "[verify]", "{{role}}", "<insert name>", "XX%", "$XX", "TBD", "lorem ipsum"):
            with self.subTest(value=value):
                self.assertIn("placeholder_text", {f["id"] for f in self.report(value)["findings"]})
        result = self.report("Old Employer and Other Co", forbid=["old employer", "Other Co"])
        evidence = next(f["evidence"] for f in result["findings"] if f["id"] == "placeholder_text")
        self.assertEqual(len(evidence), 2)
        self.assertNotIn("placeholder_text", {f["id"] for f in self.report("TBDish XXylophone")["findings"]})

    def test_chronology_deterministic_and_neutral(self):
        text = "Experience\nA 2023 - 2019\nB 2031 - Present\nC Jan 2020 - Dec 2021\nD Jun 2021 - Dec 2022\nE Aug 2023 - Jan 2024"
        result = self.report(text, as_of="2026-11-05")
        item = next(f for f in result["findings"] if f["id"] == "chronology")
        self.assertEqual(item["severity"], "info")
        self.assertEqual({i["kind"] for i in item["evidence"]["issues"]}, {"end_before_start", "future_start", "overlap", "gap"})
        self.assertIn("legitimate", item["message"])
        self.assertEqual(item["evidence"]["as_of"], "2026-11-05")

    def test_chronology_union_and_gap_boundary(self):
        text = "Experience\nA 2010 - 2020\nB 2012 - 2013\nC 2015 - 2016\nD Jul 2021 - Dec 2021"
        result = self.report(text, as_of="2026-11-05")
        issues = next(f["evidence"]["issues"] for f in result["findings"] if f["id"] == "chronology")
        self.assertEqual([i["kind"] for i in issues], ["overlap", "overlap"])

    def test_decomposed_accents_and_nfc_control(self):
        result = self.report("Mu\u0308ller Gene\u0300ve")
        self.assertEqual(result["facts"]["decomposed_accents"], 2)
        self.assertIn("NFC", next(f["message"] for f in result["findings"] if f["id"] == "decomposed_accents"))
        self.assertEqual(self.report("Müller Genève")["facts"]["decomposed_accents"], 0)
        self.assertNotEqual(result["status"], "blocking_issues")
        self.assertEqual(next(f["severity"] for f in result["findings"] if f["id"] == "decomposed_accents"), "info")

    def test_cli_options_and_invalid_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.txt"
            path.write_text("Experience\nRole 2031 - Present\nOld Employer\nOther Co", encoding="utf-8")
            command = [sys.executable, "-B", str(Path(ats.__file__)), str(path)]
            result = subprocess.run(command + ["--as-of", "2026-11-05", "--forbid", "Old Employer", "--forbid", "Other Co"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("chronology", {f["id"] for f in json.loads(result.stdout)["findings"]})
            bad = subprocess.run(command + ["--as-of", "2026-02-30"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, "")
            self.assertEqual(json.loads(bad.stderr)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
