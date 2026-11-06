# test-money-7a3
import unittest

from src.fmt import money


class MoneyTests(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(money.fmt(3), "3.00")
