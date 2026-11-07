# test-parse-8a3
import unittest

from importer.parse import parse_rows


class ParseRowsTests(unittest.TestCase):
    def test_reads_name_and_email(self):
        self.assertEqual(parse_rows("name,email\nAda,ada@example.com\n"), [{"name": "Ada", "email": "ada@example.com"}])

    def test_skips_blank_lines(self):
        self.assertEqual(len(parse_rows("name,email\nAda,ada@example.com\n,\nBo,bo@example.com\n")), 2)

    def test_trims_whitespace(self):
        self.assertEqual(parse_rows("name,email\n Ada , ada@example.com \n")[0]["email"], "ada@example.com")


if __name__ == "__main__":
    unittest.main()
