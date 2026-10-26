# Build and resume

Act only within current host permissions and user scope. Make changes in authorized isolation, preserve unrelated work, and use existing tools. Capture a meaningful failing regression before correction where useful; prose/config changes need an appropriate check, not a fabricated red test. Do not weaken existing assertions.

Use bounded attempts with an explicit stop condition. A denied action remains denied across all modules. Do not change permissions, choose a different tool or broaden writes to escape it. A materially new relevant authorization/environment fact may justify a new decision only under host rules; time passing does not.

Before a mutation, record action ID, target hash, scope ID and pause occurrence when needed. Afterward distinguish applied, not-applied, uncertain and denied. A timeout is not proof of failure.

Resume checklist:
1. Refresh current user scope, source revision, patch and host capabilities.
2. Inspect the actual target/audit receipt for every uncertain action without repeating it.
3. If applied, record reconciliation evidence and do not replay. If not-applied, reassess current authority before retry. If still unknown, stop that action.
4. Reject stale responses to previous occurrence IDs, targets or scopes. A replayed event must not advance state twice.
5. Persist the next safe action and remaining blockers. Continue independent authorized work.

The helper's reconciliation recommendation is diagnostic and uses caller observations. It does not observe a remote system or make a retry safe by itself.

Reconciliation evidence must name the action as its claim and match the current revision, patch and scope. An unrelated acceptance test, unrun receipt or stale observation cannot settle an uncertain action. Keep a denied action's occurrence identity even if another record ID is proposed; renaming it cannot create authority. Historical applied actions may remain in the record after the current scope changes, without authorizing a new execution.

For a stale session or unavailable instance, distinguish a confirmed rejection before any execution from an uncertain partially executed attempt. A bounded fresh attempt is reasonable only when structured evidence shows that the rejected attempt produced no output, tool activity or effects, and current authority still permits it. Any meaningful activity requires target inspection before replay. This is guidance, not an implemented automatic provider retry.

When watching an asynchronous task, retain the typed result. A successful wait/resume command can mean attention, cancellation, owner loss, failure or validation-only acknowledgment. It does not establish that the underlying work ran. Update the task from observed work state and artifacts, then refresh the next safe action.

