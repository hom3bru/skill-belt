import csv


def export_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name", "total"])
        for row in rows:
            writer.writerow([row["id"], row["name"], row["total"]])
