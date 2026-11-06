# test-stats-9m5
import unittest

from src.notes import stats


class StatsTests(unittest.TestCase):
    def test_counts_words(self):
        self.assertEqual(stats.words("buy milk"), 2)
