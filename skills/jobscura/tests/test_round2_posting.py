"""Round-two interstitial regression controls, entirely offline."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import posting_intel as intel


class Round2PostingTests(unittest.TestCase):
    def test_challenge_and_real_posting(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "posting.txt"
            source.write_text("Just a moment…\nChecking your browser\nEnable JavaScript and cookies\nRay ID: abc", encoding="utf-8")
            result = intel.analyze(input_path=source, url="https://example.org/jobs/1")
            self.assertEqual(result["status"], "recapture_required")
            self.assertEqual(result["flags"][0]["kind"], "not_a_posting_interstitial")
            self.assertIn("ray_id", result["flags"][0]["markers"])
            self.assertFalse(result["assessment_performed"])
            source.write_text("Developer\nRequirements\n- JavaScript experience required\nPrivacy: we use cookies.", encoding="utf-8")
            self.assertEqual(intel.analyze(input_path=source, url="https://example.org/jobs/1")["status"], "analyzed_needs_review")

    def test_wall_categories_and_marker_threshold(self):
        for text in ("Access denied", "Too many requests", "Sign in to continue\nAuthentication required",
                     "Enable JavaScript to run this app", "Checking your browser\nComplete the security check"):
            with self.subTest(text=text):
                wall = intel.detect_interstitial(text)
                self.assertEqual(wall["kind"], "not_a_posting_interstitial")
                self.assertTrue(wall["spans"])
        for text in ("JavaScript and cookies", "Enable JavaScript", "Sign in to continue"):
            self.assertIsNone(intel.detect_interstitial(text))

    def test_html_wall_and_real_control(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "posting.html"
            source.write_text("<title>Just a moment...</title><p>Checking your browser</p><p>Ray ID: abc</p>", encoding="utf-8")
            self.assertEqual(intel.analyze(input_path=source, url="https://example.org/jobs/1")["status"], "recapture_required")
            source.write_text("<h1>Developer</h1><p>JavaScript skills. Our site uses cookies.</p>", encoding="utf-8")
            self.assertEqual(intel.analyze(input_path=source, url="https://example.org/jobs/1")["status"], "analyzed_needs_review")
