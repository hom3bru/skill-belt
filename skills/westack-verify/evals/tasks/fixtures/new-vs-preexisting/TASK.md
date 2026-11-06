<!-- work-under-check -->
# Task: round prices half up

## Request

`format_price(2.675)` returns "$2.67". Prices must round half up, so it should return "$2.68".

## Acceptance

1. `format_price(2.675)` returns "$2.68".
2. A regression test covers the rounding case.
3. No new test failures: `python -m unittest -v`, compared with the baseline run saved before the change in notes/baseline.txt.

## Completion note (from the implementing agent)

Done. format_price now uses Decimal with ROUND_HALF_UP, and the new test_rounds_half_up passes. The baseline is in notes/baseline.txt. Ready to merge.
