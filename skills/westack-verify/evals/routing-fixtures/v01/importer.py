import csv


def import_customers(path):
    imported, skipped, seen = 0, 0, set()
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not {"email", "name"} <= set(reader.fieldnames or []):
            raise ValueError("missing header")
        for row in reader:
            email = row["email"].strip().lower()
            if "@" not in email or email in seen:
                skipped += 1
                continue
            seen.add(email)
            imported += 1
    return {"imported": imported, "skipped": skipped}
