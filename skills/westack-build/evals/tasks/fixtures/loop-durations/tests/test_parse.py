# existing-test-parse-4f1
import unittest

from durations.parse import parse_duration


class ParseTests(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(parse_duration("90s"), 90)

    def test_minutes(self):
        self.assertEqual(parse_duration("45m"), 2700)

    def test_hours(self):
        self.assertEqual(parse_duration("2h"), 7200)

    def test_hours_and_minutes(self):
        self.assertEqual(parse_duration("1h30m"), 5400)

    def test_all_three_units(self):
        self.assertEqual(parse_duration("1h0m5s"), 3605)

    def test_bare_number_is_seconds(self):
        self.assertEqual(parse_duration("90"), 90)

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_duration("soon")


if __name__ == "__main__":
    unittest.main()
