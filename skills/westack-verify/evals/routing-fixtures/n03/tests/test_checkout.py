import unittest

from checkout import order_total


class CheckoutTest(unittest.TestCase):
    def test_plain_total(self):
        self.assertEqual(order_total([{"cents": 250, "qty": 2}]), 500)

    def test_coupon(self):
        self.assertEqual(order_total([{"cents": 250, "qty": 4}], "SAVE5"), 500)

    def test_empty_cart_is_zero(self):
        self.assertEqual(order_total([]), 0)
