# Durable runs and scheduling (C6)

Reference only: no helper ships for this facility.

- Screen a task before it runs unattended ([authority](authority.md), Unattended runs).
- Set caps before a loop starts (iterations, time or cost, consecutive failures); on any exit, write a state note ([handoff](handoff.md)). A loop is done when receipts meet the goal's criteria, never because it printed a completion marker.
- Stuck rule: about three identical results or errors from the same action end that approach (batch work over different files is no repeat); change it, or stop and report. Retry a read-only command at most twice, noting what changed; retry one with side effects only if its brief or the user says so, as one receipt counting attempts. A third distinct failure is blocked or needs a decision.
- Remote state: observe, claim, act, confirm. After an interruption, observe again before acting; an unconfirmed action is uncertain, not done.
- Timed re-checks use only a scheduler the host provides, set up by the user; westack installs none. Its jobs get an interval floor and job cap, enforced at creation. A task waiting on an outside event is waiting, not stuck: record it in `waiting_on` ([handoff](handoff.md)), and have each re-check run that check, never re-dispatch the job.
- A run ends as `finished`, `budget-exhausted`, `crashed`, `lost`, `declined`, `cancelled` or `waiting-on-person`, each with a final record. Only `finished` with receipts can pass; the others are blocked or not-run ([vocabulary](evidence-vocabulary.md)) with the reason named, and completion stays partial or blocked. Exhausting a budget is never success. `cancelled` is a stop on purpose, never resumed; routine events never overwrite a terminal or paused outcome, and an uncertain exit is paused with its reason, never done.
- A gate that can refuse "done" (a user-installed stop hook) needs a release: one refusal per stop, a small cap, or a no-progress test on state, not output bytes. A release records stopped-unfinished (completion partial), never complete; finish before the host's timeout and fail visibly.

Provenance: C6 in provenance/facility-donors.json.
