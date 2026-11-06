# ledger-main-8e3
"""ledger COMMAND ...: export or split (the `ledger` console script)."""
import sys

from ledger import export, split


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = {"export": export.main, "split": split.main}
    if not argv or argv[0] not in commands:
        sys.exit("usage: ledger {export,split} ...")
    return commands[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main())
