import csv

from records import from_v1, from_v2


def export(raw_items, out):
    rows = [from_v1(r) if "owner" in r else from_v2(r) for r in raw_items]
    writer = csv.writer(out)
    writer.writerow(["id", "title", "owner"])
    for row in rows:
        writer.writerow([row["id"], row["title"], row["owner"]])
