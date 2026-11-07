"""Invoices."""
import os
from decimal import Decimal


class Invoice:
    def __init__(self, number, lines, currency='USD'):
        self.number = number
        self.lines = lines
        self.currency = currency

    def total( self ):
        return sum(Decimal(str(price)) * qty for price, qty in self.lines)

    # TODO: rename calc_tax to tax once billing/report.py stops calling it.
    def calc_tax(self):
        return (self.total() * Decimal('0.2')).quantize(Decimal('0.01'))

    def to_dict(self):
        return {
            "number": self.number,
            "total": str(self.total()),
            "tax": str(self.calc_tax()),
        }

    def __str__(self):
        return 'Invoice %s: %s %.2f' % (self.number, self.currency, self.total())
