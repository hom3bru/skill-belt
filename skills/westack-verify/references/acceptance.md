# Acceptance mode: is the task done?

For a task, PR or branch with several criteria. Work through the steps in order; each one can end the run early with a failed or blocked result, but report everything already learned.

## 1. Criteria table

One row per criterion: id, the criterion restated so it can fail, verifier (`agent` or `human`), the check that would settle it, and the evidence type it needs (read, unit, integration, end-to-end, observation on the real path). Add the standing criterion "no new test failures against the baseline" unless the user excluded it. A decision that names the check showing it was followed becomes a criterion; until a passing receipt covers that check, report it as decided but unconfirmed, never implemented.

If the work was claimed in an earlier session, run [resume](resume.md) first.

## 2. Baseline and after-run of the suite

Use the repository's own test command for the whole relevant suite, even when the task names one file. Get the baseline from the first of these that exists:

1. a saved baseline whose raw output and command match the after-run (a task record receipt, or one the claimant saved). Record who produced it; it is still raw runner output, not a summary;
2. the same command at the pre-change revision (merge base, parent commit, or HEAD when the change is uncommitted) in a disposable worktree outside the work;
3. none. Then every after-run failure is listed as unattributed (or, for one failing test, proved pre-existing at the parent commit: [claim](claim.md), step 3), and "no new failures" is inconclusive.

Save both raw outputs in the evidence root, with the options and inputs in effect for each (a name filter, a path subset, fail-fast, retries): a run narrowed by a flag, or by an input its runner ignored, covers less than the suite, so "no new failures" is inconclusive for the part it skipped. Then run `python "<core>/scripts/checks.py" diff <baseline> <after>`. Exit 1: the new failures fail the criterion. Exit 2: read its reasons; a test failing with changed text is unattributed, not pre-existing. A missing test or a test that is now skipped is a finding for the diff audit, never something to explain away. Keep the JSON beside the raw outputs. An accepted-failure list holds exact, dated entries with a reason and a review date; a broad rule is a policy decision.

A criterion that passed in an earlier receipt and now fails is regressed: name the last passing receipt and the files changed since (the manifests between the patches). Recheck every criterion each iteration; reuse a heavy check only while it last passed and its declared paths are unchanged.

## 3. Each agent criterion

Run its check and tie the result to a receipt. Two traps:

- a green suite that never touches the changed behaviour shows nothing about it. Name the test or observation that exercises the behaviour, or mark the criterion inconclusive;
- a criterion that says a test or guard detects a failure needs a broken-copy control ([claim](claim.md), step 4);
- a direct state change (seeding data, setting a value, jumping the system to a state) may set up or measure a check, never achieve what the criterion is about: list each with its reason, by phase (setup, action, measure); a result reached through one on the criterion's own path is a cheat, not a pass;
- a check run with a selection flag, or with an input its runner or CI action silently ignored, is a narrower claim than the criterion: record the options in effect, treat the skipped part as not-run, and never call a green exit a full pass.

For a check you may not run (outside your grant, CI-only, special hardware), give the user the exact command and where to save its output, or read the CI log for the exact revision. A badge is not a log. Until then the criterion is blocked.

## 4. Delivery diff audit

List every changed path from version control, never from the claimant's summary:

- `git status --porcelain=v1 --untracked-files=all`, plus `git diff --name-status <base>` for committed work; or the PR's diff.

Classify each path:

| Class | Examples | Report |
| --- | --- | --- |
| intended | serves a criterion | nothing more |
| scratch | repro scripts, debug output, temp files, notes left in the tree | name it; it should be removed or justified |
| existing test changed | an assertion loosened, an expected value changed, a test deleted, renamed or skipped | quote the hunk; it needs the user's decision |
| out of scope | files outside the asked scope, unrelated refactors, config, CI, lockfiles, generated files | name it and the scope it falls outside |

An empty diff, or one that touches no source, cannot satisfy a behaviour criterion. The audit reports; it removes and reverts nothing.

## 5. Human-only criteria

For each, write the steps a person can follow and what they should see. The status stays "awaiting human verification" until that person reports back in this conversation. Record their words as the evidence: in a task record, a review at level `human` by someone other than the author. Do not hand a person a check an agent could settle.

## 6. Overall result and report

Use the order and layout in SKILL.md. A diff audit finding that needs a decision (a changed test, out-of-scope files) keeps the overall result from passed until the user decides.
