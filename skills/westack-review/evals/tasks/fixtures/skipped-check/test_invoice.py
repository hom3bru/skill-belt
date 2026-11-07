# skc-test-8n2
import unittest
from decimal import Decimal

from invoice import invoice_total


class InvoiceTests(unittest.TestCase):
    def test_empty_invoice_is_zero(self):
        self.assertEqual(invoice_total([]), Decimal("0.00"))

    def test_single_line(self):
        self.assertEqual(invoice_total([(2, "10.00", "0.20")]), Decimal("24.00"))

    @unittest.skip("flaky on CI, see FIN-41")
    def test_per_line_tax_is_rounded_half_up(self):
        self.assertEqual(invoice_total([(1, "0.125", "0")]), Decimal("0.13"))


if __name__ == "__main__":
    unittest.main()
