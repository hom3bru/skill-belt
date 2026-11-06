import csv
import io

from orders import list_orders


def export_csv(user_id):
    rows = list_orders(user_id, status="complete")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "placed_at", "total"])
    for order in rows:
        writer.writerow([order["id"], order["placed_at"], order["total"]])
    return out.getvalue()
