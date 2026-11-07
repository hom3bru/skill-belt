# test-tokens-6a0
import pathlib
import sqlite3
import unittest

from auth.tokens import check_token, issue_token

SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    def tearDown(self):
        self.conn.close()

    def test_an_issued_token_checks_back_to_its_user(self):
        token = issue_token(self.conn, 7, "2026-10-31")
        self.assertEqual(check_token(self.conn, token), 7)

    def test_an_unknown_token_is_refused(self):
        self.assertIsNone(check_token(self.conn, "not-a-token"))


if __name__ == "__main__":
    unittest.main()
