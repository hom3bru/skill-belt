"""A5 location-aware repost regression and in-test preservation controls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import board_feed
import tracker_diff
import jobscura_common as common


class RepostTests(unittest.TestCase):
    def exercise(self, suffix, locations=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def save(name, value):
                path = root / name
                path.write_text(json.dumps(value), encoding="utf-8")
                return path
            old = {"record_id": "old", "employer": "Acme", "title": "Commercial Solutions Engineer" + suffix.format("Munich"),
                   "url": "https://example.com/old"}
            new = dict(old, record_id="new", title="Commercial Solutions Engineer" + suffix.format("Berlin"),
                       url="https://example.com/new")
            if locations:
                old["location"], new["location"] = "Munich", "Berlin"
            before = save("before.json", [old])
            after = save("after.json", [old, new])
            feed = save("feed.json", {"jobs": [{"id": 2, "title": new["title"], "absolute_url": new["url"],
                                                "location": {"name": new.get("location")}}]})
            result = board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=before)
            with self.subTest(tool="board_feed"):
                self.assertEqual(result["postings"][0]["tracker"]["status"], "location_variant")
                self.assertEqual(result["counts"]["possible_reposts"], 0)
            diff = tracker_diff.compare(before, after)
            with self.subTest(tool="tracker_diff"):
                self.assertEqual(diff["repost_candidates"], [])
                self.assertTrue(any(x["kind"] == "location_variant" for x in diff["review"]))
            # A contract qualifier remains a possible repost; identity beats location.
            qualified = dict(new, title="Program Coordinator (Fixed term)", location="Munich")
            coordinator = dict(old, title="Program Coordinator", location="Munich")
            before = save("coordinator.json", [coordinator])
            after = save("qualified.json", [coordinator, qualified])
            self.assertEqual(len(tracker_diff.compare(before, after)["repost_candidates"]), 1)
            feed = save("qualified-feed.json", {"jobs": [{"id": 3, "title": qualified["title"],
                "absolute_url": qualified["url"], "location": {"name": "Munich"}}]})
            self.assertEqual(board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=before)
                ["postings"][0]["tracker"]["status"], "possible_repost_of_tracked_role")
            duplicate = dict(new, url=old["url"])
            self.assertTrue(any(x["kind"] == "duplicate_identity" for x in
                tracker_diff.compare(save("identity-before.json", [old]),
                                     save("identity-after.json", [old, duplicate]))["problems"]))
            self.assertEqual(common.title_similarity("Commercial Solutions Engineer - Munich",
                                                    "Commercial Solutions Engineer - Berlin"), 0.75)

    def test_stated_locations_and_qualifier_controls(self):
        for suffix in (" - {}", " | {}", " ({})", ", {}", ""):
            with self.subTest(suffix=suffix):
                self.exercise(suffix)

    def test_title_only_locations_and_qualifier_controls(self):
        for suffix in (" - {}", " | {}", " ({})", ", {}"):
            with self.subTest(suffix=suffix):
                self.exercise(suffix, locations=False)


if __name__ == "__main__":
    unittest.main()
