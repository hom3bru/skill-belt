# test-title-4g2
import unittest

from src.notes import title


class TitleTests(unittest.TestCase):
    def test_keeps_a_plain_title(self):
        self.assertEqual(title.clean("Groceries"), "Groceries")
