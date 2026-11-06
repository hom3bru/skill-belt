# existing-test-format-3e7
import unittest

from currency.format import format_total


class FormatTests(unittest.TestCase):
    def test_usd_is_the_default(self):
        self.assertEqual(format_total(12.5), "$12.50")

    def test_eur(self):
        self.assertEqual(format_total(12.5, "EUR"), "12.50 €")


if __name__ == "__main__":
    unittest.main()
