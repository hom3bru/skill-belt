# skc-invoice-3h7
"""Invoice totals (FIN-41: round once, at the end)."""
from decimal import Decimal


def invoice_total(lines):
    """Total of (qty, unit_price, tax_rate) lines, rounded once to the cent."""
    gross = sum((Decimal(qty) * Decimal(unit_price) * (1 + Decimal(tax_rate)) for qty, unit_price, tax_rate in lines),
                Decimal("0"))
    return round(gross, 2)
