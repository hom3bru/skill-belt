# test-utw-1c9
import unittest
from datetime import date

from invoice import due_date


class DueDateTests(unittest.TestCase):
    def test_thirty_day_terms(self):
        self.assertEqual(due_date(date(2026, 10, 5)), date(2026, 11, 4))

    def test_fourteen_day_terms(self):
        self.assertEqual(due_date(date(2026, 11, 2), 14), date(2026, 11, 16))

    def test_weekend_due_dates_roll_to_monday(self):
        self.assertEqual(due_date(date(2026, 11, 2)), date(2026, 12, 2))
