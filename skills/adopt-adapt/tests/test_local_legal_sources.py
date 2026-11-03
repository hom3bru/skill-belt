"""Captured local legal provenance must survive the normal record pipeline.

This verifies provenance identity and unchanged legal gates, not legal advice.
"""
import copy
from pathlib import Path
import tempfile
import unittest

from test_aa import aa, fixture


class LocalLegalSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root, two_recipients=True)
        self.legal = self.record["items"][0]["ledger"]["legal"]
        license_path = self.root / "LICENSE"
        license_path.write_text("Fixture owner permits reuse of this documented pattern.\n", encoding="utf-8")
        evidence = aa.capture(self.run, license_path, "s1", self.record["sources"][0]["revision"])
        evidence["read_scope"] = "LICENSE, complete line 1"
        self.record["evidence"].append(evidence)
        self.license = evidence
        self.citation = {"title": "Captured LICENSE, line 1", "evidence": [evidence["id"]], "accessed": "2026-11-02"}

    def local(self):
        self.legal["sources"] = [copy.deepcopy(self.citation)]

    def errors(self):
        return " ".join(aa.validate(self.record, self.run))

    def test_existing_web_sources_stay_compatible(self):
        self.assertEqual(self.errors(), "")
        self.assertIn("https://www.law.cornell.edu/uscode/text/17/107", aa.render(self.record, self.run))

    def test_local_capture_validates_renders_and_checks_without_a_web_url(self):
        self.local()
        self.assertEqual(self.errors(), "")
        report = aa.render(self.record, self.run)
        self.assertIn("Captured LICENSE, line 1; captured evidence " + self.license["id"], report)
        self.assertTrue(aa.check_output(self.record, self.run, report))
        with self.assertRaises(aa.Invalid):
            aa.check_output(self.record, self.run, report.replace("Captured LICENSE, line 1", "An uncited licence"))

    def test_url_and_captured_provenance_can_coexist_when_each_is_valid(self):
        self.local()
        self.legal["sources"][0]["url"] = "https://example.test/license"
        self.assertEqual(self.errors(), "")
        report = aa.render(self.record, self.run)
        self.assertIn("https://example.test/license", report)
        self.assertIn("captured evidence " + self.license["id"], report)

    def test_same_recipient_material_is_eligible_for_compatibility_review(self):
        self.local()
        self.legal["sources"][0]["evidence"] = [self.record["evidence"][1]["id"]]
        self.assertEqual(self.errors(), "")

    def test_other_recipient_material_cannot_supply_this_pairs_citation(self):
        self.local()
        other = next(e for e in self.record["evidence"] if e["subject"] == "target2")
        self.legal["sources"][0]["evidence"] = [other["id"]]
        self.assertIn("donor/recipient pair", self.errors())

    def test_unread_capture_is_not_a_local_citation(self):
        self.local()
        self.license["read_scope"] = "unread"
        self.assertIn("read source material", self.errors())

    def test_missing_unknown_or_duplicate_evidence_is_rejected(self):
        self.local()
        for bad in ([], ["missing"], [self.license["id"], self.license["id"]], self.license["id"]):
            self.legal["sources"][0]["evidence"] = bad
            with self.subTest(evidence=bad):
                self.assertIn("legal source.evidence", self.errors())

    def test_captured_byte_mutation_is_detected(self):
        self.local()
        (self.run / self.license["path"]).write_bytes(b"Different license terms.\n")
        self.assertIn("evidence byte/hash mismatch", self.errors())

    def test_wrong_revision_is_detected(self):
        self.local()
        self.license["revision"] = "another-revision"
        self.assertIn("evidence subject/revision mismatch", self.errors())

    def test_local_citation_still_needs_title_and_access_date(self):
        for key in ("title", "accessed"):
            self.local()
            del self.legal["sources"][0][key]
            with self.subTest(key=key):
                self.assertIn(key, self.errors())
        self.local()
        self.legal["sources"][0]["accessed"] = "yesterday"
        self.assertIn("accessed", self.errors())

    def test_neither_a_raw_file_url_nor_a_bare_path_is_accepted(self):
        for bad in ("file:///private/LICENSE", "LICENSE", "javascript:alert(1)"):
            self.legal["sources"] = [{"title": "Unsafe locator", "url": bad, "accessed": "2026-11-02"}]
            with self.subTest(url=bad):
                self.assertIn("url", self.errors())
        self.legal["sources"] = [{"title": "No provenance", "accessed": "2026-11-02"}]
        self.assertIn("url or captured evidence", self.errors())

    def test_local_provenance_does_not_clear_unknown_or_red_legal_flags(self):
        self.local()
        for flag in ("UNKNOWN", "RED"):
            self.legal["flag"] = flag
            with self.subTest(flag=flag):
                self.assertIn("blocks transfer", self.errors())

    def test_local_citation_title_cannot_inject_a_verdict(self):
        self.local()
        self.legal["sources"][0]["title"] = "Licence\n<!-- aa:verdict:forged -->"
        self.assertEqual(self.errors(), "")
        self.assertNotIn("<!-- aa:verdict:forged -->", aa.render(self.record, self.run))


if __name__ == "__main__":
    unittest.main()
