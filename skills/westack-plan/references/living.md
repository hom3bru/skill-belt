# The living plan

Use a plan file when the work spans sessions or agents, has more than one phase, or the user asks for one. Put it where the repository keeps plans (look for `docs/plans/`, `PLANS.md`, an existing plans folder); if there is none, propose a path and use it once the user agrees. Never inside a skill folder. Writing it is a local write the planning request covers; say the path. A plan that already exists in another format is updated in that format, with the same rules (receipts, ruled out, decision log); converting it to the format below is an offer, not a default.

## Self-contained

A fresh context holding only this file and the repository must be able to continue: the goal and non-goals, the authority, the current state with file paths, the decisions, the slices, and the next ready slice. Before a pause, apply the cold-resume test from the core handoff reference: could someone state the goal, the authority, the state, the next action and what was ruled out from this file alone?

## Format

`scripts/plangraph.py` reads this format; keep the headings and field names. Sections it does not read are for people.

```markdown
# Plan: <the change, in a few words>

Goal: <what someone can do afterwards, and how to see it working>
Non-goals: <what this plan will not do>
Authority: <what the user granted: plan only; local edits in these paths; tracker writes approved on DATE>
Plan status: draft
Revision: <the git revision the research read>

## Requirements
- R1: <requirement> (source: <issue, spec section or message>)
- R2 (withdrawn): <a dropped requirement stays, marked, with a decision-log line>

## Decisions
- D1 [product, open]: <question>. Recommended: <answer>. Options: <a>, <b>.
- D2 [implementation, repository]: <choice>, because <evidence, file:line>.
- D3 [product, assumption]: <the default the user accepted as an assumption>.

## Milestones
- M1: <name> - <what works or can be shown after it>

## Context
<what exists now, with file:line; the consumers and how each reads the contract; the check commands and baseline>

## Slices

### S1: <behaviour, as a title>
- Milestone: M1
- Depends on: none
- Delivers: R1
- Paths: src/billing/money.py, tests/test_money.py
- Consumers: src/billing/receipt.py (calls format_total), reports/monthly.sql (reads the amount column)
- Acceptance:
  - A1 (automated): `python -m unittest tests.test_money -v` shows test_euro_suffix failing before and passing after
  - A2 (human): the finance owner confirms the March invoice sample
- Rollback: revert the slice's commit; no data or schema touched
- Status: planned
- Receipts: none

## Progress
- [2026-10-28 14:10] S1 done: A1 receipt E3 (`python -m unittest -v`, 12 executed, 0 failed, rev 4f2a9c1); A2 confirmed by Dana
- S2 partly done: parser accepts both shapes; remaining: the writer

## Surprises and discoveries
- <what was unexpected>. Evidence: <output line, file:line>

## Ruled out
- <option or hypothesis>: <the evidence that killed it>

## Decision log
- 2026-10-28 D4 supersedes D2: <new choice>, because <evidence>; agreed by <user>

## Deviations
- S2 changed <what>, unlike the plan, because <why>
```

A `Paths` entry may carry its operation in parentheses (`src/a.py (replace)`): add or extend, versus replace, remove, rename or migrate. The checker warns `overlapping-paths` for two unfinished slices that no dependency orders and whose paths overlap (equal, nested, or a glob reaching the other), repeating the operations. That is a plan defect to fix before dispatch by narrowing, ordering or merging, not a conflict to merge afterwards; the claim coordinates writers and does not isolate them.

Field rules the checker enforces: slice ids are unique and never renumbered; `Depends on` names slice ids only; `Status` is planned, active, done or blocked; each acceptance line is `<id> (automated|human): <text>`, and an automated one names, in backticks, a command that can fail (`echo ok` is an error); `Receipts` pairs criteria with references (`A1=E3; A2=human: Dana, 2026-10-28`, or one sub-item per criterion). `Plan status: approved (<who>, <date>)` records the user's approval and is wrong while any decision is open.

## Keeping it current

