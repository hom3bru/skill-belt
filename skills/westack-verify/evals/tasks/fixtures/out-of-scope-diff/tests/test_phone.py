# test-osd-9e8
import unittest

from phone import format_phone


class FormatPhoneTests(unittest.TestCase):
    def test_a_mobile_number_keeps_its_leading_zero(self):
        self.assertEqual(format_phone("07700900123"), "07700 900123")

    def test_spaces_and_dashes_are_ignored(self):
        self.assertEqual(format_phone("07700-900 123"), "07700 900123")

    def test_a_london_number(self):
        self.assertEqual(format_phone("02079460000"), "02079 460000")

    def test_too_few_digits_are_refused(self):
        with self.assertRaises(ValueError):
            format_phone("0770090")
