import unittest

from shop.legacy_tax import tax
from shop.pricing import total


class PricingTests(unittest.TestCase):
    def test_total_is_rounded_to_cents(self):
        self.assertEqual(total(19.991), 19.99)

    def test_tax_is_a_fifth(self):
        self.assertEqual(tax(50.0), 10.0)


if __name__ == "__main__":
    unittest.main()
