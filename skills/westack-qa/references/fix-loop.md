# Fix loop

Only when the user asks QA to fix what it finds, and only inside an edit grant that names the paths. Commits need their own grant; without one, each fix stays as an uncommitted change listed in the report. Run a report-only pass first: the fix loop works from its `report.json`.

## Triage

Sort confirmed issues by severity. By default fix critical and high; medium and low only when the user chose that tier. Mark as `deferred` what cannot be fixed from this repository (a third-party widget, infrastructure, content someone else owns) and what is outside the grant.

## For each issue, in severity order

1. **Reproduce and find the cause.** Reproduce it once more and name the responsible lines. A cause you cannot see after one attempt goes to westack-debug (diagnose mode); the issue stays open.
2. **Regression test first.** Where the project has a test runner, write a new test in its style that fails on this defect, and run it to see it fail for the defect's reason (westack-tdd's red-run rule). No runner, or a defect only a browser can show: browser evidence stands in, and the report says the test is missing.
3. **Smallest fix.** Edit only the responsible files. No refactor, rename or feature on the side.
4. **Re-test.** The new test, the original browser probe and the nearest happy path. A failed or unavailable re-check leaves the issue unresolved: try one revised fix, otherwise undo this run's edit.
5. **Commit (with a grant).** One commit per verified fix, holding the fix and its test and nothing else.
6. **Classify.** `verified` (re-test passed), `best-effort` (applied, not fully re-checked, and why), `reverted` (undone; the test and evidence kept, the issue deferred) or `deferred`. Never discard the user's own changes.

Record each fix in the report's `fix_loop.fixes`: the issue, status, files, test, commit (if any) and re-check evidence.

## Stop and ask

`python scripts/qacheck.py loop report.json` applies the rule from `thresholds.json`:

- check in with the user every 5 fixes and after any revert;
- stop after two reverts, after any edit to a file unrelated to its issue, or when two fixes in a row each touch more than five files;
- stop when only low issues remain;
- stop at 50 fixes whatever remains.

Test-only commits do not count as fixes.

## Final QA

Re-check every page a fix touched and its neighbours, and recompute the score. Report the score before and after; a worse score or a broken happy path is the first line. A blocked or inconclusive re-check never verifies a fix.
