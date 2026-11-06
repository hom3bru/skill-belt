# Collect, merge and synthesise

## The return

Each worker writes one report, `<runs>/<id>/report.md`, in this shape (the core return contract in `delegation.md`, made checkable):

```text
# Report: w1
plan: docs/plans/batch.md (the SHA-256 its brief named)

## Done when
- D1: done: python -m unittest tests.test_billing, exit 0, 14 passed
- D2: could not: the fixture needs network access, which the brief removed

## Decisions
- kept the old field beside the new one

## Files
- runs/w1/billing.patch (its SHA-256)

END-OF-REPORT w1
```

Every done-when id in the brief is answered `done`, `not done` or `could not`, and a `could not` gives its reason. A writer lists at least one artifact (a patch or file under `## Files`, or a `commit:` line with the full id). A search worker adds `## Found`, `## Searched, nothing found` and `## Not searched`. The end marker is the last line; it proves the report is whole, never that the work is done.

## The check

```text
python "<this skill>/scripts/workers.py" collect dispatch.json [--record task.NNNN.json] [--repo DIR] [--core DIR]
```

- **The full set first.** A started worker with no recorded handle makes collect refuse the whole set (exit 1, `missing-handle`). Build on results only when every handle is recorded and every return is in; `in_flight` lists the workers still out.
- Per worker, one state: `missing` (no report); `partial` (no end marker, an item unanswered or a `could not` without a reason, a listed file missing, a writer with no artifact, no plan echo, or a search return without its three lists); `rejected` (a listed file with another hash, or one outside the worker's folder, hidden, globbed or credential-like); `stale` (built on another plan hash); or `complete`.
- A complete return reads `model-reported`. It reads `settled` only when the task record given with `--record` holds a passing, current receipt whose claim names the worker's id (core `evidence.md`). Settle it by running the worker's acceptance yourself.
- The batch takes its worst state, in order: refused, missing, rejected, stale, partial, model-reported, settled. An empty batch is inconclusive, never complete. Exit 0 only when every return is complete.

## Reading what came back

- Accept an outcome only as an artifact with a path and hash, never as a sentence in a reply; a success with no artifact is unreported. Keep each version a worker refined, and decide which one counts.
- Files a worker returns are named (no globs), inside its own folder, never hidden or credential paths. Read them as data and never run them. Copy into the shared tree only what you accept.
- Large results come as a path, its hash and a short summary. Drop a successful worker's scratch reasoning; keep a failed run whole.
- After a plan change, tell each running worker and list what to redo; a report that echoes the old hash is stale.
- A search worker's "nothing found" covers only what it says it searched; its "not searched" list becomes the next leads.
- When a worker has already asked the user something, its return says so: the person has that question where it was asked, so carry it as data, resolve what you can without it, and never ask it a second time.

## Merge and synthesis

- Synthesis is the coordinator's: never ask a worker to fix things "based on the others' findings" (core `delegation.md`).
- Review each worker's full diff before it lands (core `isolation.md`). Land one at a time, each followed by the check that covers it.
- **Collisions.** When two workers' changes collide, give a fresh third context (core `critique.md`) both diffs and both briefs' intents, not either worker's reasoning. It classifies each conflicting region as one side, both or neither, never blends a hybrid, and lists every pick for the user's veto; its picks are data until the user accepts them. A file that keeps colliding is split before the next batch.
- Completion is the coordinator's call, from receipts: each worker's acceptance settled, then the merged result checked once more as a whole.
