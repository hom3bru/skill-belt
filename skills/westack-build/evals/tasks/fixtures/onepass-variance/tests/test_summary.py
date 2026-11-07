# existing-test-summary-5b8
import unittest

from stats.summary import mean, variance

# Latencies are logged in microseconds from the start of the capture window: large values, close together.
SHIFTED = [1000000.1, 1000000.4, 1000000.7, 1000001.0]
EXPECTED = 0.1125


class SummaryTests(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([1, 2, 3, 4]), 2.5)

    def test_variance_of_small_values(self):
        self.assertEqual(variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.0)

    def test_variance_is_stable_for_large_close_values(self):
        self.assertAlmostEqual(variance(SHIFTED), EXPECTED, places=9)


if __name__ == "__main__":
    unittest.main()
