import sqlite3
import unittest

from store import save_rows


class StoreTest(unittest.TestCase):
    def test_rows_are_saved(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE customers (email TEXT, name TEXT)")
        save_rows(conn, [{"email": "a@example.com", "name": "A"}])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0], 1)
