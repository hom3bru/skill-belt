import argparse


def parser():
    top = argparse.ArgumentParser(prog="notes")
    sub = top.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("text", nargs="?")
    add.add_argument("--tag")
    listing = sub.add_parser("list")
    listing.add_argument("--tag")
    listing.add_argument("--limit", type=int, default=20)
    export = sub.add_parser("export")
    export.add_argument("--format", choices=("md", "json"), required=True)
    return top
