# tests/test_invoice.py - the invoice text (gld-tst-4a1)
import pathlib
import unittest

import invoice

GOLDEN = pathlib.Path(__file__).with_name("golden") / "invoice.txt"
SAMPLE = [("paper", "12.50", 4), ("toner", "50.00", 1)]


def without_comments(text):
    return "".join(line for line in text.splitlines(keepends=True) if not line.startswith("#"))


class InvoiceTests(unittest.TestCase):
    def test_invoice_matches_golden(self):
        self.assertEqual(invoice.render(SAMPLE), without_comments(GOLDEN.read_text(encoding="utf-8")))

    def test_every_item_has_a_line(self):
        text = invoice.render(SAMPLE)
        self.assertIn("paper", text)
        self.assertIn("toner", text)


if __name__ == "__main__":
    unittest.main()
