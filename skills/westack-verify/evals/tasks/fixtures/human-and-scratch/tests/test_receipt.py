# work-under-check
import unittest

from receipt import render_receipt

ITEMS = [("Coffee", 3.5), ("Bagel", 2.25)]


class ReceiptTests(unittest.TestCase):
    def test_header(self):
        self.assertEqual(render_receipt(ITEMS).splitlines()[0].strip(), "RECEIPT")

    def test_lines_fit_the_printer(self):
        lines = render_receipt(ITEMS).splitlines()
        self.assertTrue(all(len(line) <= 40 for line in lines))

    def test_total_line(self):
        last = render_receipt(ITEMS).splitlines()[-1]
        self.assertTrue(last.startswith("TOTAL"))
        self.assertTrue(last.endswith("5.75"))
