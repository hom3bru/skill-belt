import unittest

from src.units import fmt


class UnitsTest(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(5, "kg"), "5 kg")
