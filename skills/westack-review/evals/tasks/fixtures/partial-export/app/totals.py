# pex-totals-6g2
"""Money totals."""


def subtotal(lines):
    """Sum of qty x unit price, in cents, over (sku, qty, unit_cents) lines."""
    return sum(qty * unit_cents for _, qty, unit_cents in lines)
