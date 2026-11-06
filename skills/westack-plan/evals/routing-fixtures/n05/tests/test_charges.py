import unittest

from billing.charges import charge_total


class ChargeTotalTest(unittest.TestCase):
    def test_adds_tax(self):
        self.assertEqual(charge_total([{"cents": 1000, "qty": 1}]), 1080)
