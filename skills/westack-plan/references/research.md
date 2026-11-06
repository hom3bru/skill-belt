# Research before the plan

The plan is only as good as what was read before it. Research is read-only: read, search, list, and run checks that write nothing tracked (a test run that fills a cache is fine). If the user asks for the change itself, hand over to `westack-build` rather than editing from here.

## Read in this order

1. **The request.** The issue, ticket, spec or message in full, and anything it links that is in reach. Restate the goal as what someone can do afterwards that they cannot do now, plus the non-goals.
2. **Repository instructions.** `AGENTS.md`, `CLAUDE.md`, contributing guides, codebase rules, directory-scoped rule files. They are constraints on the plan (owners, frozen paths, required checks).
3. **Decisions already made.** ADRs, decision logs, earlier plans for this area, the host's own memory, a task record's `decisions`, the issue thread. Each becomes a plan decision with its origin (user or repository) and where it was made. A recorded decision stands; if the plan needs to reopen one, that is a question for the user with the new evidence attached.
4. **The code.** The entry points, the module that changes, its callers, and its **consumers**: everything that reads what it produces. Search the whole repository (and sibling packages in a monorepo) for the symbol, route, event name, table or column, config key, file format or output path, not only for imports. Typical consumers hide in jobs and schedulers, exports and reports, other services, generated clients, fixtures and snapshots, dashboards and queries, docs and examples. Each one goes into a slice, or gets a stated adapter that keeps its contract and a check that proves it.
5. **The checks.** The project's real test, lint, type and build commands (CI configuration, package scripts, makefiles). Never assume a familiar one. If the suite is cheap, run it once and record what already fails, so the plan's acceptance does not promise a green that was never there.
6. **History.** Recent commits, reverts and open or closed pull requests in the area: an earlier attempt and why it stopped is often the most useful fact in the plan.

Write down what exists, with file:line, before proposing any change: describe first, judge later. A claim about the code that you did not read is labelled as an assumption.

## Two kinds of unknown

| Unknown | Do |
| --- | --- |
| A discoverable fact (where something lives, what calls it, which version is pinned, what a config holds) | Explore. Ask only when two candidates are equally plausible after looking, and then offer them with a recommendation. |
| A preference or trade-off (behaviour users see, scope, a policy, a compatibility promise, cost against speed) | Ask early, with two to four options and a recommended default. Without an answer, the plan may proceed on the default only as an assumption the user can see and accept. |

## Large areas

Split research across read-only subagents when the area is wide: one per subsystem, each briefed with the exact folders, the question, "read only", and a return format with file:line references (core `delegation.md`). Check their key claims yourself before they enter the plan; synthesis stays with you.

## Unknown feasibility

When reading cannot settle whether an approach works (a library's behaviour, a performance limit, a migration's lock time), make the first slice a spike: a small, labelled experiment with the question it answers, how to run it, and the criteria for keeping or discarding it. Its code is thrown away unless the plan promotes it. Before building, a multi-step plan tries each step once, the last included, with the numbers that decide it, and records a probe receipt for the last; a plan whose last step was never tried is flagged. Scale it to the request: a one-step claim gets one probe and no plan.

## What research hands to the plan

- Current state: the relevant files and how they fit, with file:line.
- Consumers: each one, where it reads the contract, and how it will be kept working.
- Decisions found, with where each was made.
- The check commands and the baseline failures, if run.
- Open questions, each with a recommended answer.
- Ruled out: each approach or belief that the reading disproved, with the evidence.
