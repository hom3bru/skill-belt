# Plan: customer CSV import

Status: S1 done, S2 ready.

## S1: parse and validate the file

Acceptance: `parse_rows()` rejects a file with no header row. Check: `python -m unittest tests.test_parse` (CI).
Rollback: remove `importer.py`.

## S2: write the rows to the customers table

Depends on: S1.
Acceptance: parsed rows are inserted in one transaction, and a bad row rolls back the whole batch. Check: `python -m unittest tests.test_store` (CI).
Rollback: revert the commit; there is no migration.
