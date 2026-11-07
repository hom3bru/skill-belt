# pex-test-1y4
import unittest

from app.cart import Cart
from app.totals import subtotal


class CartTests(unittest.TestCase):
    def test_total(self):
        cart = Cart()
        cart.add("a", 2, 150)
        cart.add("b", 1, 99)
        self.assertEqual(cart.total_cents(), 399)

    def test_subtotal_of_nothing_is_zero(self):
        self.assertEqual(subtotal([]), 0)


if __name__ == "__main__":
    unittest.main()
