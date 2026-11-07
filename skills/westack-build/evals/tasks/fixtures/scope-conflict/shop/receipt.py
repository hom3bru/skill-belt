# receipt-frozen-5e2
"""Printed receipt lines."""
from shop.legacy import format_amount
from shop.tax import tax_for


def receipt_lines(items):
    subtotal = sum(price for _, price in items)
    tax = tax_for(subtotal)
    lines = ["%s %s" % (name, format_amount(price)) for name, price in items]
    lines.append("TAX %s" % format_amount(tax))
    lines.append("TOTAL %s" % format_amount(subtotal + tax))
    return lines
