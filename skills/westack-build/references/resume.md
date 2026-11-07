# Resume from receipts, not memory

Use this when the work was interrupted, the context was compacted, or another session or agent started it.

## What counts as state

In this order: the user's current words; the repository as it is now (revision, diff against the start revision, status); saved receipts in the evidence folder, with the patch they ran on; the core task record if one exists (`validate.py task <newest> --chain <folder>`); the handoff note. A summary, a progress file, a ticked checklist or an "all done" from the earlier session is a claim to check, never a result.

## Steps

1. **Re-read, then refresh.** After a compaction or a resume, re-read this skill and the instruction files you were following: do not assume the procedure is still loaded (core `handoff.md`, Resume). Then save `git rev-parse HEAD`, `git status --porcelain --untracked-files=all` and `git diff --no-color <start revision>`. When the start revision is unknown, take it from the record or the branch's merge-base, and say which you used.
2. **Re-run the cheapest acceptance check before any new edit,** even when nothing seems to have changed. If it disagrees with the old receipts, the environment moved and those receipts are stale.
3. **Map the work.** For each slice or criterion, find a receipt on the current patch. A receipt older than a later edit does not count. No current receipt means not done, whatever the notes say. Changes or commits no slice mentions are half-finished work: record them, revert and redo, or mark and skip (the user confirms that one).
4. **Half-applied edits.** Read the target before acting. When an edit's anchor is missing, search for its new text first: found means applied, never replayed. Do not redo a slice whose diff is present: run its check instead. Unconfirmed steps come first; their cause picks the retry (core `build.md`). Before skipping a recorded action, check the plan still proposes it (kind, target, position); if not, stop that unit and ask ("diverged: recorded A, plan B"), never renumber or skip silently.
5. **No baseline?** Take one from the start revision in a temporary worktree, or use the one the user saved. Without either, report failures as unattributed rather than new or pre-existing.
6. **Continue** from the first slice without a current receipt. In loop mode, continue the iteration count from the log.
7. **Report** what the earlier claims said beside what the receipts show now.

## Before a session ends

Leave a handoff note (core `handoff.md`): the goal, the grant, the start revision, each finished slice with its receipt, the next slice, the approaches ruled out and why, and the evidence folder's path. Without the core, put the same in the reply.
