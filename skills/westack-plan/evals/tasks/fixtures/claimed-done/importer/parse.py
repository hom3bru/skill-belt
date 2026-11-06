# parse-src-6f1
import csv
import io


def parse_rows(text):
    reader = csv.DictReader(io.StringIO(text))
    return [{"name": row["name"].strip(), "email": row["email"].strip()}
            for row in reader if any((value or "").strip() for value in row.values())]
