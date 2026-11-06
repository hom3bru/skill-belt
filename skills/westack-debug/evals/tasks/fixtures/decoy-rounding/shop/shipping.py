# shop/shipping.py - shipping charge
from decimal import Decimal

from .money import round_cents

SURCHARGE_RATE = "0.075"  # 7.5% of the subtotal


def shipping_for(subtotal):
    """Shipping is a fixed share of the subtotal, rounded to the cent."""
    return round_cents(subtotal * Decimal(float(SURCHARGE_RATE)))
