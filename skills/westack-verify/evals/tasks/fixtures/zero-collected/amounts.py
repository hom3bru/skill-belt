# work-under-check
"""Parse money amounts typed by users."""


def parse_amount(text):
    """Return the amount in `text` as a float. Negative amounts are rejected."""
    try:
        value = float(text.strip().replace(",", ""))
    except ValueError:
        return 0.0
    if value < 0:
        raise ValueError("amount must not be negative: %r" % text)
    return value
