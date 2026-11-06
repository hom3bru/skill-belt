# split-src-7d2
"""ledger split: cut a ledger file into parts of at most --rows lines (FILE.part1, FILE.part2, ...)."""
import argparse
import sys


def split(path, rows):
    parts, buffer = [], []
    with open(path, encoding="utf-8") as source:
        for line in source:
            buffer.append(line)
            if len(buffer) == rows:
                parts.append(_write(path, len(parts) + 1, buffer))
                buffer = []
    if buffer:
        parts.append(_write(path, len(parts) + 1, buffer))
    return parts


def _write(path, number, lines):
    target = "%s.part%d" % (path, number)
    with open(target, "w", encoding="utf-8") as out:
        out.writelines(lines)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ledger split")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("file")
    args = parser.parse_args(argv)
    for part in split(args.file, args.rows):
        print(part)
    return 0


if __name__ == "__main__":
    sys.exit(main())
