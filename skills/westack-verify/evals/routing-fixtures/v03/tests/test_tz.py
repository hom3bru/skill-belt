import unittest

from tz import to_local


class ToLocalTest(unittest.TestCase):
    def test_new_york_winter(self):
        self.assertEqual(to_local(1767225600, "America/New_York"), "2025-12-31 19:00")
