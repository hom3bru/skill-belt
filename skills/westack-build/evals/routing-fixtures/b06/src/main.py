import sys

from config import load_config


def main(path):
    config = load_config(path)
    print("loaded %d settings" % len(config))


if __name__ == "__main__":
    main(sys.argv[1])
