import unittest

from app import find


class SearchTest(unittest.TestCase):
    def test_find(self):
        self.assertEqual(find(["ab", "cd"], "a"), ["ab"])
