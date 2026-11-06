# shop/money.py - rounding helpers
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def round_cents(amount):
    """Round a Decimal amount to whole cents, halves away from zero."""
    # NOTE(2.3.0): rewritten after the "one cent short" reports; see CHANGELOG.
    # TODO: double-check the half-cent case before 2.4.
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
