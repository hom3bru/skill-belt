# export-src-2d8
"""Write report rows (dictionaries) to files."""
import csv
import json


def export_json(rows, path):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(list(rows), stream)


def export_csv(rows, path):
    rows = list(rows)
    fields = list(rows[0]) if rows else []
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
