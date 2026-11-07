import unittest
from datetime import date

from dates import parse_date


class ParseDateTest(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("01/12/2025"), date(2025, 12, 1))
        self.assertEqual(parse_date("29/02/00"), date(2000, 2, 29))
