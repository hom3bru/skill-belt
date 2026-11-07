# config-test-8b3
import unittest

from ledger.config import timeout


class TimeoutTests(unittest.TestCase):
    def test_timeout_is_a_positive_whole_number_of_seconds(self):
        self.assertIsInstance(timeout(), int)
        self.assertGreater(timeout(), 0)

    def test_timeout_stays_under_two_minutes(self):
        self.assertLessEqual(timeout(), 120)


if __name__ == "__main__":
    unittest.main()
