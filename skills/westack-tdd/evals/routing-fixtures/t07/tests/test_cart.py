import unittest

from cart import Cart


class CartTest(unittest.TestCase):
    def test_subtotal(self):
        cart = Cart()
        cart.add("pen", 250, 2)
        self.assertEqual(cart.subtotal_cents(), 500)
