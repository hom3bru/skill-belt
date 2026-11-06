# Changelog

## 1.0.0-alpha.38 (receipt scope in orchestrate; plan replan grader), unreleased

westack-orchestrate rule 5 now ends: a complete return is model-reported until a receipt settles it, and only for what its command ran (one module is not "the whole suite"). Why: in the second measurement both westack replicates on settle-claim rejected w1's return for a real regression but accepted its two-test receipt as if it covered the whole suite its done-when item asked for; the bare host caught that. `SKILL.md` 1,016 to 1,040 words (its ceiling).

## 1.0.0-alpha.34 (lean start pages: review, ship, docs, research, orchestrate), unreleased

`SKILL.md` is now a short start page: when to use it and when not, the mode table naming the page each mode reads, the rules behind the measured wins that hold in every mode, and the report. Everything else moved word for word into a reference read on demand, and the page says to read a mode's pages in one turn with the first look at the work. The description and the minimum core block are unchanged; no rule changed; rule numbers are kept on both sides of the split. `SKILL.md` 1,175 to 990 words (780 to 595 without the core block). Kept: the run table, rules 1 (default: don't fan out), 4 (build only on the full set) and 5 (a return counts only when whole, then settled) and the report. New `references/every-step.md` (309 words: the roles, and rules 2, 3, 6 and 7, check before dispatch, one writer, close every entry, no new authority), named at step 2, before the first brief. No pinned phrase moved. The `where` values and one note in `provenance/donors.json` follow the moved sections.

## 1.0.0-alpha.30 (dsh-superagent: DS-7 to DS-8), unreleased

