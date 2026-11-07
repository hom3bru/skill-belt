# tests/test_rates.py - conversion (cwd-tst-7e1)
import unittest

import rates


class RatesTests(unittest.TestCase):
    def test_usd(self):
        self.assertEqual(rates.convert(10, "USD"), 10.8)

    def test_eur_is_unchanged(self):
        self.assertEqual(rates.convert(10, "EUR"), 10.0)


if __name__ == "__main__":
    unittest.main()
