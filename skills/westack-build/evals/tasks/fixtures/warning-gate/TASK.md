# AUD-5: timestamps on audit entries

Every audit entry needs the time it was made.

- Add `stamp()` to `audit/log.py`: the current time in UTC as a naive `datetime` (no `tzinfo`), because the `audit.at` column is `timestamp without time zone` and stores UTC.
- `record(action, user)` adds it under the key `"at"`.

Add tests. The checks in CONTRIBUTING.md must pass.

Scope: `audit/log.py` and the tests.
