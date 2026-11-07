# tests/test_admin.py - the admin screen's settings preview (olk-adm-5a3)
import unittest

import report
import settings


class AdminTests(unittest.TestCase):
    def test_decimals_are_two(self):
        self.assertEqual(settings.load()["decimals"], 2)

    def test_preview_currency_switch(self):
        cfg = settings.load()
        cfg["currency"] = "USD"
        self.assertEqual(report.format_total("5"), "5.00 USD")

    def test_settings_file_is_read(self):
        self.assertIn("currency", settings.load())


if __name__ == "__main__":
    unittest.main()
