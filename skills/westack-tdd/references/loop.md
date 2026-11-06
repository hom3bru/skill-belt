# The loop (slice mode)

Read in slice and regression modes. Steps 2 (red) and 5 (controls) are the start page's rules, in full there.

0. **Baseline.** Find the repository's own focused and full test commands (wrappers, scripts, CI files; never assume `npm test`). Run the full suite once; that result is the baseline.
1. **Name the behaviour and its break.** One behaviour at a public seam, and the production change that should make the test fail. Expected values come from somewhere other than the code: the spec, a worked example, a literal you checked by hand. Never from the code under test or its helpers.
2. **Red.** The start page's **Red** rule.
3. **Green.** The smallest change that passes. Rerun the focused test, then its neighbours. Never edit the test to get green; if the test itself was wrong, say so, fix it, and re-establish red.
4. **Refactor** only on a green you ran, with no new behaviour, then rerun. The collected count never drops without a stated reason.
5. **Controls.** The start page's **Controls** rule.
6. **Next slice**, or finish: rerun the step 0 command and compare with `checks.py diff`.

Helper for larger mutation sets (standard library, runs nothing): `python "<this skill's folder>/scripts/controls.py" plan SPEC --out NEW_FOLDER` writes one broken copy per mutation and refuses no-op, duplicate or ambiguous edits; `controls.py judge --reference GREEN --run LABEL=RAW ...` classifies saved outputs as killed, killed-by-error, survived or blocked (`--assertion-only --min-kills 1` checks a red run).

## With and without the core

Recorded work uses the core task record (`validate.py receipt` snapshots the red-phase file so its receipt survives the fix). Core missing: failing names compared by hand, and `scripts/controls.py judge` is unavailable (`plan` still works).

## Test quality

Full rules: [test quality](test-quality.md) and [mocking](mocking.md).
- Test behaviour through the public interface; a refactor that keeps behaviour must keep the test green.
- Mock only at boundaries you do not own. A test whose only assertion is that a mock was called proves the wiring, not the behaviour: assert what crossed the boundary (recipient, amount, payload) or the outcome.
- An expected value computed by the code under test always agrees with it, so the test passes on a broken implementation. The controls expose it: every copy survives.
- Never weaken a test to pass: the start page's rule.
- Prose and config get no fabricated red test. A test that the config file says 10 only restates the file.

## Hand-offs

`westack-build` may hand over a test-first slice: take its behaviour and seam, return its receipts and changed paths (build runs its own wrap-up gate).
