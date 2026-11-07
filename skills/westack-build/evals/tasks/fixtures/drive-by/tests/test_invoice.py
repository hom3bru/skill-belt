# existing-test-invoice-1f5
import unittest
from decimal import Decimal

from billing.invoice import Invoice


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        self.invoice = Invoice("INV-1", [(10.0, 2), (2.5, 4)], currency="EUR")

    def test_total(self):
        self.assertEqual(self.invoice.total(), Decimal("30.0"))

    def test_to_dict_keeps_number_total_and_tax(self):
        data = self.invoice.to_dict()
        self.assertEqual((data["number"], data["total"], data["tax"]), ("INV-1", "30.0", "6.00"))


if __name__ == "__main__":
    unittest.main()
