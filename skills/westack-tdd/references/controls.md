# Broken-copy controls: the mutation recipe

A control shows that a test detects the break it names. Run the same selection as the passing run against a copy of the code with one realistic defect; the test must fail there on an assertion. This is the core's broken-copy rule made concrete for tests; the core's `verify.md` holds the receipt fields.

## 1. Choose the claim

One claim per test or small group: "`test_bulk_discount` catches a wrong discount rule". The claim names the code under test (file and lines) and the selection (the exact command and test names).

## 2. Choose at least two distinct mutations

Distinct means different edits, preferably of different kinds, at the lines the slice added or the bug lives in. Realistic means a mistake a person could make while writing this code:

| Kind | Example edit |
| --- | --- |
| constant | `0.9` to `0.8`; a wrong unit, limit or default |
| argument | swapped or wrong argument; the wrong field passed on |
| boundary | `>=` to `>`; `< len` to `<= len`; an off-by-one start |
| branch | an inverted condition; the else branch's result in the if branch |
| side-effect | the save, send, emit or state update removed |
| return | an empty, default, `None` or unchanged-input return |
| validation | the guard for empty, zero, missing, unauthorised or malformed input removed |
| error | an error swallowed, or replaced by a default value |

Not controls: a syntax break, a deleted function, a raise at import time. They fail by crashing before any assertion and prove nothing about the test.

In regression mode the pre-fix red run is one control, so one more copy is enough.

## 3. Make the copies outside the work

Never mutate the working tree. Either let the helper write them:

```text
python scripts/controls.py plan spec.json --out <new temp folder>
```

```json
{"format": "westack-tdd-controls-1", "claim": "test_bulk_discount catches a wrong discount rule",
 "root": "<project folder, relative to spec.json>", "command": "<exact test command>",
 "mutations": [
  {"id": "rate", "kind": "constant", "file": "shop/price.py", "find": "0.9", "replace": "0.8"},
  {"id": "edge", "kind": "boundary", "file": "shop/price.py", "find": "qty >= 10", "replace": "qty > 10"}]}
```

It copies the root once per mutation (skipping `.git` and caches, plus any `exclude` names), applies only that edit, and records each file's SHA-256 before and after and the diff in `plan.json`. It refuses a find text that is missing or ambiguous (name an `occurrence`), an edit that changes nothing, two mutations that make the same copy, an output folder inside the root, and a root over `--max-files`. Copies that need a large tree (installed dependencies) are better made with the core's disposable worktree recipe in `verify.md`; record the same hashes by hand.

If the tests run built or generated artefacts (a `dist/` folder, a compiled file, a regenerated client), rebuild inside each copy's command and show the mutation is live in what executes, for example by searching the built output for the edit. A control that ran stale output shows nothing: record it blocked, not survived. For a codemod or bulk transform, first run the same pipeline with a no-op transform: its diff must be empty, or formatter and line-ending changes get credited to the transform.

## 4. Run and judge

From each copy, run exactly the green run's command and selection, and save the raw output. Then:

```text
python scripts/controls.py judge --reference green.txt --run rate=rate.txt --run edge=edge.txt
```

| Outcome | Meaning |
| --- | --- |
| killed | a selected test failed on an assertion: the test detects this break |
| killed-by-error | only errors (unittest ERROR, pytest ERROR): it counts only if the traceback reaches the mutated line, not a broken import |
| survived | every selected test passed: a gap, or an equivalent mutant |
| blocked | no tests parsed, a different selection, a load or collection failure, a newly skipped test, a flaky result or stale built output: it shows nothing |

A timeout is blocked, never a kill. The claim is supported only when no copy survived, none is blocked, and at least two copies were killed. TAP and jest output do not separate errors from assertion failures; read those failures yourself.

## 5. Pair it with the legitimate run

The green run on the real code, same command and selection, in the same session, is the paired check: the copies fail and the real code passes. A control is meaningless if the green run fails too.

## 6. Settle each survivor

A surviving copy is a finding, not noise. Either:
- **strengthen the test**: add the input that tells the two versions apart (the boundary value, the empty case, the second item) or assert the outcome the copy dropped; rerun every control; or
- **argue equivalence in writing**: is the mutated line reachable; is the changed value ever used; across the input domain, does any input give a different result; which distinguishing inputs did you try. Equivalence is argued from the code, never assumed because the tests pass. A boundary change is a real gap unless the boundary value cannot be reached.

"No test reaches this code" is a stronger finding than "the assertion is weak": say which.

## What the controls also catch

- A test whose expected value is computed by the code under test survives every mutation of that code.
- A test that only checks that a mock was called survives every mutation of what was sent.
- A test that only restates a constant or a config value survives every mutation of the behaviour that uses it.
- A test whose act step writes the state its assertion then reads (a direct state change on the claim's own path) survives every mutation of the mechanism it claims to test.
- A scrubber whose pattern never matches leaves the volatile value in. Treat it as code under test: it ships an example it must change, its receipt gives how often it fired (zero protects nothing), and different volatile values must scrub to equal output.

Report each control as a receipt row: kind, file:line, the copy's SHA-256, command, counts, outcome. Never report a kill rate as adequacy; list each survivor.
