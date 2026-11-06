import csv


def upsert(sku, qty):
    print("upsert", sku, qty)


def run(path):
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            upsert(row["sku"], int(row["qty"]))
