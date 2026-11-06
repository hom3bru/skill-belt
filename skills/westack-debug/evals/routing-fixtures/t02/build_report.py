"""Nightly sales report: reads yesterday's orders and writes the summary CSV."""
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

ORDERS_DIR = Path("/var/data/orders")
LEGACY_DIR = Path("/var/data/legacy-orders")
OUT_DIR = Path("/var/data/reports")
REGIONS = {"na": "North America", "eu": "Europe", "apac": "Asia-Pacific"}


def yesterday():
    return datetime.date.today() - datetime.timedelta(days=1)


def read_json(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_orders(day):
    return read_json(ORDERS_DIR / ("%s.json" % day.isoformat()))


def load_legacy_orders(day):
    rows = read_json(LEGACY_DIR / ("%s.json" % day.isoformat()))
    return [
        {"id": row["order_no"], "amount": row["amount"], "currency": row["cur"]}
        for row in rows
    ]


def to_usd(amount, currency):
    rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}
    return amount * rates.get(currency, 1.0)


def merge(current, legacy):
    seen = {order["id"] for order in current}
    return current + [order for order in legacy if order["id"] not in seen]


def region_name(code):
    return REGIONS.get(code, code)


def label(code):
    return "%s (%s)" % (region_name(code), code)


def currency_symbol(code):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    return symbols.get(code, code + " ")


def money_text(value, currency="USD"):
    return "%s%.2f" % (currency_symbol(currency), value)


def share(part, whole):
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


def top_regions(totals, count=3):
    ranked = sorted(totals.items(), key=lambda item: item[1]["revenue"], reverse=True)
    return ranked[:count]


def describe(totals):
    whole = sum(bucket["revenue"] for bucket in totals.values())
    ranked = top_regions(totals)
    return [(name, share(b["revenue"], whole)) for name, b in ranked]


def empty_bucket():
    return {"orders": 0, "revenue": 0.0}


def summarise(orders):
    totals = defaultdict(empty_bucket)
    for order in orders:
        region = order["region"]
        totals[region_name(region)]["orders"] += 1
        totals[region_name(region)]["revenue"] += to_usd(order["amount"], order["currency"])
    return totals


def write_csv(path, totals):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "orders", "revenue_usd"])
        for name in sorted(totals):
            writer.writerow([name, totals[name]["orders"], round(totals[name]["revenue"], 2)])


def main():
    day = yesterday()
    orders = merge(load_orders(day), load_legacy_orders(day))
    totals = summarise(orders)
    write_csv(OUT_DIR / ("sales-%s.csv" % day.isoformat()), totals)


if __name__ == "__main__":
    main()
