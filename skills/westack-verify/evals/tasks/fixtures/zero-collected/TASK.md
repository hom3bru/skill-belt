<!-- work-under-check -->
# Task: reject bad amounts in parse_amount

## Request

`parse_amount` in amounts.py accepts negative amounts and turns text such as "abc" into 0.0. Make it raise ValueError for both.

## Acceptance

1. `parse_amount("-5")` raises ValueError.
2. `parse_amount("abc")` raises ValueError.
3. New tests cover both cases, and the project's test command, `python run_tests.py`, passes.

## Status (written by the implementing agent)

- [x] 1. Negative amounts rejected.
- [x] 2. Non-numeric text rejected.
- [x] 3. Tests added in tests/amount_validation_test.py; `python run_tests.py` exits 0 and prints OK.

COMPLETE
