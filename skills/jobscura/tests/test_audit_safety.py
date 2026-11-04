"""Offline regression checks for audit findings R1, R3 and R7."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ats_lint
import grounding
import posting_intel

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class AuditSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def docx(self, parts):
        path = self.root / "resume.docx"
        with ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            all_parts = {"word/document.xml": "<w:p><w:r><w:t>Resume</w:t></w:r></w:p>", **parts}
            for name, body in all_parts.items():
                archive.writestr(name, f'<w:document xmlns:w="{WNS}">{body}</w:document>')
        return ats_lint.lint(path)

    def test_revisions_and_comments_across_exact_story_parts(self):
        clean = self.docx({})
        self.assertFalse(any(f["severity"] == "blocker" for f in clean["findings"]))
        names = ["word/document.xml", "word/header1.xml", "word/footer2.xml",
                 "word/footnotes.xml", "word/endnotes.xml"]
        revision = '<w:ins/><w:moveTo/><w:del><w:r><w:delText>Private</w:delText></w:r></w:del><w:moveFrom/><w:commentReference/>'
        result = self.docx({name: revision for name in names})
        self.assertEqual(result["facts"]["tracked_insertions"], 10)
        self.assertEqual(result["facts"]["tracked_deletions"], 10)
        self.assertEqual(result["facts"]["comment_references"], 5)
        self.assertEqual(result["facts"].get("privacy_parts"), sorted(names))
        blockers = {f["id"] for f in result["findings"] if f["severity"] == "blocker"}
        self.assertTrue({"tracked_changes", "comments"} <= blockers)
        for name in names:
            with self.subTest(part=name):
                result = self.docx({name: '<w:del><w:r><w:delText>Private</w:delText></w:r></w:del>'})
                self.assertIn("tracked_changes", {f["id"] for f in result["findings"]})
                comments = self.docx({name: '<w:commentReference/>'})
                self.assertEqual(comments["facts"]["comment_references"], 1)
                self.assertIn("comments", {f["id"] for f in comments["findings"]})
        excluded = self.docx({"word/styles.xml": revision, "word/other.xml": revision})
        self.assertEqual(excluded["facts"]["tracked_deletions"], 0)
        self.assertEqual(excluded["facts"]["privacy_parts"], [])

    def test_invisible_story_text_keeps_layout_body_only(self):
        layout = '<w:tbl/><w:txbxContent/><w:drawing/><w:pict/><w:cols w:num="2"/>'
        for value in ("0", "false", "off"):
            result = self.docx({"word/header1.xml": f'<w:vanish w:val="{value}"/>' + layout})
            self.assertFalse(any(f["severity"] == "blocker" for f in result["findings"]))
            self.assertTrue({"tables", "text_boxes", "multi_column"}.isdisjoint(f["id"] for f in result["findings"]))
            self.assertEqual(result["facts"]["images"], 0)
        names = ["word/document.xml", "word/header1.xml", "word/footer1.xml",
                 "word/footnotes.xml", "word/endnotes.xml"]
        for name in names:
            for markup, key in (("<w:vanish/>", "hidden_runs"),
                                ('<w:color w:val="FFFFFF"/>', "white_text_runs"),
                                ('<w:sz w:val="4"/>', "tiny_text_runs")):
                with self.subTest(part=name, property=key):
                    result = self.docx({name: markup})
                    finding = next(f for f in result["findings"] if f["id"] == "hidden_or_invisible_text")
                    self.assertEqual(finding["severity"], "blocker")
                    self.assertEqual(finding["evidence"][key], 1)
                    self.assertEqual(result["facts"].get("privacy_parts"), [name])
        combined = self.docx({name: '<w:vanish/><w:color w:val="FFFFFE"/><w:sz w:val="2"/>' for name in names})
        finding = next(f for f in combined["findings"] if f["id"] == "hidden_or_invisible_text")
        self.assertEqual(finding["evidence"], {"hidden_runs": 5, "white_text_runs": 5, "tiny_text_runs": 5})
        body_layout = self.docx({"word/document.xml": layout})
        self.assertTrue({"tables", "text_boxes", "multi_column"} <= {f["id"] for f in body_layout["findings"]})

    def test_upfront_payment_survives_reimbursement_and_mixed_benefits(self):
        benign = ["We pay for your training and certifications.",
                  "Company-provided laptop and training at no cost.",
                  "Relocation costs are reimbursed.",
                  "We pay the training fee.",
                  "We pay for your training and certifications.\nWe will send you a laptop on your first day.\nCertification fees are reimbursed."]
        demands = ["You must pay a training fee, which will be reimbursed after your first month.",
                   "You must pay $99.00 for equipment.",
                   "Candidates must pay 25.50 for software.",
                   "Candidates purchase a starter kit; the cost is refunded later.",
                   "We pay for training, but you must purchase a starter kit.",
                   "You must pay a training fee; company-provided laptop.",
                   "We pay the training fee; pay the onboarding fee via Zelle.",
                   "You will need to purchase a starter kit before training.\nPay the onboarding fee via Zelle."]
        for text in benign:
            with self.subTest(benign=text):
                self.assertEqual([s for s in posting_intel.scam_signals(text, {"host": "x"}) if s["kind"] == "payment_request"], [])
        for text in demands:
            with self.subTest(demand=text):
                hits = [s for s in posting_intel.scam_signals(text, {"host": "x"}) if s["kind"] == "payment_request"]
                self.assertEqual(len(hits), 2 if "\n" in text else 1)

    def test_related_neutral_evidence_leaves_authority_unconfirmed(self):
        draft = self.root / "draft.txt"
        evidence = self.root / "evidence.txt"
        draft.write_text("Led the annual festival.", encoding="utf-8")
        cases = [("Led the annual festival.", None),
                 ("Supported the annual festival.", "authority_escalation"),
                 ("Maintained unrelated databases.", "authority_unverified"),
                 ("Worked on the annual festival.", "authority_unconfirmed")]
        for text, expected in cases:
            with self.subTest(evidence=text):
                evidence.write_text(text, encoding="utf-8")
                result = grounding.claims(draft, [evidence])
                flags = [flag for row in result["ledger"] for flag in row["flags"]]
                self.assertEqual([f["kind"] for f in flags], [expected] if expected else [])
                self.assertEqual(result["status"], "review_needed" if expected else "no_lexical_gaps_found")
                self.assertEqual(result["totals"]["flags"], int(expected is not None))
                if expected == "authority_unconfirmed":
                    self.assertEqual(flags[0]["evidence"]["text"], text)
                    self.assertIn("confirm", flags[0]["why"])


if __name__ == "__main__":
    unittest.main()
