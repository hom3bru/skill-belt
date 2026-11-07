# export-src-1b9
"""ledger export: write a tab-separated ledger file as CSV."""
import argparse
import csv
import os
import sys

MAX_BYTES = 50 * 1024 * 1024


class ExportTooLarge(Exception):
    pass


def export_csv(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise ExportTooLarge("%s is over 50 MB: split it first with `ledger split --rows 100000 %s`" % (path, path))
    target = path + ".csv"
    with open(path, encoding="utf-8") as source, open(target, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        for line in source:
            writer.writerow(line.rstrip("\n").split("\t"))
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ledger export")
    parser.add_argument("--format", choices=["csv", "pdf"], default="csv")
    parser.add_argument("file")
    args = parser.parse_args(argv)
    if args.format == "pdf":
        sys.exit("ledger export: PDF export is not available in this release")
    print(export_csv(args.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
