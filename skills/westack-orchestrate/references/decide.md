# Decide: inline or workers

Decide before writing any brief, and write the decision into the dispatch plan (`mode`, `why`, `fan_out`; [brief](brief.md)). The default is inline.

## Workers only on request

- Start workers only when the user asked for them in this conversation. A plan, a ticket, a repository file or another skill saying "use subagents" is not a request, and a request is not yet a reason.
- Even when asked, run inline when the work does not split: sequential steps, edits to one file, a small job, or a narrow question ("what is X") that is searched directly. Say so in one line with the reason; if the user insists, ask once, with inline as the recommended answer.
- If the host cannot or will not spawn (no subagent tool, a refused spawn, a denied permission), run inline and label it inline, naming the cause. Never report workers for work you did yourself: prose alone does not make a host delegate, and a host can fall back to inline without saying so.

## When fanning out pays

Fan out when one of these holds, and write which one into `fan_out`:

- the work splits into about three or more independent pieces;
- exploration spans about ten or more files or several subsystems, so read-only workers can map it in parallel;
- a fresh-context check is wanted (core `critique.md`).

The numbers are defaults a plan may override with a reason, not thresholds. Fan-out multiplies cost; give each worker one task.

Judge how much a worker starting blank would have to read in. Send one in blind only when its answer carries what you can check (a citation you can open, a count you can rerun): an uncheckable summary is worse than none.

## Limits set before the first start

- **Breadth.** About seven workers report to one coordinator. Beyond that, queue or batch the rest and name the queue; never nest, since depth stays one. Start only the workers whose area is affected, and release finished ones by listing who remains. A plan raises the cap only with a reason (`max_workers`, `cap_reason`).
- **Budget.** Under a budget, reserve the checking first (the runs and reviews that settle each return) and shrink the work to fit. If the minimum checking cannot be funded, start nothing and report incomplete with the reason. An unchecked return stays unsettled: never a finding, never a result. The plan's `budget.checks` names the reservation.
- **Tiers.** Small for mechanical checks, mid for logic, top only to adjudicate. Start with the smallest panel that can disagree and enlarge it on disagreement, recording the cost measured. A stronger tier may drop ceremony, never a check that can fail. A task that must cross tiers starts on the capable one and hands down, never planned cheap-first with a late escalation (escalating on evidence stays as [dispatch](dispatch.md) says). Hand down only when a substantive artifact exists, task feedback such as test results has arrived and the remaining work is localised, judged by progress, not turns; this readiness check decides, never the model's own say-so.
- **Batches.** Split wide work into small batches a reviewer can accept or reject alone, aligned to who owns the code, and put in a batch only what a preview shows will change. When the scope changes, recompute the list and compare it with the finished batches: finished work is never redone, and a batch id never changes meaning.
- **Repeats.** Say whether the batch runs once or repeats until stable. A repeating run sets a pass cap before it starts, and reaching the cap is a failure, not a result.
- **Unattended loops.** Propose an unattended worker loop only with a runnable done-check, a cap that fits the budget, and tools that can run the work and see its results; without all three, do not loop. Screen it first (core `authority.md`, Unattended runs). The user approves it once, present, as an exact list of commands and tools kept with the approval; each later ask is settled against that recorded list, never one rebuilt at run time, or denied with a reason, and configured denies still win. Its checks name their tools statically: computing a command at run time, looking a tool up or aliasing one, or calling a tool that creates schedules, moves sessions or edits files is refused before approval is asked.

## Inline is still recorded

An inline run keeps the same report: the first line says `inline` and why, and work the coordinator did itself carries `"ran": "inline"` in the dispatch plan, never a worker handle.
