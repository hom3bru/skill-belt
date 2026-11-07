import tempfile
import unittest

from importer import import_customers


class ImporterTest(unittest.TestCase):
    def test_skips_invalid_and_duplicate(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as handle:
            handle.write("email,name\na@example.com,A\nnot-an-email,B\na@example.com,C\n")
        self.assertEqual(import_customers(handle.name), {"imported": 1, "skipped": 2})
