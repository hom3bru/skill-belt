# Slicing the work

## What a slice is

A vertical slice: the thinnest change that crosses each layer it touches (storage, logic, interface, tests) and leaves the whole system working, so it can be shown or checked on its own. Several thin slices beat one layer at a time: a plan that builds every table, then every endpoint, then every screen has nothing working until the end. Size a slice so one fresh session can finish it, and split where a reviewer could reasonably accept one part and reject the other. When workers take slices, the coordinator sizes each to one worker's budget (files, check time, context) and splits one that will not fit before dispatch; workers never pick their own slice or edit the plan.

## Order

1. **Prefactor first.** A structural change that makes the real change easy, with behaviour unchanged, is its own slice. Its acceptance is the existing suite staying as it was.
2. **The riskiest unknown early.** A spike, or the slice that proves the hard part, comes before the work that assumes it.
3. **Consumers never break between slices.** Expand, migrate, contract: add the new path beside the old one, move each consumer (one slice each when they are owned separately), then remove the old path last, in its own slice, once nothing reads it.
4. **Data changes in safe order.** Code that tolerates both shapes ships before the data changes; destructive steps come after a backup and after every reader has moved.
5. **Only true blockers.** `Depends on` names the slices that must be done before this one can start. Independent slices stay independent, so they can run in parallel.

Milestones are optional: an ordered phase with a goal stating what works after it, each leaving the product working. A slice never depends on a slice in a later milestone. One phase of work needs no milestone at all.

## What each slice carries

| Field | Content |
| --- | --- |
| id and title | a stable id (`S1`) that never changes meaning; the title says the behaviour |
| Milestone | optional |
| Depends on | slice ids, or none |
| Delivers | the requirement ids it satisfies, or none (prefactor, spike) |
| Paths | the files or folders it may touch |
| Consumers | each reader of a changed contract, and how it stays working |
| Interfaces | when a later slice relies on it: the exact names, signatures, shapes or formats it produces |
| Acceptance | criteria, each marked automated or human |
| Rollback | how to undo it, in proportion |
| Status | planned, active, done or blocked (the core task record's values) |
| Receipts | per criterion, a reference to the evidence; empty until it exists |

Write what the builder could not decide alone: files, names, signatures, the values the spec pins, the tests that prove each slice. Leave out what the signature and the test already determine. If the plan outgrows the change it describes, it has turned into the code; a line that decides nothing ("handle errors", "add tests", "TBD", a function no slice defines) is a gap.

## Acceptance

Each criterion is something a check or a person could fail.

- **Automated:** the exact command, where it runs, and what it must show: counts, an exit code, an output line, an HTTP status. For a behaviour change, name the test that fails before the slice and passes after. "Tests pass" with no command, or a criterion the current code already meets, proves nothing.
- **Human-only:** what a person checks and how: a screen, real data, a load, wording, a sign-off from an owner. Mark it `(human)`. An agent's run never passes it; it stays "awaiting human verification" until that person confirms.
- **Consumers:** each consumer of a changed contract gets a criterion of its own (its tests, a contract test, or a sample read), in the slice that could break it.
- **Known failures:** if the baseline already fails somewhere, the criterion says "no new failures against the baseline", by test name, not "all green".

## Rollback

| Change | A proportionate rollback |
| --- | --- |
| code in one commit per slice | revert that commit; the previous slice still works |
| configuration or a flag | restore the previous value or turn the flag off; say who can and where |
| schema migration | a tested down migration, or expand-contract so the old code runs on the new schema |
| data backfill or destructive data change | backup first, an idempotent re-runnable script, and the restore steps |
| a public contract (API, file format, published package) | keep the old version until every consumer has moved; a published release cannot be unpublished, so say so |
| anything irreversible | say "irreversible", and make it a step that needs the user's explicit approval when it is built |

`none` is not a rollback. "Revert the commit" is a fine one when it is true.

Write the rollback before the slice's first effect, safe if that effect never ran, and test that case. Undo runs in reverse, each step ending ran, undone or only stopped; a failed undo is partly undone, said plainly. A rollback target is the last verified revision, whose receipts stand; any other target is a new candidate. Running one (read back that the target is healthy, else failed, never reverted) is `westack-deploy`'s job (pending).

## Coverage

- Every active requirement is delivered by at least one slice. A requirement dropped on purpose is marked `(withdrawn)` with a decision-log line, never deleted.
- Every constraint and edge case the request names is carried by the slice it applies to, or explicitly deferred with the user's agreement.
- Every consumer found in research is in a slice or kept working by a verified adapter.

## Self-check before presenting

1. Coverage: each requirement, constraint and consumer maps to a slice.
2. Each slice leaves the system working, and its rollback returns it to the state the previous slice left.
3. Names and interfaces used by later slices match what earlier slices produce.
4. Every criterion could fail, and says whether it is automated or human.
5. Proportion: the plan is shorter than the code it describes.
6. Run `scripts/plangraph.py` on a written plan; fix every error, or say why one stands.

## Granularity by size

- **Tiny:** no slices. Name the change and the check.
- **Bounded:** three to eight slices in the reply, in the format above, without the living sections.
- **Cross-cutting:** the living plan file ([living](living.md)), with milestones when there is more than one phase.