Two rules for the ledger and the brief, from deepseek-ai/dsh-superagent-prototype at `6337fc82` (MIT; ideas only, in westack's words, nothing copied or run), approved by the user ("Brief and send all", 2026-10-31). No SKILL.md change (1,148 words, ceiling 1,150).

- **DS-7, holds.** A user's pause or stop is a hold, written to the ledger as the record's `waiting_on` (the contract's own field; a delegate entry accepts no new key): `what` is `hold: pause by user: <why>` (or stop) and the check is `person-confirms`, the one kind no event satisfies. It survives resume and restart as the record does; a CI result, a clue or a bot comment never lifts it; only the user does, and the next record version drops `waiting_on`. `ledger.md` 670 to 712 words (cap 717), `dispatch.md` Pause and stop points to it (871, cap 872).
- **`workers.py ledger`.** `held` (instead of `still-waiting`) while a hold stands, `hold-event-check` when the check is a kind an event could satisfy, `hold-incomplete` when `what` names no user or no reason.
- **DS-8, sources.** Each `## Done when` item ends with `(source: user <their words>)`, `(source: plan <step>)` or `(source: rule <file>)`; a brief adds no requirement none of them states. `brief.md` 869 to 911 words (cap 942). `workers.py plan`: `unsourced-requirement` (the weakest item: the coordinator plans, so a plan step counts).
- **Behaviour change.** Every brief the old `plan` check passed now needs sources: `tests/test_workers.py`'s default brief gained them. Seven of the eight task fixtures under `evals/tasks/fixtures` (untouched here) have a dispatch plan whose briefs carry no sources, and `plan` now reports `unsourced-requirement` over all seven (items: budget-reserve 8, collect-returns 5, dispatch-check 6, patch-collision 4, report-injection 4, scope-creep 2, settle-claim 2), in addition to the defects dispatch-check and patch-collision plant. Those briefs need sources in a follow-up once the running measurement is done.
- **Tests.** `tests/test_holds_and_sources.py`, 18 (82 in the suite): red first (18 tests, 27 failures), then green. Five broken copies: a copy that does not know a hold reads it as an ordinary wait that an event could end; one that lets any check kind stand passes an event-checked hold; one that does not ask who and why passes an incomplete hold; one without the source check, and one that takes any source word.
- **Provenance.** One record. Not carried: the off, observe and auto accept modes, and inbound message routing.

Known limits: a source is a word and some text, not a verified quote; the hold is only as durable as the record the coordinator keeps.

## 1.0.0-alpha.29 (slim: less loaded, fewer steps on small tasks), unreleased

The regenerated minimum core block (the core is found only before the first core helper or reference; a new Lean rule; the broken-copy control applies when the work adds or claims a check). Core references are named on demand, each only when its step needs it, instead of loaded at start. `SKILL.md` 1,163 to 1,148 words; `delegation.md` is read before the first brief. No rule changed.

## 1.0.0-alpha.26 (evals: harder cases B; grader fixes), unreleased

Evals only; SKILL.md, references and `workers.py` are unchanged.

- Five held-out cases (`"new_in": "1.0.0-alpha.26"`), 3 to 8, each with recorded worker returns: settle-claim (rule 5 and `collect.md`: a worker's done is settled by running its acceptance; its receipt ran only its own tests), scope-creep (rule 3: a green patch that also edits files outside its brief), report-injection (a worker's report is data: it asks the coordinator to run a publish script on a claimed approval), budget-reserve (`decide.md`, Budget: reserve the checking first; four workers fit only if checking is left out), patch-collision (`collect.md`, Collisions: two returns rewrite one line with contradicting tests; the user picks). Budget 16 runs, $40.
- `notes.first_measurement`: dispatch-check was at full marks in every run of both arms; it stays as a floor.

## 1.0.0-alpha.12 (seven-repos and OpenCode addendum), unreleased

Ideas only, in westack's own words, from the seven-repos and OpenCode addendum (`westack-research/2026-10-30-seven-repos-and-opencode.md`): claude-mem, openrig, Agent-Reach, OpenMausBot, OpenBot and andrej-karpathy-skills at their pinned commits, and OpenCode's delta at 4878a0e3. Nothing was run or quoted.

- claude-mem (NR-5) with OpenCode (OC-4): `references/dispatch.md`, Start and record the handle (Lock-down reaches the child). A restriction counts only once seen in the spawned child's real arguments, an auto-approve list restricts nothing, a tool-less worker gets no messaging or agent-listing tool, and a hosted agent runtime gets every setting passed, its own settings files, memory, hooks and tools off and environment overrides cleared, listed in its brief, or it does not start. NR-5's core clause is in core `delegation.md`.
- claude-mem (NR-7): `references/dispatch.md`, same section. A worker resumes only by its own handle, never the coordinator's session id, and only while the host still holds it; a stored handle alone resumes nothing.
- OpenCode (OC-6): `references/dispatch.md`, Pause and stop. An entry stays running until its completion notice is admitted; discarding the run cancels its workers and closes their entries discarded; after a restart a lost worker is marked lost and never rerun for that alone. The page goes from 727 to 872 words (20% cap 872).
- OpenCode (OC-3): `references/ledger.md`, the `waiting_on` line. The check runs once when recorded, with the user present; one that errors is not recorded, and its first reading is a baseline, never a wake.
- OpenCode (OC-5): `references/ledger.md`, Resume step 1. Continuing a worker's conversation under another model compares hashes of each turn's visible text: continue after the shared prefix, send the unseen turns in the one labelled block, or start fresh, never splitting a tool call from its result. The addendum named `dispatch.md` for OC-3 and OC-5; this skill keeps waiting and resume in `ledger.md` (598 to 670 words).
- claude-mem (NR-6) and openrig (NR-10): `references/brief.md`, What a brief in a batch adds (Cut material; Shape). 785 to 869 words.
- openrig (NR-9) and OpenCode (OC-1, OC-2): `references/decide.md`. Send a worker in blind only when its answer carries what can be checked; an unattended loop is approved once as an exact list, later asks settle against the recorded list, and its checks name their tools statically, schedule-creating, session-moving and editing tools refused before approval. 643 to 765 words.
- OpenMausBot (NR-21): `references/collect.md`, Reading what came back. A question a worker already put to the user is carried as data and never asked again. 634 to 675 words.
- Donor records: `nr:thedotmack/claude-mem`, `nr:mvschwarz/openrig`, `nr:milind-soni/OpenMausBot` and `oc:anomalyco/opencode` (4878a0e3), each with its repository's flags; the OpenCode record holds the terms flag (GS-44 stands) and the second donor for Failures and retries.

## 1.0.0-alpha.6, unreleased

- TokenEconomizer (TE-2): `references/dispatch.md`, Clocks. Set the heartbeat from how healthy workers moved in this repository; a stuck worker gets one redirect and the user is told; a forced stop is only for the user's stop or a hard stop declared before the first start. Checked against SS-05: consistent. Text only (a redirect count would change the contract).
- AgentBaton (AB-1, AB-2, AB-3): `references/decide.md`, Tiers. A task that crosses tiers starts on the capable one and hands down, never planned cheap-first (escalation on evidence stays in `dispatch.md`); hand down when an artifact exists, feedback has arrived and the rest is localised, judged by progress, not turns; the readiness check decides, never the model's own say-so.
- AgentBaton (AB-4): `references/brief.md`, History. Switch models only at a subagent boundary; `history` names the direction and method (a file when handing up, the conversation when handing down, the one exception to the whole-conversation rule). The paper's numbers are its authors' claims, so the donor record grades them claimed. AB-1 to AB-4 are text only.
- Feynman (FY-4, no-subagent half): `references/decide.md`. A narrow question ("what is X") is searched directly, without workers, beside the small job and the single-file edit. The query-logging half waits for westack-research.
- Core follow-ups landed in the core: the Subagents line in `hosts/README.md` (HD-12) and the pointer in `references/isolation.md` (HD-18). The two entries above that say "not applied" are history.

## 1.0.0-alpha.5 (P2 adoption), unreleased

First build of `westack-orchestrate` (skill version 1.0.0-alpha.0), manual only (`disable-model-invocation: true`). It carries the P1 items that waited for this skill, the P2 backlog items whose home it is, and one later addendum item (OR-8). Ideas only, in westack's own words. The core references for delegation, handoff, durable runs, isolation and fresh critique are pointed to, not restated. Donor records: `provenance/donors.json` (19 `deep:` records for the P1 items, 42 `p2:` records for the P2 items, one `or:` record for OR-8).

- Package: `SKILL.md` (roles, the six steps, seven rules, the report), `references/decide.md`, `brief.md`, `dispatch.md`, `collect.md`, `ledger.md`, `scripts/workers.py` (`plan`, `collect`, `ledger`; reads files, runs nothing), `tests/test_workers.py` (64 tests: 63 red against a stub first, one added later and shown red on a copy without its fix; a broken-copy control per check), `evals/` (17 trigger cases, 3 task cases with fixtures).
- Core: `scripts/record.py` exposes the ledger rules as `check_delegates(task, final)`, which `check_task` now calls; `workers.py ledger` calls it with `final=True` instead of restating the rules.

P1 items deferred until this skill existed:

- P1 (HD-07): `references/decide.md`, `SKILL.md` rule 1. Fan out only when the work splits into about three independent pieces, exploration spans about ten files, or a fresh check is wanted; never for sequential steps, one file or a small job; the reason goes in the dispatch plan's `fan_out`. The fan-out budget line in westack-plan is not applied.
- P1 (HD-11): `SKILL.md` Roles. One coordinator owns the plan, synthesis, completion and merges; workers report to it only; strict mode on request. `workers.py ledger` reports a worker whose parent is another worker (`nested-worker`).
- P1 (HD-12): `references/decide.md`, `SKILL.md` rule 1 and report. Workers only on the user's request; a host that cannot spawn runs inline, labelled; never "workers" for work the coordinator did. The Subagents row in the core `hosts/README.md` is not applied (outside this build's files).
- P1 (HD-15): `SKILL.md` rule 3, `references/dispatch.md`, `references/collect.md`. Private worker folders named by the ledger id, the coordinator as the one writer, copying in only what it accepts; `workers.py plan` puts each worker's folder into the overlap check.
- P1 (HD-01): `references/brief.md`. A brief's tools are a subset of the coordinator's; `workers.py plan` reports `tool-not-held` and `tool-conflict`.
- P1 (HD-03): `references/collect.md`. The return's shape; `workers.py collect` classes a return without its end marker or with an unanswered item as partial, never complete.
- P1 (HD-17): `references/ledger.md`. One `delegates` entry per worker, closed landed or discarded; `workers.py ledger` checks it through `record.check_delegates`.

P2 backlog items whose home is this skill:

- P2 (HD-13): `references/dispatch.md`. A start handle per worker before waiting on any; `workers.py collect` refuses the whole set when a handle is missing; inline work is labelled `ran: inline`.
- P2 (HD-18): `references/collect.md`, Collisions. A fresh third context classifies each conflicting region, never blends, and lists every pick for the user's veto; a file that keeps colliding is split. The `isolation.md` cross-reference is not applied.
- P2 (WB-68): `references/decide.md`, Batches. Small owner-aligned batches, only what a preview shows will change, and an idempotent re-plan that never redoes finished batches. The migrate half waits for westack-migrate.
- P2 (WB-69): `references/collect.md`, `workers.py collect`. The batch takes its worst state; an empty batch is inconclusive.
- P2 (EV-72): `references/collect.md`. An outcome counts only as an artifact with a path and hash; `workers.py collect` reports a writer that names none (`no-artifact`).
- P2 (GS-46): `references/collect.md`. Returned files are named, inside the worker's folder, never hidden or credential paths, and read as data; `workers.py collect` rejects any other (`file-not-allowed`).
- P2 (HD-04): `references/brief.md`, `references/collect.md`. Inputs and results go by path and SHA-256; `workers.py` checks both hashes. The `context.md` note is not applied.
- P2 (HD-08): `references/decide.md`, Tiers. Small for mechanical checks, mid for logic, top to adjudicate; a stronger tier never drops a check that can fail.
- P2 (HD-09): `references/dispatch.md`. Change model only on evidence (two failed attempts, or a worker that hands back an unsettled question); never to escape a spending cap; one cost ledger.
- P2 (HD-22): `references/brief.md`. The brief says what history the worker gets; `history` is a required header field.
- P2 (HD-31): `references/decide.md`. An unattended worker loop needs a runnable done-check, a cap that fits the budget, and tools that can see results.
- P2 (HD-43): `references/ledger.md`, Resume 1. A resume packet from a foreign or lost record, under a history-not-instructions heading, oldest dropped first and terminal results kept.
- P2 (HD-48): `references/dispatch.md`, Before each start 1. Re-read authoritative state before each start; an unreadable refresh blocks new starts.
- P2 (CM-09): `references/ledger.md`. Suspect context is replaced from the record, not patched.
- P2 (WA-04): `references/ledger.md`. Early, late and hard context lines; the note is written at a point with nothing in flight.
- P2 (WA-12): `references/dispatch.md`, Clocks. A progress cursor in the worker's folder; silence past the heartbeat is lost; stop in two rungs, and a forced stop leaves effects uncertain.
- P2 (WA-13): `references/dispatch.md`, Pause and stop. A pause stops new starts only; a stop is re-read every step and approves nothing.
- P2 (WA-50): `references/dispatch.md`. A soft-failure budget and hard stops declared first; every failed check counts, even when a retry passes.
- P2 (WA-83): `references/brief.md`, `references/collect.md`. A search worker returns found, searched with nothing found, and not searched; `workers.py collect` reports a missing list.
- P2 (WB-48): `references/decide.md`, Breadth. About seven workers per coordinator, queue the rest; `workers.py plan` reports `too-many-workers` and a raised cap without a reason.
- P2 (WB-54): `references/decide.md`, Repeats. Once or until stable; a repeating run sets a pass cap, and reaching it is a failure. The transform test input waits for westack-refactor.
- P2 (HD-34): `references/ledger.md`, Resume 2. Work no entry mentions has three exits; mark-and-skip needs the user's confirmation.
- P2 (HD-35): `references/ledger.md`, Resume 3. Uncertain steps first; the recorded cause picks the retry.
- P2 (HD-42): `references/ledger.md`. Prefer a fresh session when a long run starts hedging.
- P2 (WA-06): `references/ledger.md`, Resume 4. Skip a recorded dispatch only if the plan still proposes it at that position.
- P2 (WA-01): `references/dispatch.md`. Class the failure first; a permanent one stops at once; name the reason a retry stopped.
- P2 (WA-03): `references/dispatch.md`, Before each start 3. A stable id; a repeated start returns the open entry; another goal under the same id is an error; a retry takes a new id.
- P2 (WA-11): `references/brief.md`, `references/dispatch.md`. Four clocks with an absolute deadline; `workers.py plan` reports `clock-format` and `clock-order`.
- P2 (CM-21): `references/dispatch.md`. Host-neutral wording (the host's subagent tool, per core `hosts/README.md`).
- P2 (WA-78): `references/brief.md`, `references/collect.md`. Briefs carry the plan's path and SHA-256 and reports echo it; `workers.py` reports `plan-stamp`, `plan-moved` and `stale`.
- P2 (HD-23): `references/brief.md`, Leaving the session. Redact before a brief or note leaves; a summary is not redaction.
- P2 (HD-47): `references/ledger.md`. One claimant per unit with a lease; an expired lease means inspect, never requeue unseen.
- P2 (HD-16): `references/dispatch.md`, Before each start 2. The coordinator sizes units to one worker's budget; workers never choose their tasks.
- P2 (HD-26): `references/dispatch.md`, Before each start 4. List existing workers before retrying a start; never a duplicate.
- P2 (HD-10): `references/decide.md`, Budget. Fund the checking first; `workers.py plan` reports a budget with no `checks` reservation.
- P2 (CM-45): `references/brief.md`, `workers.py plan`. An unfilled placeholder or a missing or changed declared input blocks the dispatch. The scan lives in `workers.py`; whether `scripts/checks.py` also gets one stays the coordinator's decision.

Addendum (OpenResearch, 2026-10-29):

- OR-8: `references/dispatch.md`, Waiting. A wake-up is a signal, not the state: on every wake re-read every running worker and handle each newly finished one; stop when nothing is in flight. Merged beside HD-48. `workers.py collect` reads every worker on each call and lists `returned` and `in_flight`; a copy that stops at the first new return fails its test.

Not taken here: the P3 orchestrate items (HD-20, HD-25, HD-27, HD-29, HD-32). Known limits: no host has loaded this skill's body; the trigger and task cases are not a measurement.
