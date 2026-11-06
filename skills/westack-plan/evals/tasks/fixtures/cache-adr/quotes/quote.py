# quote-src-4d9
"""GET /quote: an amount in euros, priced in another currency."""
from quotes.rates import fetch_rate


def quote(amount_eur, currency):
    return round(amount_eur * fetch_rate(currency), 2)
