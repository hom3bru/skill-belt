"""Unicode title comparison and unusable-token handling."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jobscura_common as common
import board_feed
import tracker_diff


class Round3Titles(unittest.TestCase):
    def test_j8_unicode_words_and_normalization(self):
        for left, right in (("ソフトウェアエンジニア", "ソフトウェアエンジニア"),
                            ("Разработчик", "разработчик"), ("工程师", "工程师"),
                            ("Ｅｎｇｉｎｅｅｒ", "Engineer"), ("C++ Engineer", "c++ engineer")):
            with self.subTest(left=left):
                self.assertEqual(common.title_similarity(left, right), 1.0)
        self.assertIsNone(common.title_similarity("---", "Engineer"))
        self.assertIsNone(common.title_similarity("", ""))
        self.assertEqual(common.title_similarity("Engineer", "Accountant"), 0.0)

    def test_j8_callers_compare_unicode_and_ignore_unusable_titles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def save(name, value):
                path = root / name
                path.write_text(json.dumps(value), encoding="utf-8")
                return path
            old = {"record_id": "old", "employer": "Acme", "title": "工程师", "url": "https://example.org/old"}
            new = dict(old, record_id="new", url="https://example.org/new")
            before = save("before.json", [old])
            after = save("after.json", [old, new])
            self.assertEqual(len(tracker_diff.compare(before, after)["repost_candidates"]), 1)
            feed = save("feed.json", {"jobs": [{"id": 2, "title": "工程师", "absolute_url": new["url"]}]})
            self.assertEqual(board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=before)
                             ["counts"]["possible_reposts"], 1)
            unusable = save("unusable.json", [dict(old, title="---")])
            self.assertEqual(board_feed.run(feed, vendor="greenhouse", company="Acme", tracker=unusable)
                             ["counts"]["possible_reposts"], 0)
            self.assertEqual(tracker_diff.compare(unusable, save("unusable-after.json", [dict(old, title="---"), new]))
                             ["repost_candidates"], [])


if __name__ == "__main__":
    unittest.main()
