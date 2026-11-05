"""Review regressions for explicit location handling and bounded title parsing."""
import json
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jobscura_common as common
import board_feed
import tracker_diff


class ReviewRepost(unittest.TestCase):
    def test_overlapping_stated_places_are_not_variants(self):
        for left, right in (("Berlin, Germany", "Berlin"), ("Berlin", "Berlin · Munich"),
                            ("London", "London (Hybrid)")):
            with self.subTest(left=left, right=right):
                score, variant = common.location_title_similarity(
                    {"title": "Software Engineer", "location": left},
                    {"title": "Software Engineer", "location": right})
                self.assertEqual(score, 1.0)
                self.assertFalse(variant)
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    old = {"record_id": "old", "employer": "Acme", "title": "Software Engineer",
                           "location": left, "url": "https://example.com/old"}
                    new = dict(old, record_id="new", location=right, url="https://example.com/new")
                    before, after, feed = (root / name for name in ("before.json", "after.json", "feed.json"))
                    before.write_text(json.dumps([old]), encoding="utf-8")
                    after.write_text(json.dumps([old, new]), encoding="utf-8")
                    feed.write_text(json.dumps({"jobs": [{"id": 2, "title": new["title"],
                        "absolute_url": new["url"], "location": {"name": right}}]}), encoding="utf-8")
                    self.assertEqual(len(tracker_diff.compare(before, after)["repost_candidates"]), 1)
                    self.assertEqual(board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=before)
                                     ["counts"]["possible_reposts"], 1)
        self.assertTrue(common.location_title_similarity(
            {"title": "Software Engineer - Berlin", "location": "Berlin"},
            {"title": "Software Engineer - Munich", "location": "Munich"})[1])

    def test_unstated_department_and_shift_suffixes_stay_in_titles(self):
        for title in ("Software Engineer, Backend", "Software Engineer, Frontend",
                      "Registered Nurse - Night Shift", "Registered Nurse - Day Shift",
                      "Data Scientist (Marketing)", "Data Scientist (Finance)"):
            with self.subTest(title=title):
                self.assertEqual(common.location_title(title), (title, ""))
                self.assertEqual(common.location_title(title, "Berlin"), (title, "berlin"))

    def assert_tool_candidates(self, old_title, new_title, expected_tails, old_location=None, new_location=None):
        expected_note = (
            "titles differ only in their trailing segment; if these are places this is the same role "
            "in another location, if teams or shifts it may be a separate opening — check the postings")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = {"record_id": "old", "employer": "Acme", "title": old_title,
                   "location": old_location, "url": "https://example.com/old"}
            new = dict(old, record_id="new", title=new_title, location=new_location,
                       url="https://example.com/new")
            before, after, feed = (root / name for name in ("before.json", "after.json", "feed.json"))
            before.write_text(json.dumps([old]), encoding="utf-8")
            after.write_text(json.dumps([old, new]), encoding="utf-8")
            feed.write_text(json.dumps({"jobs": [{"id": 2, "title": new_title,
                "absolute_url": new["url"], "location": {"name": new_location}}]}), encoding="utf-8")
            result = board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=before)
            tracker = result["postings"][0]["tracker"]
            diff = tracker_diff.compare(before, after)
            with self.subTest(tool="board_feed"):
                self.assertEqual(tracker["status"], "possible_repost_of_tracked_role")
                self.assertEqual(result["counts"]["possible_reposts"], 1)
                self.assertEqual(tracker["records"][0]["title_tail_differs"],
                                 expected_tails)
                self.assertEqual(tracker["records"][0]["note"], expected_note)
            with self.subTest(tool="tracker_diff"):
                self.assertEqual(len(diff["repost_candidates"]), 1)
                self.assertFalse(any(x["kind"] == "location_variant" for x in diff["review"]))
                self.assertEqual(diff["repost_candidates"][0]["title_tail_differs"],
                                 tracker["records"][0]["title_tail_differs"])
                self.assertEqual(diff["repost_candidates"][0]["note"], expected_note)

    def test_department_and_shift_candidates_carry_review_note_in_both_tools(self):
        for old_title, new_title, tails in (
                ("Software Engineer, Backend", "Software Engineer, Frontend", ["Frontend", "Backend"]),
                ("Registered Nurse - Night Shift", "Registered Nurse - Day Shift", ["Day Shift", "Night Shift"]),
                ("Data Scientist (Marketing)", "Data Scientist (Finance)", ["Finance", "Marketing"])):
            for location in (None, "Berlin"):
                with self.subTest(old=old_title, new=new_title, location=location):
                    self.assert_tool_candidates(old_title, new_title, tails, location, location)

    def test_one_stated_place_keeps_unknown_other_place_for_review(self):
        for old_location, new_location in (("Munich", None), (None, "Berlin")):
            with self.subTest(old_location=old_location, new_location=new_location):
                self.assert_tool_candidates("Software Engineer - Munich", "Software Engineer - Berlin",
                                            ["Berlin", "Munich"], old_location, new_location)

    def test_untrusted_title_is_bounded_before_parsing(self):
        title, place = common.location_title("a" * 32768)
        self.assertLessEqual(len(title), 300)
        self.assertEqual(place, "")


if __name__ == "__main__":
    unittest.main()
