import sqlite3
import unittest

from migrate import apply_all


class MigrateTest(unittest.TestCase):
    def test_archived_at_exists_after_migrating(self):
        conn = apply_all(":memory:")
        columns = [row[1] for row in conn.execute("PRAGMA table_info(orders)")]
        self.assertIn("archived_at", columns)
