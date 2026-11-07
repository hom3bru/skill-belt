# Claim mode: one claim

For a single statement such as "this commit fixes the timezone bug", "the new test catches the null case" or "the import is twice as fast". Inline receipts are enough unless the user wants files.

## 1. Restate it so it can fail

Write the claim as a condition, an observable and a threshold:

- "With the fix, `pytest tests/test_tz.py::test_dst_gap` executes 1 test and it passes; without the fix it fails on its assertion."
- "On this machine, importing the 50 MB sample takes at most half the time it took at the parent commit, median of 5 runs."

A claim with no observable ("the code is cleaner") is out of scope. Ask what result would show it, or report not-run. A check that finds no target (nothing selected, a lookup that returns nothing), gets malformed input or cannot apply a rule is blocked or inconclusive, never passed or clean.

## 2. Choose the smallest check that could prove it wrong

Prefer the focused test, repro command, request and response, or timing that touches the claimed behaviour directly. Run the claimant's own command too, exactly as they ran it: the gap between their command and yours is often the finding.

## 3. Before and after, same conditions

- **Before** is the state the claim improves on: the saved red run, the parent commit or merge base, or HEAD in a disposable worktree when the change is uncommitted. Use the core's worktree recipe in `../westack/references/verify.md`; never stash or reset the user's tree. To show one failing test was already failing, run just that test at the parent commit in a detached worktree, with a receipt bound to that commit, and tell the user either way.
- **After** is the current work, with the same command, data, environment and warm-up.
- For a metric, fix the threshold first, take both runs on the same machine and repeat enough to see the noise. A difference inside the noise is inconclusive.

When no valid before state exists, say so. The claim can still pass on its own terms ("the test passes"), but a claim of change ("fixed", "faster") is then inconclusive.

## 4. Control a detection claim

When the claim is that a test or check catches something, it must fail on a copy where that something is broken:

- the red run before the fix serves, if the test has not changed since;
- otherwise revert the fix in a disposable worktree and rerun the same selection;
- the control must select the same cases and fail on the assertion. A crash, an import error or zero collected cases shows nothing.

Keep the failing output with the passing one.

## 5. Verdict

One result: passed, failed, inconclusive, blocked or not-run. Then the claim as restated, the evidence (before, after, difference, threshold), and one short paragraph naming any confound. A failed claim is stated plainly; do not soften it into "mostly works". A "can happen" claim is shown true by doing it once; a failed attempt is inconclusive (the attempt may be at fault), and it is impossible only when the system's own numbers prove it, named in the evidence. Reading code says where to look; a defect counts once the running system shows it.

```text
failed
Claim: with the fix, test_dst_gap executes 1 test and passes; without the fix it fails on its assertion.
Evidence: after = 1 executed, 0 passed, 1 failed (exit 1); before = same failure. The fix does not reach the DST branch.
```
