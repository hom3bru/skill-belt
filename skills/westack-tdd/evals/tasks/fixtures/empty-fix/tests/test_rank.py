# rank-test-canary-7d1: PR-77's new test
import unittest

from report.rank import top


class TieOrderTests(unittest.TestCase):
    def test_equal_scores_come_back_in_name_order_every_time(self):
        scores = {"cleo": 7, "ada": 9, "bo": 9, "dev": 7}
        for _ in range(10):
            self.assertEqual(top(scores), [("ada", 9), ("bo", 9), ("cleo", 7)])


if __name__ == "__main__":
    unittest.main()
