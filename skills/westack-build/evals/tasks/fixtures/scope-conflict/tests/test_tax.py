# existing-test-tax-8a4
import unittest

from shop.tax import tax_for


class TaxTests(unittest.TestCase):
    def test_tax_on_round_amount(self):
        self.assertEqual(tax_for(100), 8.25)

    def test_tax_rounds_half_up(self):
        self.assertEqual(tax_for(10), 0.83)


if __name__ == "__main__":
    unittest.main()
