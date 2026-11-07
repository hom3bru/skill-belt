# Slices

## Choosing them

- A slice is one behaviour or one structural step carried end to end. After it, the project builds and every test passes except the ones that failed in the baseline.
- Put the riskiest or least certain slice first: the integration that might not work, the API you have not used before. Proving the approach early is worth more than polish late.
- For an unfamiliar library, check the installed version and its documentation first (core `inspect.md`).
- Write the slice list in the reply: the slice, the files, the focused check. When you learn something that changes it, revise it and say why.
- Where slices may run in parallel, give each slice's paths with the operation after any path that is more than add or extend: `src/a.py (replace)`, `(remove)`, `(rename)` or `(migrate)`. Slices that no dependency orders and whose paths overlap are a plan defect to fix before dispatch, not a conflict to merge afterwards (`westack-plan`'s `plangraph.py` warns `overlapping-paths`). The claim coordinates writers and does not isolate them (core `isolation.md`).

## One slice

1. **Re-read** any file you are about to edit if something changed it since you last read it.
2. **Edit** the smallest amount this slice needs, and nothing for later slices. Apply a patch only on unique, exact anchors: check before applying, allow no fuzz, and report each hunk as applied, failed (with the nearest real lines) or already present. After a refusal, say plainly that nothing changed. Pick the nearest lines ignoring whitespace, and give their line numbers.
3. **Focused checks.**
   - Lint and type-check the touched files and compare with the baseline errors for those files. Only new errors are yours. An old error stays reported, not fixed, unless it is in scope.
   - Where the host offers editor diagnostics, read them after each edit. An empty list that may mean no server answered is inconclusive unless the diagnostics version changed; never record it as a clean check.
   - Run the tests nearest the change (the module's test file, or a name selector) and any test you added.
   - Do not rerun a check that already passed on unchanged code; it tells you nothing new.
4. **Read the result.**
   - All passed: write one receipt line and take the next slice.
   - A new failure in what you touched: fix it inside this slice.
   - The same check failing the same way after a fix: that approach is finished. Revert the slice or take a different approach, and note what the failure ruled out.
   - A failure you cannot explain: stop editing and switch to `westack-debug` in diagnose mode, or report it.
   - A fix that needs a path or action outside the grant: stop and ask. Never widen scope silently.
5. **New behaviour gets a test that exercises it.** Add it as a new test or new test file. Watch it fail without the change (run it before the code edit, or against a copy with the change reverted), then pass with it. That failing run is the broken-copy control for "this test checks the feature".

A receipt line, inline:

```text
slice 2 | python -m unittest tests.test_money -v | exit 0 | 6 collected, 6 executed, 6 passed, 0 failed, 0 skipped | passed
```

## The final gate

- After the last slice, on the final patch, run the same commands as the baseline: the full suite, lint, type check and build.
- `python "<core>/scripts/checks.py" diff <baseline> <final>`: exit 0 means no new failures; 1 lists them; 2 means it cannot tell (tests missing, newly skipped, or a run that did not finish). Treat 2 as not passed until you can explain it.
- Map each acceptance criterion to the receipt that shows it: a named test and its result, or an observed output. A green suite that never reaches the new behaviour does not show it.
- Run the delivery diff audit (`SKILL.md`).
- Any edit after the gate makes its receipts stale. Rerun what the edit affects, then the gate.

## Bulk edits

One transform over many files (codemod, rename, migration):

- Before any write, a clean tree or a named restore point (core `isolation.md`). Start with a read-only census counting each variant of the old pattern; write fixtures for the variants found, not imagined, negative ones included (`westack-tdd`, `test-quality.md`). Pilot on a small named sample, review that diff, record the sites covered, then widen.
- Done when every target file has one outcome, counted apart: changed, unchanged, declined, skipped by policy or failed. These are file outcomes, not receipt statuses: one failure fails the run however quiet its output, and zero files in scope is inconclusive.

## What counts as weakening a test

- changing an assertion's expected value, operator, tolerance or pattern so that it accepts more;
- adding a skip, an expected-failure or a focus marker, or a condition that bypasses the check;
- deleting or renaming a test, or moving it where the runner no longer collects it;
- narrowing selection in configuration or in the default command (deselect lists, ignore patterns, name filters);
- regenerating a snapshot, golden or expected-output file from the new output;
- mocking the unit under test, or catching the exception the test expects;
- raising a timeout or a retry count to get past a failure.

When an existing test blocks the requested change, show the test, the behaviour the user asked for and the conflict, recommend an answer, and wait. The one exception is in `SKILL.md`: an assertion pinning exactly the old behaviour the user asked to change.

## Craft inside a slice

- Follow the neighbouring code's patterns and names; one name per idea.
- The smallest sufficient change. No abstraction before a second real caller, no comments that narrate the next line, no catch-all error handling, no checks for states that cannot happen.
- Delete what your change made dead, in the same slice. Code you did not touch is outside the slice even when it looks dead.
