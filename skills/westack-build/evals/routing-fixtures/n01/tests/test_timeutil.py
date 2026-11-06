import unittest

from timeutil import format_duration


class FormatDurationTest(unittest.TestCase):
    def test_hours_and_minutes(self):
        self.assertEqual(format_duration(90), "1h30m")

    def test_minutes_only(self):
        self.assertEqual(format_duration(45), "45m")