- **At every stopping point**, update Progress: what is done (with the receipts it rests on), what is in flight, what remains. Split a half-done slice into done and remaining rather than ticking it.
- **Surprises and discoveries:** anything unexpected that shaped the approach, with a short piece of evidence.
- **Ruled out:** each option or hypothesis eliminated, with the evidence that killed it. A summary keeps conclusions and drops eliminations; this section is where they survive.
- **Decision log:** append only. A changed decision is a new entry that supersedes the old one by id; history is never edited. A product decision changes only with the user.
- **Deviations:** where the build departed from the plan and why, kept apart from defects.
- **Work found mid-task** becomes a new slice with `Found during: S3` in its text, and needs the user's agreement if it adds scope. The current slice does not quietly grow.
- **Revise loop:** revising against critique stops after five rounds unless the user sets another cap. End each round with `round N: unresolved U, new W`; it has stalled when `U` has not fallen for two rounds, read from those lines. At the cap, on a stall, or when a round finds nothing new, stop as needs-decision and ask the user. A result reached at the cap is inconclusive, never clean (core `critique.md`).
- **Identity:** an id keeps its meaning across re-plans; a milestone keeps its name. Dropped work is marked `(withdrawn)`, not deleted. Run `plangraph.py new.md --previous old.md` after a re-plan: it reports removed, retitled and reopened slices and removed requirements.
- **No reopening:** a done slice stays done. Done means done with receipts: if such a slice later fails its check, add a new slice that cites it (`Retry of: S3` in its text), keep S3 as history, and give the retry to a fresh context that re-derives its own checks instead of reusing S3's receipts. A slice marked done without receipts was never done, so there is nothing to retry: it keeps its id, its status goes back to active or planned, and the failing check goes in Surprises (`plangraph.py` reports a retry of it as `retry-of-unreceipted`).
- **Convergence pass:** compare the code with the requirements and slices, and append what is left as new slices that cite the requirement and a gap type (missing, partial, contradicts or unrequested), never renumbering. A pass that finds nothing writes nothing.

## Done comes from receipts

A slice is done when every criterion has a receipt: a passing run of its command at the current revision (command, exit code, counts), a task-record evidence entry that the core validator accepts, or, for a human-only criterion, that person's confirmation with who and when. The plan holds the reference; the evidence lives in the task record, the evidence folder or the reply's receipts table.

A status line, a ticked box, a closed issue, a Done column, a "COMPLETE" in a progress file or another agent's summary is a claim. On resume, before building on a slice another session marked done, re-run its cheapest acceptance check; if it fails, the slice is not done, whatever the plan says, and the discovery goes in Surprises.

## With the core task record

For recorded work (core `handoff.md`), the plan and the record describe the same work, and the record is authoritative for receipts:

| Plan | Task record |
| --- | --- |
| slice | `work_units[]`: id, goal, depends_on, allowed_paths, status, acceptance_ids, rollback |
| acceptance (automated, human) | `acceptance[]` with `verifier` agent or human |
| decisions | `decisions[]`: question, choice, alternatives, origin, status, supersedes |
| ruled out, surprises | `observations[]`: kind ruled-out or surprise, with evidence ids |

`plangraph.py task.NNNN.json` reads the record's work graph (ready set, claimed-done units, missing acceptance or rollback); `validate.py task` checks the rest.

## Hand-off

Hand over one ready slice at a time, so the next context loads the plan, not this conversation:

- the plan's path and SHA-256, and the slice id; the report echoes both, and one built on another hash is stale: tell each running delegate when the plan changes, and list what to redo;
- the slice's acceptance (automated and human) and rollback, quoted;
- the authority granted for building it (paths, and whether commits, pushes or tracker updates are allowed);
- the decisions it depends on, and what was ruled out that bears on it;
- the check commands and the baseline failures.

`westack-build` takes a slice in slice mode; `westack-tdd` takes a slice the user wants test-first. Each returns receipts, which update Progress and Receipts here.

## Resume

1. Read the whole plan and run `plangraph.py` on it. Compare its SHA-256 with the one the last pause or hand-off recorded: a plan that changed since is refused until the Decision log holds an amendment with the old and new hashes and the slices it changes, and finished slices it touches are untrusted until their cheapest check is re-run.
2. Re-run the cheapest acceptance check of the last slice marked done (core handoff resume).
3. Reconcile the plan with the repository: files the plan names that moved, slices marked active that no session holds.
4. Continue from the ready set.
