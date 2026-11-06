# Workspace isolation (C3)

- Detect isolation before creating any. An existing worktree, host sandbox or disposable copy may already be in use (`git worktree list`, the host's own worktree feature). Prefer the host's native isolation; otherwise create a git worktree and run the baseline in it first.
- One writer per worktree. Read-only investigators may run in parallel; each writer gets its own worktree and declares its write paths (`work_units[].allowed_paths`): check prefix overlap, and an unreadable declaration is unknown, not conflict-free.
- Before merging a worker's branch back, show the full diff and review it. Nothing lands unseen. For workers run by `westack-orchestrate`, its `references/collect.md` adds their private folders, what may be copied in, and how a collision between two workers is settled.
- Before a risky or destructive edit, make a restore point the host supports (a scratch-branch commit, a stash, a host checkpoint). Label it full, degraded, failed or skipped, with what it cannot restore; mark a step applied only after its check passes, and let failure restore. Restoring re-proposes the old state; it never replays recorded actions.
- Before a bulk rewrite or history change, the tree is clean or a restore point is named (history: also a disposable clone matching the remote). A failed condition stops the run before any write, with its reason (`tree dirty: 3 paths`); paths dirty before the task are never stashed or reset to pass. A heuristic: it cannot show the restore point or clone is intact.
- Gate a restore. Refuse it when later commits exist (name them), when the point is not this task's or is already pushed, or when it is unclear which step to rewind to; only an explicit grant for that destructive action overrides the refusal. Otherwise preview the effect per path, name every deletion, delete only what you can bring back, and report what was undone: the files, the conversation or both.
- Clean up only what this task created and recorded as owned, and only after its evidence is saved outside the disposable state; refuse a dirty, unpushed or question-holding workspace, and never clear a non-empty directory you did not make. The user's own recovery rules override this page.
- An unavailable required worktree blocks the writes that depend on it, not safe reads.

Snapshot helpers and shadow repositories belong to the host; westack installs none.

Provenance: C3 in provenance/facility-donors.json.
