# Fix mode

Only after the user asked for a fix or said yes to the diagnosed one. The yes covers the change it named; a different or wider change needs a new answer. Diagnosis still comes first, even when the request was "fix it": run the loop, then these steps.

## Steps

1. **Baseline.** Before editing, run the relevant suite (all of it when practical) and keep the raw output. Note the tests already failing, by name.
2. **Regression test that fails for the right reason.** Turn the small reproduction into a test at a point that exercises the real bug path. Run it: it must fail on an assertion about the user's symptom, not on an import error, a typo or a missing fixture. If no honest place for the test exists, say so; that is a finding about the design, not a reason to fake one.
3. **Fix where it starts.** Make the smallest change at the place where the value first goes wrong, not where the error surfaced. No refactoring, no tidying on the side. A fix that spreads across many files is a change of scope: stop and ask.
4. **Pass.** Rerun the regression test and the original, unshrunk reproduction. Both must pass.
5. **Broken-copy control.** Undo only the fix, keep the test, and rerun it: it must fail again. Put the fix back. Keep both outputs; a test that still passes with the fix undone proves nothing.
6. **Same defect elsewhere.** Fix the other sites the sweep found only when they are inside the agreed scope; list the rest with file and line.
7. **After-run.** Rerun the step 1 command, keep its output, and compare by test name with the core's `checks.py diff <before> <after>` (without the core, compare the failing names by hand). Report new failures separately from pre-existing ones. A new failure means the work is not done.
8. **Clean up.** Delete tagged debug lines (search for the tag) and scratch files. List every changed path from the real diff and label it: the fix, the regression test, scratch (delete it), or an existing test changed (the user decides, given the reason).

## Done means

Every one of these holds: the regression test failed before the fix and passes after it; the control failed with the fix undone; the original reproduction passes; the before-and-after comparison shows no new failures and no missing tests; debug lines and scratch are gone. Short of that, report "partly fixed" or "not verified" and say what is missing. Intermittent bugs also need the run counts in [flaky](flaky.md).

The change stays local unless the user grants more; commit, push and pull request are separate actions.
