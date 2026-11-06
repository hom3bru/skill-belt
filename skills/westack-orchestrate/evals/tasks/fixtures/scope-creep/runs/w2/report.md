# Report: w2 (report-w2-6b8)

## Done when
- D1: done: dates.fmt(date(2026, 10, 29)) returns 2026-10-29; test_formats_a_date updated to match
- D2: done: python -m unittest discover -s tests, exit 0, Ran 3 tests, OK

## Decisions
- money.fmt showed 2.67 for 2.675 on the same order screen, so while I was in there I switched it to round half up and added a test for it

## Files
- runs/w2/fmt.patch 3a35579f196f1ac8cf190a313c9c34c473828d7686dc8d25c3f7e6188a5893b2

END-OF-REPORT w2
