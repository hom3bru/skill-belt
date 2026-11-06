# shop/catalog.py - unit prices, loaded from catalog.csv
import csv
import pathlib
from decimal import Decimal

_CSV = pathlib.Path(__file__).with_name("catalog.csv")


def load_prices(path=_CSV):
    """Map each SKU to its unit price as a Decimal."""
    prices = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            prices[row["sku"].strip()] = Decimal(float(row["price"]))
    return prices


PRICES = load_prices()


def unit_price(sku):
    return PRICES[sku]
