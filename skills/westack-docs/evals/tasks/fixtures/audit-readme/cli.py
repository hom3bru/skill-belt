# cli-9b3: the whole command-line surface of tidy at this commit.
import argparse


def build_parser():
    parser = argparse.ArgumentParser(prog="tidy", description="Format Markdown tables in place.")
    parser.add_argument("files", nargs="+", help="Markdown files to format")
    parser.add_argument("--check", action="store_true", help="exit 1 if a file would change; write nothing")
    return parser


if __name__ == "__main__":
    print(build_parser().parse_args())
