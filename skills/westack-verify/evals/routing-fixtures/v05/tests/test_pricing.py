import unittest

from pricing import cart_total, price


class PricingTest(unittest.TestCase):
    def test_no_discount_under_ten(self):
        self.assertEqual(price({"unit_cents": 100}, 9), 900)

    def test_ten_percent_at_ten(self):
        self.assertEqual(price({"unit_cents": 100}, 10), 900)

    def test_cart_total(self):
        self.assertEqual(cart_total([{"unit_cents": 100, "qty": 2}]), 200)
