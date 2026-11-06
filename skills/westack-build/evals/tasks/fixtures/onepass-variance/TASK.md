# LAT-7: variance over the log stream

`variance()` in `stats/summary.py` now receives latencies straight from the log reader: a one-shot iterator over millions of values. Today it copies them into a list and walks them twice.

Change `variance()` so it reads its input once, in a single pass, keeping only a few numbers in memory (no list, no second pass). It must accept any iterable, a generator included, and return the population variance.

Acceptance: `variance(iter(values))` equals `variance(values)`, and the test suite passes (`python -m unittest`).

Scope: `stats/summary.py` and the tests.
