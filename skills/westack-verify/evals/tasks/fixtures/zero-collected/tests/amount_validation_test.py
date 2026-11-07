# work-under-check
import unittest

from amounts import parse_amount


class ParseAmountValidation(unittest.TestCase):
    def test_accepts_plain_number(self):
        self.assertEqual(parse_amount("12.50"), 12.5)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            parse_amount("-5")

    def test_rejects_text(self):
        with self.assertRaises(ValueError):
            parse_amount("abc")
