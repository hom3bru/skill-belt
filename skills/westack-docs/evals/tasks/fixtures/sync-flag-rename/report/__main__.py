# report-main-2b5
"""python -m report: write the weekly CSV."""
import argparse
import csv
import sys


def _format_row(row):
    return [row["week"], "%.2f" % row["total"]]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m report")
    parser.add_argument("--output", required=True, help="path of the CSV to write")
    args = parser.parse_args(argv)
    rows = [{"week": "2026-W44", "total": 1250.0}]
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["week", "total"])
        for row in rows:
            writer.writerow(_format_row(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
