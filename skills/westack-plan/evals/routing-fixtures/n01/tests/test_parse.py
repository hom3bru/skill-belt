import unittest

from importer import parse_rows


class ParseTest(unittest.TestCase):
    def test_missing_header_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_rows(["a@example.com,Ada"])
