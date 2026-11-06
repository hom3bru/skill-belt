# Tickets and trackers

A plan is not a mandate to publish. The default output is the plan in the reply or the plan file; tickets come only when the user asks for them, and anything outside the repository waits for approval of the exact set of writes.

## 1. Follow what the repository already uses

| Found | Then |
| --- | --- |
| `.beads/` | Beads is the tracker (core defer map `plan-beads`: a convention, consent first, its writes fenced). Receipts still decide done, never `bd close`. |
| `openspec/` or `.specify/` | write the tasks in that format (defer map `plan-spec-tasks`) |
| a tickets folder, a tracker note in the repository instructions, an issue template | follow it |
| none of these | local markdown tickets, below |

## 2. Local markdown tickets (the default)

One file per slice, in the repository's tickets folder, else `docs/plans/<plan-slug>/tickets/NN-<slug>.md`. New files continue from the largest existing number, in the order the dependencies allow. Header lines, then the body:

```markdown
Status: planned
Blocked by: 01, 02
Milestone: <plan-slug> M1
Plan: docs/plans/<plan-slug>.md (slice S3)

## What to build
<the behaviour that works once this is done, from the user's side>

## Acceptance
- A1 (automated): `<command>` shows <result>
- A2 (human): <what a person checks>

## Rollback
<how to undo it>

## Requirements and consumers
R2, R4; consumers: <each reader of a changed contract>
```

Describe behaviour more than file paths, which go stale; the plan keeps the paths. Writing these files is a local write: name the paths before writing, and write only inside the planning grant. Never rewrite an existing ticket's content or status; new work gets a new number.

## 3. External trackers: GitHub Issues, Jira, Linear

1. **Prepare the whole write set without sending anything:** each issue to create (exact title and body), each milestone, label and dependency link, and the target (repository, project, team). Show it as a table beside the slice ids.
2. **Pause for approval of that set.** One question naming the target and the counts ("Create 7 issues and 2 milestones in owner/repo?"). The approval covers that set on that target only; anything added or changed later needs a new one.
3. **Use what the user already has:** the `gh` command line, or a Jira or Linear connector the host provides. Install nothing, handle no credentials. With no working tool, write local tickets and say so.
4. **Create in dependency order**, so each item can point at its blockers' real ids:

   | Tracker | Dependencies | Phases |
   | --- | --- | --- |
   | GitHub | a "Blocked by" list of `#N` in the body | repository milestones |
   | Jira | "blocks" issue links | fix versions, or epics if the project uses them |
   | Linear | "blocked by" relations | project milestones |

5. **Read back** each created item, then record its native id and link beside the slice id in the plan. Milestones are named `<plan-slug> M<N>: <name>`; a native milestone number is a separate identity, recorded, never assumed from a name match.
6. **Uncertain results:** if a call fails or times out after sending, stop. List what was verified, what is pending and what is uncertain, and read the tracker before any retry, so a retry never creates a duplicate (core `durable.md`).
7. **Existing items:** never close, reopen, reassign, relabel, move, comment on or change the status of an existing item as a side effect of planning. Each such change is its own approval.

## 4. Reading tickets back

A closed issue, a Done column or a `Status: done` line is a claim made by whoever moved it. When planning from existing tickets, check each claimed-done item against its acceptance before treating it as done: a merged change that contains it and a passing run of its check. Report the ones that do not hold as claimed, not done, and keep their dependants waiting.
