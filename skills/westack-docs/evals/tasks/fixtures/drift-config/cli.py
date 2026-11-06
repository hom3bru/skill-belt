# cli-src-6e2
"""fetchr's command line."""
import argparse

import settings


def build_parser():
    parser = argparse.ArgumentParser(prog="fetchr", description="Fetch a URL and print it as JSON or CSV.")
    parser.add_argument("url", help="the URL to fetch")
    parser.add_argument("--timeout", type=float, help="seconds to wait (default: FETCHR_TIMEOUT, else the built-in default)")
    parser.add_argument("--format", choices=settings.OUTPUT_FORMATS, help="output format (default: json)")
    return parser


if __name__ == "__main__":
    print(build_parser().parse_args())
