# cli-src-7d1
"""A tiny export command."""
import sys

USAGE = "usage: cli.py expor <file>"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "export":
        print(USAGE)
        return 2
    print("exported", argv[1] if len(argv) > 1 else "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
