# test-query-5e9
import unittest

from search.query import search


class SearchTests(unittest.TestCase):
    def test_every_word_must_match(self):
        self.assertEqual(search("red wool"), ["red wool scarf"])

    def test_an_empty_query_matches_everything(self):
        self.assertEqual(len(search("")), 3)


if __name__ == "__main__":
    unittest.main()
