# export-src-5c2
"""Nightly finance export.

Cron, 02:00:  curl -s https://shop.internal/orders > exports/orders.json && python jobs/nightly_export.py
Writes exports/orders.csv, which finance imports into the ledger every morning.
"""
import csv
import json
import pathlib

SOURCE = pathlib.Path("exports/orders.json")
TARGET = pathlib.Path("exports/orders.csv")


def rows(orders):
    for order in orders:
        yield [order["id"], "%.2f" % order["amount"], order["currency"]]


def main(source=SOURCE, target=TARGET):
    orders = json.loads(pathlib.Path(source).read_text(encoding="utf-8"))
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["order_id", "amount_eur", "currency"])
        writer.writerows(rows(orders))


if __name__ == "__main__":
    main()
