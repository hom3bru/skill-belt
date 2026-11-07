# Review request: PR-77

PR-77 says it fixes ISSUE-31: `top()` in `report/rank.py` returned players with equal scores in a different order from run to run.

From the author's note:

> The old `rank.py` is kept in `before/rank.py` for comparison. My new test, `tests/test_rank.py`, failed 10 times out of 10 against the old code and passes against the fix, so the fix is proven.

Check the red-test claim before PR-77 is merged. Change no file under `report/`, `before/` or `tests/`.
