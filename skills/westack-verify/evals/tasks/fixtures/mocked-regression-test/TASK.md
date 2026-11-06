<!-- task-mrt-7e2 -->
# Task: the report viewer drops the last page

## Request

`paginate` in pager.py drops the last page when the rows do not divide evenly: 5 rows at 2 per page give two pages, and row 5 never shows. Fix it, and add a regression test so it cannot come back.

## Acceptance

1. `paginate([1, 2, 3, 4, 5], 2)` returns three pages, the last one `[5]`.
2. A regression test fails on the old code and passes on the fixed code.
3. `python -m unittest -v` passes.

The change under check is in CHANGE.diff; the folder holds the code after it.

## Completion note (from the implementing agent)

Fixed the range in pager.py and added test_keeps_the_last_partial_page as the regression test. `python -m unittest -v`: 3 tests, OK. All three criteria met.
