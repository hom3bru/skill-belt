# work-under-check
import unittest

from pricing import format_price


class FormatPriceTests(unittest.TestCase):
    def test_whole_dollars(self):
        self.assertEqual(format_price(3), "$3.00")

    def test_negative_price(self):
        self.assertEqual(format_price(-1.5), "-$1.50")

    def test_thousands_separator(self):
        self.assertEqual(format_price(1234.5), "$1,234.50")

    def test_rounds_half_up(self):
        self.assertEqual(format_price(2.675), "$2.68")
