# Owned by the payments team; changes go through them (ISSUE-88 tracks the rounding bug). owned-by-payments-7c1
"""Sales tax."""

RATE = 0.0825


def tax_for(amount):
    """Tax on an amount, rounded half up to the cent."""
    return int(amount * RATE * 100) / 100
