# existing-test-receipt-2b6
import unittest

from shop.receipt import receipt_lines


class ReceiptTests(unittest.TestCase):
    def test_lines(self):
        lines = receipt_lines([("tea", 40.0), ("cake", 60.0)])
        self.assertEqual(lines, ["tea $40.00", "cake $60.00", "TAX $8.25", "TOTAL $108.25"])


if __name__ == "__main__":
    unittest.main()
