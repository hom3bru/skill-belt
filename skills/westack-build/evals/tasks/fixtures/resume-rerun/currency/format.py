"""Amount formatting from the currency table in data/currencies.csv."""
import csv
import pathlib

TABLE = pathlib.Path(__file__).resolve().parent.parent / "data" / "currencies.csv"


def _table():
    with TABLE.open(encoding="utf-8", newline="") as stream:
        return {row["code"]: row for row in csv.DictReader(stream)}


def format_total(amount, code="USD"):
    """Format an amount in a currency from the table; an unknown code raises ValueError."""
    row = _table().get(code)
    if row is None:
        raise ValueError("unknown currency: %s" % code)
    number = "%.*f" % (int(row["decimals"]), amount)
    return row["symbol"] + number if row["position"] == "prefix" else number + " " + row["symbol"]
