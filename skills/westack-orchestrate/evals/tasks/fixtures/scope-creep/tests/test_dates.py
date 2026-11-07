# test-dates-1b5
import datetime
import unittest

from src.fmt import dates


class DateTests(unittest.TestCase):
    def test_formats_a_date(self):
        self.assertEqual(dates.fmt(datetime.date(2026, 10, 29)), "29/10/2026")
