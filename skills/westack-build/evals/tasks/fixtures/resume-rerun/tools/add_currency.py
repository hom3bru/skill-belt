"""Add a currency to data/currencies.csv.

Usage: python tools/add_currency.py CODE SYMBOL prefix|suffix DECIMALS
"""
import pathlib
import sys

TABLE = pathlib.Path(__file__).resolve().parent.parent / "data" / "currencies.csv"


def main(argv):
    if len(argv) != 4 or argv[2] not in ("prefix", "suffix") or not argv[3].isdigit():
        sys.stderr.write(__doc__)
        return 64
    with TABLE.open("a", encoding="utf-8", newline="") as stream:
        stream.write(",".join(argv) + "\n")
    print("added %s" % argv[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
