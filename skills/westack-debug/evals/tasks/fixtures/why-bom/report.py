# report.py - the total of the amount column of a billing export (bom-rep-1d7)
import csv
import sys
from decimal import Decimal


def total(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return sum((Decimal(row.get("amount") or "0") for row in csv.DictReader(handle)), Decimal("0"))


if __name__ == "__main__":
    print("total: %.2f" % total(sys.argv[1]))
