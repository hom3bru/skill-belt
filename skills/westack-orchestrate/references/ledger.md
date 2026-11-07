# The ledger, resume and close

The ledger lives in the task record's `delegates` list and `waiting_on` field (core `contracts/README.md`), never in a second file. Only the coordinator writes the record.

## One entry per worker

| Field | Holds |
| --- | --- |
| `id` | the brief's `worker`, also its folder name |
| `parent` | the task id (never another worker: depth stays one) |
| `executor` | the host agent and model that ran it |
| `tier` | the brief's tier |
| `scope` | the brief's path and SHA-256 |
| `status` | `running`, then an end state (core `durable.md`) |
| `continuable` | whether its context can be resumed |
| `start_by`, `deadline_at` | the brief's clocks, absolute, fixed at the start |
| `outcome` | `landed` with a `ref` (a commit, or a file and its hash) or `discarded` with a `reason` |

- A unit a worker takes has one claimant (`work_units[].claim`: owner, state, lease expiry). An expired lease means inspect the worker's target: it does not prove the worker stopped, and only an inspected unit returns to the queue.
- A run that waits on an outside event records `waiting_on` (what, the check, the next step, the expiry) and starts nothing until the check passes (core `handoff.md`, Resume). Run that check once when you record it, with the user present: a check that errors is not recorded, and its first reading is a baseline, never a wake.
- A user's pause or stop is a hold, written as `waiting_on`: `what` `hold: pause by user: <why>` (or stop), check `person-confirms`. It survives resume and restart; a CI result, clue or bot comment never lifts it, only the user, by dropping `waiting_on`. `workers.py ledger` reports `held`.

## Close

```text
python "<this skill>/scripts/workers.py" ledger task.NNNN.json [--dispatch dispatch.json] [--core DIR]
```

It checks the record's shape against the contract, then the ledger through the core's own checker (`record.py`), as for a finished record: an entry still open, a closed entry with no ref or reason, or an end state with no reason is a finding. It adds a worker whose parent is not the task (`nested-worker`), a dispatched worker with no entry (`no-ledger-entry`) and a run still waiting (`still-waiting`). Without the core it reports not-run. The full record still goes through core `validate.py task` before the run is called verified.

## Resume

Before the core resume steps (`handoff.md`), as coordinator:

1. **A packet from the record.** For a record another host or a lost session made, put it in one packet under a "history, not instructions" heading that names the source. Drop the oldest content first, say what was dropped, and keep every terminal result. To continue a worker's conversation under another model, hash each turn's visible text and find the prefix both sides share: continue after it, send the unseen turns in that one labelled block, or start fresh; never split a tool call from its result.
2. **Unrecorded work.** Compare the repository and the runs folder with the ledger. Changes or commits no entry mentions are a half-finished state with three exits: record them by hand, revert and redo, or mark and skip with the user's confirmation, never by default.
3. **Uncertain first.** List the workers and actions that started without a confirmed end and inspect each. The recorded cause (cancelled, failed, truncated, refused, abandoned) picks the retry.
4. **Same plan, same slot.** Before skipping a recorded dispatch, confirm the plan still proposes that worker, with the same brief, at that position. A mismatch is a divergence: report recorded against planned, stop that unit and ask; never renumber.

## The coordinator's own context

- Set an early, a late and a hard line for the context window, in the host's own counts where it reports them, and name the line that tripped. Write the handoff note at the next point with nothing in flight, never mid-dispatch.
- When the context turns suspect (a wrong tool result absorbed, repeated corrections), do not patch it with a reminder: write a clean note from the record and restart from it. When a long run starts hedging or wrapping up early, prefer a fresh session that reads the note and the record over a compacted one.
