"""Review regressions against bc0fe38; offline, fictional fixtures only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ats_lint as ats


class ReviewRound3ATS(unittest.TestCase):
    def report(self, text, filename="resume.txt"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.write_text(text, encoding="utf-8")
            return ats.lint(path, as_of="2026-11-05")

    def issues(self, result):
        return [issue for item in result["findings"] if item["id"] == "chronology"
                for issue in item["evidence"]["issues"]]

    def test_r2_nfd_is_advisory_not_garbled(self):
        text = unicodedata.normalize("NFD", "é è à ô ü " * 30)
        result = self.report(text)
        self.assertNotEqual(result["status"], "blocking_issues")
        self.assertEqual(result["facts"]["garbled_glyphs"]["ratio"], 0)
        accents = [f for f in result["findings"] if f["id"] == "decomposed_accents"]
        self.assertEqual(len(accents), 1)
        self.assertEqual(accents[0]["severity"], "info")
        self.assertEqual(accents[0]["evidence"]["count"], 150)
        broken = self.report("\ufffd" * 20)
        self.assertEqual(broken["status"], "blocking_issues")

    def test_r2_nfc_marks_without_composed_form_stay_clean(self):
        text = unicodedata.normalize("NFC", "ẹ\u0301 ọ\u0300 " * 10)
        self.assertTrue(any("\u0300" <= c <= "\u036f" for c in text))
        result = self.report(text)
        self.assertFalse({f["id"] for f in result["findings"]} & {"decomposed_accents", "garbled_glyphs"})

    def test_r4_bare_nine_digits_are_not_ssns(self):
        for text in ("Phone: 612345678", "Phone: 501234567", "Badge 123456789"):
            with self.subTest(text=text):
                result = self.report("Jane Example\n" + text)
                self.assertNotIn("sensitive_identifier_in_document", {f["id"] for f in result["findings"]})
                self.assertNotIn("[masked]", json.dumps(result))
        for value in ("123-45-6789", "123 45 6789", "SSN: 123456789", "Social security number: 123456789"):
            self.assertIn("ssn", {kind for _, _, kind in ats.sensitive_identifiers(value)})
        for value in ("SSN: 000123456", "SSN: 666123456", "SSN: 900123456", "SSN: 123003456", "SSN: 123450000", "SSN: 111111111"):
            self.assertFalse(ats.sensitive_identifiers(value))

    def test_r4_luhn_valid_phone_remains_in_preview(self):
        # A synthetic 13-digit mobile chosen to satisfy Luhn, not a real contact.
        digits = "441234567890"
        phone = next("+" + digits + str(n) for n in range(10)
                     if sum((int(c) * 2 - 9 if int(c) * 2 > 9 else int(c) * 2)
                            if i % 2 else int(c)
                            for i, c in enumerate((digits + str(n))[::-1])) % 10 == 0)
        for value in (phone, phone[1:]):
            result = self.report("Jane Example\n" + value)
            self.assertNotIn("sensitive_identifier_in_document", {f["id"] for f in result["findings"]})
            self.assertEqual(result["facts"]["parse_preview"]["contact"]["phone"], value)
        self.assertIn("payment_card", {k for _, _, k in ats.sensitive_identifiers("4111111111111111")})

    def test_r5_collapsed_dates_use_matched_endpoints(self):
        for dates in ("2019to2021", "2019until2021", "Jan 2019toDec 2021"):
            with self.subTest(dates=dates):
                result = self.report("Experience\nEngineer " + dates)
                self.assertEqual(result["facts"]["parse_preview"]["experience_entries"][0]["dates"], dates)
                self.assertEqual(self.issues(result), [])
        findings = ats.Findings()
        ats.chronology_checks({"experience_entries": [{"line": 2, "dates": "2019"}]}, findings, ats.date(2026, 11, 5))
        self.assertEqual(findings.items, [])

    def test_handover_precision_and_real_overlap(self):
        for entries in ("A Jan 2020 - Jun 2021\nB Jun 2021 - Dec 2022",
                        "A 2019 - 2021\nB 2021 - 2023"):
            self.assertEqual(self.issues(self.report("Experience\n" + entries)), [])
        overlap = self.issues(self.report("Experience\nA Jan 2020 - Dec 2022\nB Jun 2021 - Dec 2023"))
        self.assertEqual([i["kind"] for i in overlap], ["overlap"])

    def test_month_prefix_is_part_of_heading(self):
        self.assertIsNone(ats.DATE_RANGE.match("Novaterra 2020 - Jun 2020"))
        result = self.report("Experience\nNovaterra 2020 - Jun 2020")
        self.assertEqual(result["facts"]["parse_preview"]["experience_entries"][0]["heading"], "Novaterra")
        self.assertEqual(self.issues(result), [])
        self.assertNotIn("Mon YYYY", self.report("Experience\nNovaterra 2020 - 2021")["facts"]["date_styles"])
        preview = ats.parse_preview("Experience\nRole November 2019 - September 2021")
        self.assertEqual(len(preview["experience_entries"]), 1)

    def test_future_present_is_not_duplicate_reversal(self):
        issues = self.issues(self.report("Experience\nRole 2031 - Present"))
        self.assertEqual([i["kind"] for i in issues], ["future_start"])
        reverse = self.issues(self.report("Experience\nRole 2023 - 2019"))
        self.assertEqual([i["kind"] for i in reverse], ["end_before_start"])
        explicit = self.issues(self.report("Experience\nRole 2031 - 2019"))
        self.assertEqual({i["kind"] for i in explicit}, {"future_start", "end_before_start"})

    def test_links_citations_and_empty_braces_are_filled_content(self):
        for text in ("See [portfolio](https://example.com/work).", "Published research [1].", "Use {{ }} in templates."):
            with self.subTest(text=text):
                result = self.report(text)
                self.assertNotIn("placeholder_text", {f["id"] for f in result["findings"]})
        for text in ("[Company Name]", "[verify]", "{{role}}", "<insert name>", "XX%", "$XX", "TBD", "lorem ipsum"):
            self.assertIn("placeholder_text", {f["id"] for f in self.report(text)["findings"]})

    def test_underscore_filename_is_masked_on_success(self):
        number = "4111111111111111"
        result = self.report("Jane Example", "Jane_Example_" + number + ".txt")
        self.assertNotIn(number, json.dumps(result))
        self.assertIn("[masked]", result["facts"]["file"])

    def test_read_input_errors_mask_filename_and_keep_json_contract(self):
        number = "4111111111111111"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("Jane_Example_" + number + ".txt")
            command = [sys.executable, "-B", str(Path(ats.__file__)), str(path)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(json.loads(result.stderr)["status"], "blocked")
            self.assertNotIn(number, result.stderr)
            self.assertIn("[masked]", result.stderr)
            path.write_text("Example", encoding="utf-8")
            for error in (ats.ToolError("file exceeds limit: " + path.name),
                          PermissionError(13, "Permission denied", str(path))):
                with mock.patch.object(ats.common, "read_input", side_effect=error):
                    with self.assertRaises(ats.ToolError) as raised:
                        ats.lint(path)
                self.assertNotIn(number, str(raised.exception))
                self.assertIn("[masked]", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
