import json


def load_rows(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
