import unittest

from src.dates import iso


class DatesTest(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(iso(2026, 3, 4), "2026-03-04")
