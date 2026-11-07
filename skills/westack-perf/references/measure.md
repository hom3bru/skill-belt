# Measuring

## The run file (format westack-perf-run-1)

One file per side: `format`, `kind` (page, request or command), `target`, `claim` (the sentence you expect to ship, written before measuring), `driver` and `environment` (page: os, browser, viewport, cache; request and command: machine, with CPU, load and build mode), `runs` (each with `metrics` and an `errors` count) and `limiter`. Metric names carry their unit: `*_ms` timing, `*_bytes` size, `total_requests` a count, anything else unitless. Saved runs can be appended to a JSONL history with an `at` timestamp for `perfcheck.py history`.

## Vet the number

Answer each from a run. A one-run ballpark the user asked for says it is one run and still answers questions 4 and 7.

1. **Why not double?** Name the limiter: one core at 100%, a script parse, a serialized request chain, link bandwidth, a lock. Profile in a run you do not report; profilers slow the work. A change that did not move the number left the limiter alone.
2. **Was it tuned?** Both sides as production runs them: build and flags, data, cache warmth, versions. A side on defaults compares configurations, not implementations.
3. **Did it break a limit?** Do the arithmetic: removing a piece that took 10% of the run makes it at most about 11% faster. A result past a limit measured something else (a cache, a no-op, a bug).
4. **Did it error?** Count failures, timeouts, retries and non-success responses, and check the output is right. Rejections are fast.
5. **Does it reproduce?** At least five runs per side, alternating, reported as median and range. A gap inside the run-to-run spread is no difference.
6. **Does it matter?** Put the number next to the whole path a user waits on and give its share.
7. **Did it even happen?** The work ran inside the timed region: the request reached the server, the bytes arrived, the frame painted, the result was used.

## Comparing

`perfcheck.py compare baseline.json current.json` compares medians metric by metric (`thresholds.json`):

| Unit | Regression | Warning |
| --- | --- | --- |
| timing | over 50%, or over 500 ms | over 20% |
| size | over 25% | over 10% |
| count | none | over 30% |
| unitless (CLS) | over +0.1 | over +0.05 |

A delta no larger than either side's spread is "no measurable difference"; a drop beyond the spread is "improved". The verdict is slower, slower (warning), faster or no measurable difference, and becomes inconclusive with fewer than five runs a side, any errors, no metric in common, or a claimed difference with no limiter.

## Requests and commands

Time them the way the project does (its benchmark command, its client, or a timer around one invocation), the same way every run, with the output checked each time. A request against a system that is not yours, or under load that could hurt others, needs a grant naming it.
