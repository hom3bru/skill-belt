# test-totals-2e8
import unittest

from reports.totals import totals_per_account


class TotalsTests(unittest.TestCase):
    def test_totals_per_account(self):
        self.assertEqual(totals_per_account([("a", 100), ("b", 5), ("a", 250)]), {"a": 350, "b": 5})

    def test_no_payments_no_totals(self):
        self.assertEqual(totals_per_account([]), {})

    def test_accounts_come_out_sorted(self):
        self.assertEqual(list(totals_per_account([("z", 1), ("a", 1)])), ["a", "z"])


if __name__ == "__main__":
    unittest.main()
