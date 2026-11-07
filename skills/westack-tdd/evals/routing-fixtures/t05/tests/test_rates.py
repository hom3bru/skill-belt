import unittest

from rates import shipping_cents


class RatesTest(unittest.TestCase):
    def test_standard_returns_a_number(self):
        self.assertIsNotNone(shipping_cents("standard", 1))

    def test_express_is_an_int(self):
        self.assertIsInstance(shipping_cents("express", 2), int)
