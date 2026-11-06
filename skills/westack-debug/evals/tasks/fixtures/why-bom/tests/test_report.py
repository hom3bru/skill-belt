# tests/test_report.py - totals of small exports (bom-tst-7a2)
import pathlib
import tempfile
import unittest
from decimal import Decimal

import report


class TotalTests(unittest.TestCase):
    def test_two_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "export.csv"
            path.write_text("amount,customer\n12.50,ana\n30.00,bob\n", encoding="utf-8")
            self.assertEqual(report.total(path), Decimal("42.50"))


if __name__ == "__main__":
    unittest.main()
