# rates.py - currency conversion (cwd-rat-9b4)
import json


def load_rates(path="data/rates.json"):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def convert(amount, currency):
    return round(amount * load_rates()[currency], 2)
