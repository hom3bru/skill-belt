import csv


def export_customers(rows, stream):
    """Nightly CSV export consumed by the finance team's import job."""
    writer = csv.writer(stream)
    writer.writerow(["id", "name", "email"])
    for row in rows:
        writer.writerow([row["id"], row["name"], row["email"]])
