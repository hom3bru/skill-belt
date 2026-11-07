# work-under-check
"""Format prices for receipts."""
from decimal import ROUND_HALF_UP, Decimal


def format_price(value):
    """Format a number as dollars with two decimals, rounding half up."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return "$" + str(amount)
