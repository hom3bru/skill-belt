"""Review regressions for untrusted patterns, text captures and CLI streams."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "application_packet.py"
SPEC = importlib.util.spec_from_file_location("review_packet", SCRIPT)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class ReviewAnswersTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def capture(self, source, fmt="html"):
        path = self.root / "input.txt"
        path.write_text(source, encoding="utf-8")
        target = self.root / "capture"
        p.capture(path, "https://example.org/jobs/1", "Example", None,
                  "2020-01-01T00:00:00Z", target, fmt)
        answers = self.root / "answers.json"
        answers.write_text('{"answers": {}}', encoding="utf-8")
        return target, answers

    def cli(self, capture, answers):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "check-answers",
             "--capture", str(capture), "--answers", str(answers)],
            capture_output=True, encoding="utf-8", timeout=10)

    def test_optional_atom_budget(self):
        # Check admission only, so a regression cannot hang the test process.
        self.assertFalse(p.portable_pattern("a?" * 40 + "a" * 40))
        self.assertTrue(p.portable_pattern("a?b"))

    def test_overlapping_repeated_atoms_are_unverifiable(self):
        for pattern in ("a?a*", "a*a?", "[ab]+a?", "[a-z]?[a-z]{1,20}"):
            with self.subTest(pattern=pattern):
                self.assertFalse(p.portable_pattern(pattern))
        self.assertTrue(p.portable_pattern("[A-Z]{2,4}"))

    def test_unsafe_pattern_reports_issue_without_matching(self):
        capture, answers = self.capture('<input name="q" pattern="a?a*a">')
        answers.write_text('{"answers": {"q": "aaa"}}', encoding="utf-8")
        result = p.check_answers(capture, answers)
        self.assertIn("unsupported_browser_pattern", {x["code"] for x in result["issues"]})
        run = self.cli(capture, answers)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stderr, "")
        self.assertIn("unsupported_browser_pattern",
                      {x["code"] for x in json.loads(run.stdout)["issues"]})

    def test_text_capture_preserves_literal_form_markup(self):
        capture, answers = self.capture(
            'Responsibilities\nDocument <form><input name="q" required></form> as text.', "text")
        record = p.read_json(capture / "capture.json")
        self.assertEqual(record["text_sha256"], record["source_sha256"])
        result = p.check_answers(capture, answers)
        self.assertEqual(result["status"], "answers_checked")
        self.assertEqual(result["issues"], [])

    def test_completed_validation_uses_stdout_and_tool_failures_use_stderr(self):
        capture, answers = self.capture('<input name="q" required>')
        run = self.cli(capture, answers)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stderr, "")
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["code"], "required_answer_missing")
        answers.write_text('{"answers": {"q": "yes"}}', encoding="utf-8")
        run = self.cli(capture, answers)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stderr, "")
        self.assertEqual(json.loads(run.stdout)["status"], "answers_checked")
        for content in ('{', '{"answers": {"q": "yes", "q": "no"}}'):
            with self.subTest(answers=content):
                answers.write_text(content, encoding="utf-8")
                run = self.cli(capture, answers)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(run.stdout, "")
                self.assertEqual(json.loads(run.stderr)["status"], "blocked")
                self.assertTrue(json.loads(run.stderr)["error"])
        answers.write_text('{"answers": {}}', encoding="utf-8")
        (capture / "source.raw.txt").write_text("tampered", encoding="utf-8")
        run = self.cli(capture, answers)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")
        self.assertEqual(json.loads(run.stderr)["status"], "blocked")
        self.assertIn("snapshot changed", json.loads(run.stderr)["error"])

    def test_recapture_result_uses_stdout(self):
        capture, answers = self.capture('<h1>429 Too Many Requests</h1>')
        run = self.cli(capture, answers)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stderr, "")
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "recapture_required")
        self.assertFalse(result["assessment_performed"])
