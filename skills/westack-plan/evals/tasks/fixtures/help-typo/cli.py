"""Tiny export command line."""
import sys

USAGE = "Usage: expor FILE  (write the orders to FILE as CSV)"


def main(argv):
    if len(argv) != 2:
        print(USAGE)
        return 64
    print("would export to " + argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
