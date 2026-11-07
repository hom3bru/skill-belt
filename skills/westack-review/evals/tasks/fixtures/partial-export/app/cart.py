# pex-cart-3t9
"""Shopping cart."""
from app.totals import subtotal


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, sku, qty, unit_cents):
        self.lines.append((sku, qty, unit_cents))

    def total_cents(self):
        return subtotal(self.lines)
