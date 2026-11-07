# Characterise mode: tests for code that already exists

Use it when the user asks to add tests to existing code, before changing code that has none, when code was written before its tests, or to judge whether existing tests protect anything. The order is test-after, and the report says so.

## Why there is no red run

A characterisation test describes what the code does now, so it passes on its first run by design. A first-run pass proves nothing about the test, so the evidence that it can fail comes from controls instead: at least two distinct broken copies per behaviour claimed, each killed on an assertion ([controls](controls.md)).

## Steps

1. **Baseline.** Run the full suite and keep the raw output.
2. **Pick the behaviours that matter.** The paths the coming change touches, the rules with money, permissions or data loss behind them, and the branches callers rely on. Not every line.
3. **Find an oracle.** Prefer an independent source: the spec, documentation, an example in an issue, a value a person or another system produced. When the only oracle is the current code, run it once on chosen inputs, record the outputs as literals, and label those tests "pins current behaviour, not correctness".
4. **Surface suspicious values.** When a recorded output looks wrong (a negative total, a dropped item, an off-by-one), do not quietly enshrine it. Report it to the user as a possible bug, with the input, and ask whether to pin it or to treat it as a regression to fix.
5. **Probe, then write.** Run the controls ([controls](controls.md)) on the untouched suite first, recording the existing test that killed each copy; write tests ([test quality](test-quality.md)) only for the survivors, and run them green.
6. **Controls.** Mutate the code each test claims to protect; settle every survivor by strengthening the test or arguing equivalence. Report coverage as behaviours pinned by named tests, not line percentages.
7. **After-run** with `checks.py diff` against the baseline.

## Judging existing tests

Run controls against the tests that claim to cover the code. Each survivor is a gap: name the input or assertion that would kill it. Tests without assertions, tests that only read source text, and near-duplicate tests are candidates to flag with evidence. Change or remove existing tests only with the user's approval of that batch.

## Golden files

A check against approved (golden) files never overwrites them: it writes what it saw beside the approved file and fails; accepting the candidate is the user's call. After the run, count leftover candidate files by name: any left is a failure, whatever the exit code. A runner that can only overwrite needs a wrapper, or its pass cannot back a parity claim. Never accept a pending golden from a run with other new failures: fix or baseline those and rerun. Present candidates as a list, one old-versus-new diff each; approval is the user's act (by item key, by removing a failing marker, or by a script you wrote but did not run), and accept-all needs their explicit word. Grants and update runs: core `authority.md`, `evidence.md`.

## Then change the code

With the behaviour pinned and the controls passing, continue in slice or regression mode for the change itself. A characterisation test that the change is meant to break is updated in the same slice, with the reason stated.
