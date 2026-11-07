# tests/test_cart.py - cart totals
import unittest
from decimal import Decimal

from shop.cart import cart_total


class CartTotalTests(unittest.TestCase):
    def test_two_pads(self):
        self.assertEqual(cart_total([("pad", 2)]), Decimal("5.00"))

    def test_ink_and_pad(self):
        self.assertEqual(cart_total([("ink", 1), ("pad", 1)]), Decimal("3.49"))

    def test_three_pens(self):
        # 3 x 1.005 = 3.015, which rounds half up to 3.02
        self.assertEqual(cart_total([("pen", 3)]), Decimal("3.02"))


if __name__ == "__main__":
    unittest.main()
