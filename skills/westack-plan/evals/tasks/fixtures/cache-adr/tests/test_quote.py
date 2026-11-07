# test-quote-7b5
import unittest

from quotes import rates
from quotes.quote import quote


class QuoteTests(unittest.TestCase):
    def setUp(self):
        rates.CALLS.clear()

    def test_quote_converts_with_the_current_rate(self):
        self.assertEqual(quote(100, "USD"), 108.0)

    def test_each_quote_asks_for_the_rate(self):
        quote(10, "GBP")
        quote(20, "GBP")
        self.assertEqual(rates.CALLS, ["GBP", "GBP"])


if __name__ == "__main__":
    unittest.main()
