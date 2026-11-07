import argparse

ITEMS = [
    {"name": "alpha", "archived": False},
    {"name": "beta", "archived": True},
]


def select(archived=None):
    if archived is None:
        return ITEMS
    return [item for item in ITEMS if item["archived"] == archived]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="listctl")
    parser.add_argument("--archived", action="store_true")
    args = parser.parse_args(argv)
    for item in select(True if args.archived else None):
        print(item["name"])


if __name__ == "__main__":
    main()
