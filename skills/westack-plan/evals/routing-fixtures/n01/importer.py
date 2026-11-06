import csv


def parse_rows(lines):
    reader = csv.DictReader(lines)
    if not reader.fieldnames or "email" not in reader.fieldnames:
        raise ValueError("missing header row")
    return list(reader)
