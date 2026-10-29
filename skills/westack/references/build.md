# Build and resume

Act only within current host permissions and user scope. Make changes in authorized isolation, preserve unrelated work, and use existing tools. Capture a meaningful failing regression before correction where useful, snapshotting the file before and after the fix (see Verify) so the red receipt stays valid; prose/config changes need an appropriate check, not a fabricated red test. Do not weaken existing assertions.

Writes to scripts, build steps, package-manager hooks, git hooks, CI configuration, shell startup files or shared directories are deferred execution: they can run later outside current authority, so they need explicit scope even inside the allowed paths.

Use bounded attempts with an explicit stop condition. A denied action remains denied across all modules. Do not change permissions, choose a different tool or broaden writes to escape it. A materially new relevant authorization/environment fact may justify a new decision only under host rules; time passing does not.

Before a mutation, record action ID, target hash, scope ID and pause occurrence when needed. Afterward distinguish applied, not-applied, uncertain and denied. A timeout is not proof of failure.

Resume checklist:
1. Refresh current user scope, source revision, patch and host capabilities.
2. Inspect the actual target/audit receipt for every uncertain action without repeating it.
3. If applied, record reconciliation evidence and do not replay. If not-applied, reassess current authority before retry. If still unknown, stop that action.
4. Reject stale responses to previous occurrence IDs, targets or scopes. A replayed event must not advance state twice.
5. Persist the next safe action and remaining blockers. Continue independent authorized work.

`validate.py reconcile <task.json> --root <evidence-root> --action <id> --observed applied|not-applied|unknown` turns your observation of the target into a diagnostic recommendation (`do-not-replay`, `inspect-without-replay`, `refresh-authority-before-retry`, `stop-denied`, or `report-unauthorized-effect` when an effect appeared without an approved decision; report that to the user). It does not observe the target, check approvals or make a retry safe.

Reconciliation evidence must name the action as its claim and match the current patch and scope. An unrelated acceptance test, unrun receipt or stale observation cannot settle an uncertain action. Keep a denied action's occurrence identity even if another record ID is proposed; renaming it cannot create authority. Historical applied actions may remain in the record after the current scope changes, without authorizing a new execution.

For a stale session or unavailable instance, distinguish a confirmed rejection before any execution from an uncertain partially executed attempt. A bounded fresh attempt is reasonable only when structured evidence shows that the rejected attempt produced no output, tool activity or effects, and current authority still permits it. Any meaningful activity requires target inspection before replay. This is guidance, not an implemented automatic provider retry.

When watching an asynchronous task, retain the typed result. A successful wait/resume command can mean attention, cancellation, owner loss, failure or validation-only acknowledgment. It does not establish that the underlying work ran. Update the task from observed work state and artifacts, then refresh the next safe action.

## Numbered records and refresh

Save each record version as a new file (`task.0001.json`, `task.0002.json`, …); never edit a saved version. Two helpers write the next number by exclusive create and run nothing:

- `validate.py receipt <task.N.json> --root <evidence-root> --repo <repo> --id <id> --claim <criterion> --type unit --operation "<command as run>" --environment "<tool versions>" --raw <output> --artifact <tested file> --passed N --failed N --exit N --expected-exit N` appends one receipt. It snapshots the artifact, hashes the raw output, takes patch and scope from the record after checking the repository still matches (otherwise it tells you to refresh), and derives `collected`, `executed` and the status from the counts. Repeat `--claim` when one run backs several criteria; `--control <id>` names its failed broken-copy receipt; `--link` points the named acceptance criteria at the receipt.
- `validate.py refresh <task.N.json> --root <evidence-root> --repo <repo>` re-observes patch and revision. Passed receipts whose patch or scope changed become `stale`; criteria that relied on them become `not-run`; verification resets (verified → implemented, delivered → inspected); pending or unapplied approvals from an old scope become `stale`; a history event records why. Failed receipts stay failed: they are history, and a red run can still serve as a control. A new commit with the same content changes only the revision. Add `--scope <new> --reason "<why>"` when authority changed; with it, `--relax <id>` makes a criterion optional, drops a work unit or review, or (`independent-review`) drops that requirement. `--grant <kind> --reason "<why>"` records an action the user granted within the scope.

Check the newest with `task --repo --chain <folder>`, which checks every numbered version against its predecessor (`--previous <file>` checks one pair). Writing a version by hand follows the same rules: a receipt may only become `stale`, and only once its patch or scope differs; findings, requirements, decisions, acceptance criteria, unfinished work units and reviews are never removed; adjudication moves only forward (open → accepted, rejected, deferred or fixed; accepted → deferred or fixed; deferred → fixed); and finish conditions only get stricter within a scope.

Collect acceptance receipts on the final patch. Any later edit makes earlier receipts stale, so per-unit runs are working checks; re-record them at the end.

