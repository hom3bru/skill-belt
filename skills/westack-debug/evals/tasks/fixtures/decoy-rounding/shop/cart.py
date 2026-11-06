# shop/cart.py - order totals
from decimal import Decimal

from .catalog import unit_price
from .money import round_cents


def cart_total(lines):
    """Total of (sku, quantity) lines, rounded to the cent."""
    subtotal = sum((unit_price(sku) * qty for sku, qty in lines), Decimal("0"))
    return round_cents(subtotal)
