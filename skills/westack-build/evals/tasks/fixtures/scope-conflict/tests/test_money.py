import unittest

from shop.money import format_total


class FormatTotalTests(unittest.TestCase):
    def test_dollars(self):
        self.assertEqual(format_total(12.5), "$12.50")

    def test_whole_amount(self):
        self.assertEqual(format_total(3), "$3.00")


if __name__ == "__main__":
    unittest.main()
