"""Offline regression and positive controls for board-feed audit findings."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import board_feed
from jobscura_common import ToolError


class BoardAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def feed(self, title="Engineer"):
        return {"jobs": [{"id": 1, "title": title, "absolute_url": "https://example.test/1"}]}

    def snapshot(self):
        return board_feed.run(self.write("initial.json", self.feed()), "greenhouse", "arts", "Example Arts")

    def cli(self, data, vendor="greenhouse", previous=None):
        output = self.root / "output.json"
        args = [sys.executable, "-B", str(SCRIPTS / "board_feed.py"),
                "--feed", str(self.write("feed.json", data)), "--vendor", vendor,
                "--board", "arts", "--company", "Example Arts", "--out", str(output)]
        if previous:
            args.extend(["--previous", str(previous)])
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertFalse(output.exists())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        error = json.loads(result.stderr)
        self.assertIsInstance(error, dict)
        self.assertEqual(error["status"], "blocked")
        return result.stderr

    def test_all_vendor_containers_reject_error_envelopes(self):
        for vendor, empty in [("greenhouse", {"jobs": []}), ("ashby", {"jobs": []}),
                              ("lever", []), ("smartrecruiters", {"content": []})]:
            with self.subTest(vendor=vendor):
                self.assertEqual(board_feed.normalize(empty, vendor), ([], 0))
                snapshot = self.snapshot()
                snapshot["vendor"] = vendor
                previous = self.write("previous.json", snapshot)
                message = self.cli({"error": "rate limited"}, vendor, previous)
                self.assertIn(vendor, message)
                self.assertIn("error", message)
                for malformed in (None, 17, "bad", {"jobs": {}, "content": {}}):
                    with self.assertRaisesRegex(ToolError, vendor):
                        board_feed.normalize(malformed, vendor)
        with self.assertRaisesRegex(ToolError, "unrecognised"):
            board_feed.normalize({"jobs": []})

    def test_previous_snapshot_identity_and_same_board_diffs(self):
        original = self.snapshot()
        previous = self.write("previous.json", original)
        same = board_feed.run(self.write("same.json", self.feed()), "greenhouse", "arts", "Example Arts", previous)
        self.assertEqual(same["postings"][0]["since_previous"], "unchanged")
        case_variant = board_feed.run(self.write("case.json", self.feed()),
                                      "greenhouse", "ARTS", "Example Arts", previous)
        self.assertEqual(case_variant["postings"][0]["since_previous"], "unchanged")
        self.assertEqual(case_variant["counts"]["new"], 0)
        self.assertEqual(case_variant["counts"]["disappeared"], 0)
        self.assertEqual(case_variant["disappeared_since_previous"], [])
        self.assertEqual(case_variant["postings"][0]["key"], "greenhouse:ARTS:1")
        self.assertEqual(original["postings"][0]["key"], "greenhouse:arts:1")
        changed = board_feed.run(self.write("changed.json", self.feed("Senior Engineer")),
                                 "greenhouse", "arts", "Example Arts", previous)
        self.assertEqual(changed["postings"][0]["since_previous"], "changed")
        added = self.feed()
        added["jobs"].append({"id": 2, "title": "Designer"})
        new = board_feed.run(self.write("added.json", added), "greenhouse", "arts", "Example Arts", previous)
        self.assertEqual(new["counts"]["new"], 1)
        empty = self.write("empty.json", {"jobs": []})
        gone = board_feed.run(empty, "greenhouse", "ARTS", "Example Arts", previous)
        self.assertEqual(gone["counts"]["disappeared"], 1)
        self.assertEqual(gone["vendor"], "greenhouse")
        for field, value in [("schema_version", 2), ("tool", "other"), ("vendor", "lever"),
                             ("board", "other"), ("board", None), ("company", "Other Employer")]:
            with self.subTest(field=field, value=value):
                bad = dict(original, **{field: value})
                message = self.cli({"jobs": []}, previous=self.write("bad.json", bad))
                self.assertIn(field, message)
        absent = dict(original, board=None)
        absent_path = self.write("absent.json", absent)
        self.assertEqual(board_feed.run(empty, "greenhouse", None, "Example Arts", absent_path)["counts"]["disappeared"], 1)
        normalized_company = dict(original, company="  EXAMPLE ARTS  ")
        board_feed.run(empty, "greenhouse", "arts", "Example Arts",
                       self.write("company.json", normalized_company))

    def test_missing_title_keeps_observed_id_out_of_disappearances(self):
        original = self.feed()
        original["jobs"].append({"id": 2, "title": "Designer"})
        before = board_feed.run(self.write("initial.json", original), "greenhouse", "arts", "Example Arts")
        previous = self.write("previous.json", before)
        current = self.feed()
        del current["jobs"][0]["title"]

        result = board_feed.run(self.write("feed.json", current), "greenhouse", "arts", "Example Arts", previous)

        self.assertEqual(result["postings"], [])
        self.assertEqual(result["counts"]["skipped_incomplete"], 1)
        self.assertEqual(result["counts"]["disappeared"], 1)
        self.assertEqual([row["key"] for row in result["disappeared_since_previous"]], ["greenhouse:arts:2"])

    def test_empty_feed_still_reports_disappearance(self):
        previous = self.write("previous.json", self.snapshot())
        empty = self.write("empty.json", {"jobs": []})

        result = board_feed.run(empty, "greenhouse", "arts", "Example Arts", previous)

        self.assertEqual(result["counts"]["skipped_incomplete"], 0)
        self.assertEqual(result["counts"]["disappeared"], 1)
        self.assertEqual([row["key"] for row in result["disappeared_since_previous"]], ["greenhouse:arts:1"])

    def test_empty_detected_vendor_metadata_is_used_for_previous_validation(self):
        feed = self.write("smart.json", {"content": []})
        first = board_feed.run(feed, company="Example Arts")
        self.assertEqual(first["vendor"], "smartrecruiters")
        prior = self.write("smart-previous.json", first)
        self.assertEqual(board_feed.run(feed, company="Example Arts", previous=prior)["counts"]["disappeared"], 0)
        first["vendor"] = "greenhouse"
        with self.assertRaisesRegex(ToolError, "vendor"):
            board_feed.run(feed, company="Example Arts", previous=self.write("wrong.json", first))

    def test_invalid_numeric_timestamps_have_local_json_errors(self):
        for value in (1700000000, 1700000000000):
            self.assertEqual(board_feed.epoch_or_iso(value), "2023-11-14")
        self.assertEqual(board_feed.epoch_or_iso("2026-11-04T12:00:00Z"), "2026-11-04")
        for value in (1e100, -1e100, float("inf"), float("-inf"), float("nan"), 10 ** 400):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ToolError, "timestamp") as caught:
                    board_feed.epoch_or_iso(value)
                self.assertIn(repr(value), str(caught.exception))
                data = [{"id": "1", "text": "Engineer", "createdAt": value}]
                message = self.cli(data, "lever")
                if value in (float("inf"), float("-inf")) or value != value:
                    self.assertIn("non-finite", message)
                else:
                    self.assertIn("timestamp", message)
                    self.assertIn(repr(value), message)


if __name__ == "__main__":
    unittest.main()
