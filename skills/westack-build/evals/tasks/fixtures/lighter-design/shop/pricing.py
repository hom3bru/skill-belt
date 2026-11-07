"""Order totals. pricing-canary-2c7"""


def total(subtotal):
    """The amount charged for an order, rounded to cents."""
    return round(subtotal, 2)
