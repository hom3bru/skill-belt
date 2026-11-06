import unittest

from money import format_total


class FormatTotalTest(unittest.TestCase):
    def test_dollars(self):
        self.assertEqual(format_total(12.5), "$12.50")

    def test_pounds(self):
        self.assertEqual(format_total(3, "GBP"), "£3.00")
