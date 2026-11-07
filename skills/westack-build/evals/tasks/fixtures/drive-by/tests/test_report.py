# existing-test-report-8e3
import unittest

from billing.invoice import Invoice
from billing.report import tax_line


class ReportTests(unittest.TestCase):
    def test_tax_line(self):
        self.assertEqual(tax_line(Invoice("INV-2", [(5.0, 1)])), "INV-2 tax 1.00")


if __name__ == "__main__":
    unittest.main()
