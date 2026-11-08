# Discovery ledger (optional, file-first)

Use the recipient's search tools to find provider calls, then follow callers to a live path. Classify disabled, test-only, and already-coded paths before estimating conversion value. Use existing sanitized trace exports only when authorized; absence of traces grants no instrumentation or provider permission.

For each seam record: caller/file evidence; observation window and recurrence; calls/tokens/cost with provenance; output contract; state/effects; proposed mechanism and cheapest algorithmic comparator; oracle; unknowns; expected validity horizon; falsifier. Rank a Pareto shortlist using recurrence, error exposure and total decision value. Unknown volume, missing state and unknown cost stay unknown; do not manufacture a universal conversion score.

## Worked ledger: authored fixture, not measured traffic

| Seam | Caller evidence | Recurrence / window | State / effects | Proposal | Oracle / gap | Estimated savings |
| --- | --- | --- | --- | --- | --- | --- |
| live-policy | `fixtures/live.py:4`, enabled caller | 100 calls / synthetic day | policy flag present, pure | test selective rule | authored reference; real labels absent | unknown cost |
| disabled | `fixtures/disabled.py:3`, feature off | 0 / synthetic day | no active caller | exclude from current shortlist | activation unknown | 0 current calls |
| test-only | `fixtures/test_example.py:2` | tests only | fixture state | exclude production savings | no production evidence | unknown |
| coded-rule | `fixtures/rule.py:2` | no provider calls | deterministic lookup | reuse existing rule | existing contract | 0 inference removed |
| missing-state | `fixtures/state.py:4` | unknown | unavailable account state | insufficient evidence; acquire state if authorized | state unavailable | unknown |

The runnable fixture files and retained decisions are in `assets/discovery/`. They deliberately contain no callable provider. [test_templates.py](../tests/test_templates.py) checks the decisions against these different evidence conditions; broken copies must catch recommending all five and assigning savings to missing state. No scanner or store is added.

Choose one scoped seam only after evidence supports a useful hypothesis. A disabled call can become relevant if activation is the requested task; this example does not ban that investigation.

For reuse and net-value decisions, continue with [lifetime.md](lifetime.md).
