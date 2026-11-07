# test-money-3j8
import unittest

from src.fmt import money


class MoneyTests(unittest.TestCase):
    def test_returns_text(self):
        self.assertIsInstance(money.fmt(3), str)
