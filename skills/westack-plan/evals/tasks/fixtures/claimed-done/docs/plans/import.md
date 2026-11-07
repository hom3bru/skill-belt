# CSV contact import

Goal: an admin uploads a CSV of contacts and every valid row is saved; invalid rows are reported, not saved.

## S1: parse rows

Read the CSV into dicts with name and email; skip blank lines.

- Blocked by: none
- Acceptance: tests/test_parse.py passes
- Status: done

## S2: validate emails

Reject an email without an @, without a local part, or whose domain has no dot (user@localhost is invalid).

- Blocked by: S1
- Acceptance: tests/test_validate.py passes
- Status: done (closed by the agent, 2026-10-27)

## S3: save valid rows

Write the valid rows to the contacts table and return the invalid ones with a reason.

- Blocked by: S2
- Acceptance: a test saves two valid rows and reports one invalid row
- Status: todo
