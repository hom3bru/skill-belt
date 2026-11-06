# Dispatch and the clocks

Start workers one at a time from a plan that `workers.py plan` passed. The core's caps, stuck rule and end states (`durable.md`) apply to each worker; this page adds what running several at once needs.

## Before each start

1. **Re-read the state.** Just before starting each worker, read the authoritative state of every unit again (the task record, the plan, git) and skip a unit that is now finished, unroutable or gone. A refresh you cannot read blocks new starts; it never counts as "no change". Nothing held only in memory survives an interruption.
2. **Size the unit.** The coordinator cuts the work into units from a checked survey and sizes each to one worker's budget (files, check time, context); a unit that will not fit is split before dispatch. Workers never choose their own task or edit a shared to-do list.
3. **Ledger entry first.** Write the worker's `delegates` entry ([ledger](ledger.md)) before starting it, under a stable id: the brief's `worker`, which is also its folder name. Starting the same id again returns the open entry; the same id with another goal is an error naming both; a retry takes a new id that cites the old one.
4. **No duplicates.** Before retrying a start, list the workers the host already has. Accepted is not running, and an idle worker may still be working: never start a second copy, and "still running" must point to a tracked job.

## Start and record the handle

Spawn each worker with the host's subagent tool, given its brief only (core `hosts/README.md`, the fresh-reviewer row, names the setting per host). Record its start handle (the host's agent or task id) in the dispatch plan as `handle` before waiting on any worker. A handle shows that a worker started, not that it ran in parallel, honestly or isolated. Resume a worker only by its own handle, never the coordinator's session id, and only while the host still holds it; a stored handle alone resumes nothing.

**Lock-down reaches the child.** A restriction (tool list, denied tool, a mode refusing unapproved calls) counts only once seen in the spawned child's real arguments; an auto-approve list restricts nothing. A tool-less worker gets no messaging or agent-listing tool: messaging a session with tools borrows its authority. A hosted agent runtime gets every setting passed explicitly, its own settings files, memory, hooks and tools off and environment overrides cleared, listed in its brief; without the host's tools, it does not start.

## Waiting

A wake-up (a completion notice, a message, a timer) is a signal, not the state. On every wake, re-read every running worker's folder and ledger entry, and handle each worker that has newly finished, not only the one the wake named; two can finish while you read the first. `workers.py collect` reads every worker on each call for this reason. Stop waiting when nothing is in flight.

## Clocks

- `start_by` passes with no start: the worker never started. Reroute it or report it; it is not slow.
- `cap` bounds one attempt; `deadline_at` bounds the worker overall and never moves later.
- Heartbeat: the worker keeps a progress cursor, `<runs>/<id>/progress.md`, in its own folder. Set the heartbeat from how healthy workers' cursors moved in this repository and note that baseline in the plan; before one is learned the heartbeat is a guess. Silence past the heartbeat marks it lost, and the next attempt resumes from the cursor. A worker that is still working but stuck (its cursor repeats) gets one redirect saying what to change, and the user is told.
- Stop in two rungs: ask the worker to stop, then force with a reason, only on the user's stop or a hard stop declared before the first start. Never on your own reading of a stuck turn: that gets the one redirect, then the user's call. A forced stop leaves the worker's effects uncertain until inspected.

## Failures and retries

- Class each failure first: transient, intermittent or permanent. A permanent one stops at once. Otherwise stop at the first of: not retryable, attempts used, the wait would pass `deadline_at`, no retry policy. Name the reason that stopped it.
- Before the first start, declare the run's soft-failure budget and its hard stops. Count every failed check against the budget, even when a retry later passes; a hard stop (a missed deadline, a denied grant) ends the run at once.
- Change tier or model only on evidence: after two failed attempts, or when a worker says the evidence cannot settle its question and hands back what it found. Switch model for an outage, never to escape a spending cap, and keep one cost ledger for the run.

## Pause and stop

A user's pause stops new starts only. In-flight workers keep going, their actions read uncertain until inspected, and the clocks keep running; record the hold ([ledger](ledger.md)). A user's stop is re-read at every step, ends the run, and approves nothing.

A worker's entry stays `running` until its completion notice is admitted. Discarding the run cancels its workers and closes each entry discarded; after a restart, mark a lost worker `lost` and never rerun it for that alone.
