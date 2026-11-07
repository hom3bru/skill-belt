import unittest

from src.money import fmt


class MoneyTest(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(150), "$1.50")
