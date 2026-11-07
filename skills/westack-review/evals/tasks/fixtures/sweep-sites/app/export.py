# swp-export-8q3
"""CSV export of orders."""
import csv
import io


def export_rows(rows, seen=set()):
    """CSV text for `rows`, skipping a row already written (so a retried export does not repeat lines)."""
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        writer.writerow(row)
    return out.getvalue()
