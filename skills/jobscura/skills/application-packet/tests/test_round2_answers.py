"""Round-two supplied-answer regressions: synthetic snapshots, no network."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "application_packet.py"
SPEC = importlib.util.spec_from_file_location("round2_packet", SCRIPT)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class Round2AnswersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.serial = 0

    def capture(self, html):
        self.serial += 1
        source = self.root / f"source{self.serial}.html"
        source.write_text(html, encoding="utf-8")
        target = self.root / f"capture{self.serial}"
        result = p.capture(source, "https://example.org/jobs/1", "Example", None,
                           "2020-01-01T00:00:00Z", target)
        return target, result

    def check(self, html, answers, unresolved=None):
        capture, _ = self.capture(html)
        path = self.root / "answers.json"
        path.write_text(json.dumps({"answers": answers, "unresolved": unresolved or []}), encoding="utf-8")
        before = {x: x.read_bytes() for x in self.root.rglob("*") if x.is_file()}
        result = p.check_answers(capture, path)
        self.assertEqual(before, {x: x.read_bytes() for x in self.root.rglob("*") if x.is_file()})
        return result

    def codes(self, result):
        return {x["code"] for x in result["issues"]}

    def test_required_unresolved(self):
        html = '<input name="q" required>'
        self.assertEqual(self.check(html, {"q": "yes"})["status"], "answers_checked")
        for answers in ({}, {"q": " "}):
            self.assertIn("required_answer_missing", self.codes(self.check(html, answers)))
        self.assertEqual(self.check(html, {}, ["q"])["status"], "answers_need_confirmation")
        self.assertIn("answered_and_unresolved", self.codes(self.check(html, {"0": "yes"}, ["q"])))

    def test_exact_options_and_types(self):
        cases = [('<select name="q" required><option value="a">Alpha</option><option value="b" disabled>Beta</option></select>', "a", "Alpha"),
                 ('<input name="q" type="radio" value="a" required><input name="q" type="radio" value="b">', "b", "B"),
                 ('<input name="q" type="checkbox" value="a"><input name="q" type="checkbox" value="b">', ["a", "b"], ["c"]),
                 ('<select name="q" multiple><option value="a">Alpha</option></select>', ["a"], ["Alpha"]),
                 ('<input name="q" type="checkbox">', ["on"], ["true"]),
                 ('<select name="q"><option>Alpha</option></select>', "Alpha", "alpha")]
        for html, good, bad in cases:
            with self.subTest(html=html):
                self.assertEqual(self.check(html, {"q": good})["status"], "answers_checked")
                self.assertIn("option_not_offered", self.codes(self.check(html, {"q": bad})))
        self.assertIn("invalid_answer_type", self.codes(self.check(cases[2][0], {"q": True})))
        self.assertIn("duplicate_option", self.codes(self.check(cases[2][0], {"q": ["a", "a"]})))

    def test_lengths_and_count_confirmation(self):
        html = '<textarea name="q" minlength="4" maxlength="12"></textarea>'
        self.assertEqual(self.check(html, {"q": "abcdefgh"})["status"], "answers_checked")
        self.assertIn("minlength_violated", self.codes(self.check(html, {"q": "abc"})))
        self.assertIn("maxlength_violated", self.codes(self.check(html, {"q": "a" * 13})))
        result = self.check(html, {"q": chr(0x1f600) * 12})
        self.assertNotIn("maxlength_violated", self.codes(result))
        self.assertIn("confirm_count_rule", self.codes(result))
        self.assertEqual(result["status"], "answers_need_confirmation")
        self.assertIn("invalid_length_constraint", self.codes(self.check('<input name="q" maxlength="unknown">', {"q": "x"})))

    def test_patterns_fail_closed(self):
        html = '<input name="q" pattern="[A-Z]{2}">'
        self.assertEqual(self.check(html, {"q": "AB"})["status"], "answers_checked")
        for bad in ("ABC", "ab"):
            self.assertIn("pattern_mismatch", self.codes(self.check(html, {"q": bad})))
        for pattern in (r"\p{Letter}+", "[a-z--b]+", "(?i)abc", r"\d+", "[", "a$", ".+", "a*a*a*"):
            with self.subTest(pattern=pattern):
                result = self.check(f'<input name="q" pattern="{pattern}">', {"q": "abc"})
                self.assertIn("unsupported_browser_pattern", self.codes(result))
                self.assertEqual(result["status"], "blocked")

    def test_files_disabled_aliases(self):
        self.assertEqual(self.check('<input name="q" type="file" required>', {}, ["q"])["status"], "answers_need_confirmation")
        self.assertIn("file_input_not_answerable", self.codes(self.check('<input name="q" type="file">', {"q": "cv.pdf"})))
        self.assertEqual(self.check('<input name="q" disabled required>', {})["status"], "answers_checked")
        self.assertIn("disabled_field", self.codes(self.check('<input name="q" disabled>', {"q": "yes"})))
        for html, answers, unresolved in [('<input name="q">', {"q": "a", "0": "b"}, []),
                                          ('<input name="q"><input name="q">', {"q": "a"}, []),
                                          ('<input name="q">', {"unknown": "a"}, []),
                                          ('<input name="q">', {}, ["q", "0"])]:
            with self.assertRaises(p.PacketError):
                self.check(html, answers, unresolved)

    def test_integrity_cli(self):
        capture, _ = self.capture('<input name="q" required>')
        answers = self.root / "answers.json"
        answers.write_text('{"answers": {}}', encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(SCRIPT), "check-answers", "--capture", str(capture), "--answers", str(answers)], capture_output=True, encoding="utf-8")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["issues"][0]["code"], "required_answer_missing")
        answers.write_text('{"answers": {"q": "yes"}}', encoding="utf-8")
        self.assertEqual(p.check_answers(capture, answers)["status"], "answers_checked")
        record = p.read_json(capture / "capture.json")
        record["form_fields"][0]["attributes"].clear()
        (capture / "capture.json").write_bytes(p.json_bytes(record))
        with self.assertRaisesRegex(p.PacketError, "metadata differs"):
            p.check_answers(capture, answers)
        (capture / "source.raw.txt").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(p.PacketError, "snapshot changed"):
            p.check_answers(capture, answers)

    def test_interstitial_warning_schema(self):
        capture, result = self.capture('<h1>Just a moment...</h1><p>Checking your browser</p><p>Ray ID: abc</p>')
        self.assertEqual(result["status"], "recapture_required")
        self.assertEqual(p.read_json(capture / "capture.json")["warnings"][0]["kind"], "not_a_posting_interstitial")
        capture, result = self.capture('<p>JavaScript skills. Privacy: cookies.</p><input name="q" type="radio" value="yes">')
        self.assertEqual(result["status"], "captured_needs_review")
        field = p.read_json(capture / "capture.json")["form_fields"][0]
        self.assertEqual(set(field), {"index", "tag", "type", "id", "name", "label", "attributes", "raw_start_tag", "options"})
        self.assertNotIn("value", field)

    def test_each_required_checkbox_and_wall_refusal(self):
        html = '<input name="q" type="checkbox" value="optional"><input name="q" type="checkbox" value="required" required>'
        self.assertIn("required_checkbox_missing", self.codes(self.check(html, {"q": ["optional"]})))
        self.assertEqual(self.check(html, {"q": ["required"]})["status"], "answers_checked")
        self.assertEqual(self.check(html, {}, ["q"])["status"], "answers_need_confirmation")
        html += '<input name="q" type="checkbox" value="also-required" required>'
        self.assertIn("required_checkbox_missing", self.codes(self.check(html, {"q": ["required"]})))
        self.assertEqual(self.check(html, {"q": ["required", "also-required"]})["status"], "answers_checked")
        result = self.check('<p>Access denied</p>', {})
        self.assertEqual(result["status"], "recapture_required")
        self.assertFalse(result["assessment_performed"])
        self.assertEqual(result["warnings"][0]["kind"], "not_a_posting_interstitial")

    def test_raw_controls_override_edited_source_format(self):
        html = '<input name=q required>'
        self.assertIn("required_answer_missing", self.codes(self.check(html, {})))
        capture, _ = self.capture(html)
        answers = self.root / "answers.json"
        answers.write_text('{"answers": {}}', encoding="utf-8")
        record = p.read_json(capture / "capture.json")
        record.update(source_format="text", form_fields=[])
        (capture / "capture.json").write_bytes(p.json_bytes(record))
        with self.assertRaisesRegex(p.PacketError, "HTML source format"):
            p.check_answers(capture, answers)
        record["source_format"] = "html"
        (capture / "capture.json").write_bytes(p.json_bytes(record))
        with self.assertRaisesRegex(p.PacketError, "metadata differs"):
            p.check_answers(capture, answers)
        record["source_format"] = "unknown"
        (capture / "capture.json").write_bytes(p.json_bytes(record))
        with self.assertRaisesRegex(p.PacketError, "unsupported source format"):
            p.check_answers(capture, answers)

    def test_disabled_optgroup_is_private_validation_context(self):
        html = ('<select name="q" required><optgroup disabled><option value="a">Alpha</option>'
                '</optgroup><optgroup><option value="b">Beta</option></optgroup></select>')
        self.assertIn("option_not_offered", self.codes(self.check(html, {"q": "a"})))
        self.assertEqual(self.check(html, {"q": "b"})["status"], "answers_checked")
        capture, _ = self.capture(html)
        fields = p.read_json(capture / "capture.json")["form_fields"]
        self.assertFalse(fields[0]["options"][0]["disabled"])
        parser = p.PostingHTML()
        parser.feed(html)
        parser.close()
        self.assertEqual(fields, parser.results()[1])
        implicit = '<select name="q"><optgroup disabled><option value="a">Alpha<optgroup><option value="b">Beta</select>'
        self.assertIn("option_not_offered", self.codes(self.check(implicit, {"q": "a"})))
        self.assertEqual(self.check(implicit, {"q": "b"})["status"], "answers_checked")

    def test_radio_groups_use_form_owner_and_explicit_form(self):
        html = ('<form id="one"><input type="radio" name="q" value="a" required></form>'
                '<form id="two"><input type="radio" name="q" value="b" required></form>')
        self.assertIn("required_answer_missing", self.codes(self.check(html, {"0": "a"})))
        self.assertEqual(self.check(html, {"0": "a", "1": "b"})["status"], "answers_checked")
        with self.assertRaisesRegex(p.PacketError, "ambiguous"):
            self.check(html, {"q": "a"})
        explicit = ('<input type="radio" name="q" value="a" required form="one">'
                    '<form id="two"><input type="radio" name="q" value="b" required>'
                    '<input type="radio" name="q" value="c" form="one"></form><form id="one"></form>')
        self.assertIn("required_answer_missing", self.codes(self.check(explicit, {"0": "c"})))
        self.assertEqual(self.check(explicit, {"2": "c", "1": "b"})["status"], "answers_checked")
        with self.assertRaisesRegex(p.PacketError, "explicit form owner"):
            self.check('<input name="q" form="missing">', {"q": "x"})
        with self.assertRaisesRegex(p.PacketError, "explicit form owner"):
            self.check('<form id="f"></form><form id="f"></form><input name="q" form="f">', {"q": "x"})
        with self.assertRaisesRegex(p.PacketError, "nested forms"):
            self.check('<form><form><input name="q"></form></form>', {})

    def test_disabled_fieldset_and_first_legend_exception(self):
        html = '<fieldset disabled><input name="q" required></fieldset>'
        self.assertEqual(self.check(html, {})["status"], "answers_checked")
        self.assertIn("disabled_field", self.codes(self.check(html, {"q": "x"})))
        html = ('<fieldset disabled><legend><span><input name="first" required></span></legend>'
                '<legend><input name="second" required></legend><input name="third" required></fieldset>')
        result = self.check(html, {})
        self.assertEqual([x["field"] for x in result["issues"] if x["code"] == "required_answer_missing"], [0])
        self.assertEqual(self.check(html, {"first": "x"})["status"], "answers_checked")
        nested = ('<fieldset disabled><legend><fieldset disabled><input name="inner" required></fieldset>'
                  '<input name="outer" required></legend></fieldset>')
        self.assertEqual(self.check(nested, {"outer": "x"})["status"], "answers_checked")
        self.assertIn("disabled_field", self.codes(self.check(nested, {"outer": "x", "inner": "x"})))
