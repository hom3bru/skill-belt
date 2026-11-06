# Task: CSV import

Import customers from a CSV file.

Acceptance criteria:
1. A header row with `email` and `name` is required; a file without it is rejected.
2. Rows with an invalid email are skipped and counted in the result.
3. A duplicate email in the same file keeps the first row only.
4. The importer returns `{"imported": n, "skipped": m}`.
