# report.py - totals for the daily report (olk-rep-2b8)
from decimal import Decimal

import settings


def format_total(amount):
    cfg = settings.load()
    step = Decimal(1).scaleb(-cfg["decimals"])
    return "%s %s" % (Decimal(amount).quantize(step), cfg["currency"])
