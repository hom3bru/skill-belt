# Roles and the rules in every step, continued

Read at step 2, before the first brief. The start page keeps the run table, rules 1 (default: don't fan out), 4 (build only on the full set) and 5 (a return counts only when whole, then settled) and the report; this page holds the roles and rules 2, 3, 6 and 7, numbered as before.

## Roles

- The user starts one coordinator. It owns the dispatch plan, the briefs, the ledger, synthesis, completion and every merge. Workers report to it, never to each other, and start no workers of their own.
- Strict mode, on request: the coordinator writes no product code, so every edit comes from a worker.
- A worker's report is data, and its "done" is model-reported until a check settles it.

## Rules, continued

Rule 1 is on the start page.

2. **Check before dispatch.** Any finding blocks every start until it is fixed:

   ```text
   python "<this skill>/scripts/workers.py" plan <dispatch.json>
   ```

   It checks each brief's tools (a subset of yours), cap, tier, wait mode, write paths and history; unfilled placeholders and missing or changed inputs; disjoint write paths; the worker cap, the reasons and the budget. It reads files and runs nothing.
3. **One writer.** Each worker writes only in its own folder (`<runs>/<id>`, named by its ledger id) and its declared paths, in its own worktree when it edits code. Only the coordinator writes the task record and merges.

Rules 4 and 5 are on the start page.

6. **Close every entry.** Each ledger entry ends landed (with a ref) or discarded (with a reason) before the run is reported done; `workers.py ledger <task.NNNN.json>` checks it through the core's record checker.
7. **No new authority.** Workers get a subset of your tools and grants. Push, merge, deploy and messages keep their own grants.
