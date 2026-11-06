# The brief and the pre-dispatch check

Core `delegation.md` lists what every brief holds (purpose, scope, tools, cap, tier, wait mode, return format, a way out). This page gives the file shapes `scripts/workers.py` reads and what a brief in a batch adds.

## The dispatch plan

One JSON file per run, written and updated only by the coordinator:

```json
{
  "format": "westack-dispatch-1",
  "mode": "workers",
  "why": "user: run tickets 41-43 as parallel workers",
  "fan_out": "three independent modules, no shared files",
  "coordinator": {"tools": ["Read", "Grep", "Glob", "Edit", "PowerShell", "Agent"]},
  "plan": {"path": "docs/plans/batch.md", "sha256": "64 hex characters"},
  "budget": {"limit": "5 USD", "checks": "one mid-tier review and the unit suite per return"},
  "runs": "runs",
  "workers": [{"id": "w1", "brief": "briefs/w1.md", "handle": "set after the start"}]
}
```

`mode` is `workers` or `inline`; `why` says what the user asked; `fan_out` says which condition in [decide](decide.md) holds. `plan`, `budget`, `max_workers` and `cap_reason` are optional. `runs` is the folder of private worker folders (default `runs`). A worker gets `handle` once started, or `"ran": "inline"` for work the coordinator did itself. Paths are relative to the plan's folder unless `--repo` names a root.

## The brief

A markdown file that starts with a header block, then the prose a fresh worker needs:

```text
---
worker: w1
tier: mid
wait: report
tools: Read, Grep, Glob, Edit
removed: PowerShell, WebFetch
cap: 40 turns
start_by: 2026-10-30T09:00:00Z
deadline_at: 2026-10-30T11:00:00Z
heartbeat: 10 minutes
writes: src/billing/
history: the assignment only
plan: docs/plans/batch.md (its SHA-256)
inputs: docs/specs/billing.md (its SHA-256)
kind: build
---
```

Required: `worker` (its ledger id and folder name), `tier` (small, mid or top), `wait` (`report`: wait for the final report; `handle`: keep the handle and check later), `tools`, `cap` (a number and a unit: turns, minutes, hours or calls), `writes` (`none` for a read-only worker) and `history`. Optional: `removed`, `effort`, `start_by`, `deadline_at`, `heartbeat`, `plan`, `inputs` (several separated by `;`) and `kind` (`search`, `review` or `build`).

The body holds the purpose, the scope ("do only this"), what is known and ruled out with its evidence, a `## Done when` list with ids and a source on each line (`- D1: the billing tests pass, with the command (source: user "run the billing tests")`; a source is the user's words, a plan step as `plan S2` or a repository rule as `rule AGENTS.md`, and a brief adds no requirement none of them states), the return instructions (write `runs/w1/report.md` in [collect](collect.md)'s shape, ending with the line `END-OF-REPORT w1`), and the way out.

## What a brief in a batch adds

- **Tools.** A subset of the coordinator's `tools`, never one it lacks; a tool both listed and removed is a contradiction. Approval requests still go up to the user.
- **History.** Say what the worker gets: the full assignment plus at most a short recent window, never the whole conversation. Earlier steps go in as "earlier work said X", not as the worker's own words; a transcript passed for reading is read-only and removed afterwards. A model switch happens only at a subagent boundary, never mid-session (it breaks caching), and `history` names its direction and method: handing up, the history goes as a file the receiver can inspect; handing down, the receiver may get the conversation itself where the host allows, the one exception to the rule above (secrets still come out first).
- **Shape.** Brief by the task, not by a label on the worker. A worker known to be capable gets the goal, the reason and the requester's own words; any other, an unknown one included, gets small pieces it can check. Describe the task, never the worker: no brief calls a worker weak.
- **Inputs by path and hash.** Large material goes as a path and its SHA-256, not pasted in. A missing or changed input blocks the dispatch; it never runs blank.
- **Cut material.** A cut tool result or file keeps its cut marker, and the task text says to describe only what was kept and infer nothing about the part removed.
- **Plan stamp.** A brief built from a plan names the plan's path and SHA-256, and the report echoes them. A report built on an older hash is stale.
- **Writes.** A writer names its paths. Two workers whose paths are equal or nested, or one writing in another's folder, is a plan defect: re-split or order them before dispatch, never merge afterwards (core `isolation.md`).
- **Clocks.** `start_by`, a per-attempt `cap`, a `heartbeat`, and an absolute `deadline_at` fixed when the work starts so a resume cannot extend it ([dispatch](dispatch.md#clocks)).
- **Search workers** (`kind: search`) return three lists: found, searched with nothing found, and not searched (the next leads). Facts taken from snippets are marked unconfirmed.
- **Leaving the session.** A brief or note may reach another vendor or a person: remove secrets and private data before summarising (a summary is not redaction) and say what the receiver is given (core `guards.md`, Egress).

## The check

```text
python "<this skill>/scripts/workers.py" plan dispatch.json [--repo DIR] [--core DIR]
```

Exit 1 blocks every start. Findings: `field-missing`, `bad-tier`, `bad-wait`, `bad-cap`, `bad-id`, `duplicate-id`, `id-mismatch`, `tool-not-held`, `tool-conflict`, `placeholder` (`{{x}}`, `<x>`, `TODO`, `TBD`, `FIXME`, `[fill in]`), `no-done-when`, `duplicate-item`, `unsourced-requirement`, `no-end-marker`, `input-missing`, `input-unhashed`, `input-changed`, `writes-undeclared`, `writes-not-portable`, `writes-overlap`, `clock-format`, `clock-order`, `plan-stamp`, `plan-moved`, `no-reason`, `mode-mismatch`, `no-workers`, `too-many-workers`, `cap-without-reason`, `budget-checks`, `brief-unreadable`. Exit 2: the plan is unreadable or not this format. With the core, tier and id are read from its contract; without it they are reported not checked. The check covers structure and hashes, not whether the brief is wise.
