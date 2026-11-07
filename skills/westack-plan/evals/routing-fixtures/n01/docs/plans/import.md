# Plan: customer CSV import

Status: S1 done, S2 ready.

## S1: parse and validate the file

Acceptance: `parse_rows()` rejects a file with no header row. Check: `python -m unittest tests.test_parse` (CI).
Rollback: remove `importer.py`.

## S2: write the rows to the customers table

Depends on: S1.
Acceptance: parsed rows are inserted in one transaction, and a bad row rolls back the whole batch. Check: `python -m unittest tests.test_store` (CI).
Rollback: revert the commit; there is no migration.

## S3: the upload page

Depends on: S2.
Acceptance: a person can upload a file in a browser and sees how many rows were imported. Human only: look at the page.
Rollback: hide the page behind the `import_ui` flag.
