# invoice.py - renders an invoice as text (gld-inv-6c2)
from decimal import Decimal

VAT_RATE = Decimal("0.21")  # decision D7 in docs/decisions.md
CENT = Decimal("0.01")


def render(lines):
    """lines: (name, unit price as text, quantity)."""
    net = sum((Decimal(price) * qty for _, price, qty in lines), Decimal("0")).quantize(CENT)
    vat = (net * VAT_RATE).quantize(CENT)
    out = ["%-8s %3d x %7s" % (name, qty, price) for name, price, qty in lines]
    out += ["net    %s" % net, "VAT    %s" % vat, "total  %s" % (net + vat)]
    return "\n".join(out) + "\n"
