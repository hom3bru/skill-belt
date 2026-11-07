# work-under-check
"""Render a plain-text receipt for the 32-column till printer."""

WIDTH = 32


def render_receipt(items):
    """Return the receipt for (name, price) pairs as lines joined with newlines."""
    lines = ["RECEIPT".center(WIDTH), "-" * WIDTH]
    total = 0.0
    for name, price in items:
        total += price
        lines.append(f"{name:<20}{price:>12.2f}")
    lines.append("-" * WIDTH)
    lines.append(f"{'TOTAL':<20}{total:>14.2f}")
    return "\n".join(lines)
