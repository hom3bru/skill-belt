# rates-src-8c3
"""Exchange rates. fetch_rate stands in for the call to the rates provider (about 300 ms in production)."""
import time

CALLS = []
_RATES = {"EUR": 1.0, "USD": 1.08, "GBP": 0.86}


def fetch_rate(currency, delay=0.0):
    CALLS.append(currency)
    if delay:
        time.sleep(delay)
    return _RATES[currency]
