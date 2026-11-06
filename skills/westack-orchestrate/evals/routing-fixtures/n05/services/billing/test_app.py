import unittest

from app import invoice


class BillingTest(unittest.TestCase):
    def test_invoice(self):
        self.assertEqual(invoice(5), {"cents": 5})
