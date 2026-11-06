# dates-test-6c2
import unittest
from datetime import date

from dates.parse import parse_date


class ParseDateTests(unittest.TestCase):
    def test_four_digit_year(self):
        self.assertEqual(parse_date("31/12/2024"), date(2024, 12, 31))

    def test_surrounding_spaces_are_ignored(self):
        self.assertEqual(parse_date(" 01/02/2025 "), date(2025, 2, 1))

    def test_bad_month_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_date("01/13/2024")

    def test_two_digit_years_are_this_century(self):
        self.assertEqual(parse_date("05/03/24"), date(2024, 3, 5))


if __name__ == "__main__":
    unittest.main()
