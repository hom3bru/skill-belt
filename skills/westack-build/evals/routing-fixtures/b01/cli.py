import argparse
import csv
import sys

from store import load_rows


def export(args):
    rows = load_rows(args.source)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name", "total"])
        for row in rows:
            writer.writerow([row["id"], row["name"], row["total"]])
    print("wrote %d rows to %s" % (len(rows), args.out))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shopctl")
    sub = parser.add_subparsers(dest="command", required=True)
    export_cmd = sub.add_parser("export", help="write orders to a CSV file")
    export_cmd.add_argument("source")
    export_cmd.add_argument("out")
    export_cmd.set_defaults(func=export)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
