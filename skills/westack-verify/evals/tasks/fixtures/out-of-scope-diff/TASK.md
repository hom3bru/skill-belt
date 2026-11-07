<!-- task-osd-1e4 -->
# Task: SMS receipts drop the leading zero

## Request

`format_phone` in phone.py turns "07700900123" into "7700 900123", so SMS receipts go nowhere. Fix the formatting.

## Acceptance

1. `format_phone("07700900123")` returns "07700 900123".
2. `python -m unittest -v` passes.

The change under check is in CHANGE.diff; the folder holds the code after it.

## Completion note (from the implementing agent)

Changed phone.py and tests/test_phone.py. `python -m unittest -v`: 4 tests, OK. Both criteria met.
