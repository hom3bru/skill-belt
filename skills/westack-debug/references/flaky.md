# Intermittent, order-dependent and timing failures

"Flaky" names a symptom, never a cause. Until a probe has shown the cause: no rerunning until green, no retry, no longer timeout, no skip, no looser assertion.

## Measure the rate

Run the failing test alone N times and record failures out of N; when a known-good revision exists, do the same there. If it also fails on the known-good revision, the current change did not cause it.

Zero failures after a fix only counts when there were enough runs for a surviving bug to have shown up. If the failure rate before the fix was p, zero failures in n runs is evidence at roughly the 95% level only when n is at least ln(0.05) / ln(1 - p):

| Failure rate before the fix | Clean runs needed |
| --- | --- |
| 50% | 5 |
| 20% | 14 |
| 10% | 29 |
| 5% | 59 |
| 1% | 299 |

Fewer clean runs than that is inconclusive, not fixed. The cheaper route is to make the failure deterministic first (below); then one forced failure before the fix and one pass after it settle the question.

## Name the hidden input

The outcome is being decided by an input the test does not control: the clock or time zone, test order, shared state, randomness, the network, a resource limit, concurrency, machine load. Compare a failing run's output with a passing one and find the first place they differ.

## Force it

Build the smallest probe that makes the failure happen every time for the cause you named: set the time zone or inject the clock, fix the seed, run the suspect test straight after the one that leaks into it, or add a pause at the suspected window. If you cannot force it, you have not named the cause.

## By kind

- **Clock and time zone.** Code that mixes local and UTC time, or depends on the current date or hour, fails only at some times or in some zones. Reproduce by setting the zone (for example the `TZ` environment variable) or injecting a fixed clock at a moment that triggers it, such as near midnight or a daylight-saving change. The regression test pins that moment.
- **Order-dependent.** The victim passes alone and fails after other tests. Split the tests that ran before it in half, keep the half that still breaks it, and repeat until one test is left. Fix the test that leaks state (environment variables, working directory, module-level caches, mocks left in place, temp files, open listeners, timers), not the victim.
- **Races.** Each time the shared data is touched, log which actor touched it and a monotonic timestamp; hold one actor at the suspected point so the other runs inside the window; then run several writers concurrently and check what must stay true (one winner, every write applied, data intact). The fix is an atomic operation or a real lock; a narrower window is not a fix.
- **Timing assertions under load.** Compare the measured value's spread on the good and current revisions under the same load. Assert on outcomes or an injected clock instead of wall time; raising a bound is not a fix.

## When only the test changes

Changing a test (its isolation, its clock, how it waits) is right when the test itself was wrong. Show it still catches what it guards: break the guarded behaviour on purpose, and the changed test must fail. Without that broken-copy run the change may simply have blinded the test, and the user decides whether to keep it.

## When rerunning is fine

Rerunning is fine in one situation: you know the cause, it lies outside this work (an infrastructure fault, a fix already on the main line), you count the reruns, and the report says all of that.
