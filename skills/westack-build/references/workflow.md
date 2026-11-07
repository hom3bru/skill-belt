# Workflow: before the first edit, slices and the rest of the rules

Read in slice and loop modes. The start page keeps the grant (step 1), the scope, test-strength, stop and hand-off rules and the report; this page holds the rest of what the start page said.

## Before the first edit

2. **Inspect.** Repository instructions, the code to change, its callers and its tests. Note which paths were already dirty: they are not yours.
3. **Resolve the checks.** The project's own commands for tests, lint, types and build. Never substitute a familiar one; a missing command is a question or a not-run.
4. **Baseline.** Run those checks before editing and save the raw output outside the work tree.

Details, and when to ask: [start](start.md).

## Build in slices

A slice is the thinnest change that leaves the project working. Edit it, run the focused checks for what it touched, and compare them with the baseline. Fix a new failure inside the slice, or revert the slice. When a slice adds behaviour, a test must exercise it and must fail without the change; when the user wants test-first, hand that slice to `westack-tdd` if it is installed. At the end, rerun the full gate on the final patch. Details: [slices](slices.md).

## Rules in every mode, continued

- **Scope.** With a task record, keep that list as `follow-up` observations worded as open questions (for example, why no check caught this earlier). Before adding code, climb the reuse ladder in core `craft.md`; subtracting never reaches trust-boundary validation, data-loss handling, security or accessibility.
- **Tests stay as strong.** One exception: an assertion that pins exactly the old behaviour the user asked to change may be updated to the new value at the same strength, and the report lists it. Anything else that turns a red test green by editing the test needs the user's decision first.
- **Deferred execution.** Hooks, CI configuration, build and package scripts, `conftest.py`, makefiles, container files and shell or agent-host settings run later, outside this session's authority. Edit them only when the user named that file.
- **No scratch left behind.** Probes, reproduction scripts and logs live in an evidence folder outside the work tree; when you cannot write there, keep receipts inline and say so. Remove anything you created that is not part of the change. Never remove files you did not create.
