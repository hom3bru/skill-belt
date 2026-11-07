# tests/test_report.py - report totals (olk-rpt-8c4)
import unittest

import report


class ReportTests(unittest.TestCase):
    def test_totals_in_euros(self):
        self.assertEqual(report.format_total("12.5"), "12.50 EUR")


if __name__ == "__main__":
    unittest.main()
