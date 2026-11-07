# Planning steps 4 to 7

Read after [steps](steps.md), before presenting a plan. The start page keeps the id rule and "done never comes from ticket text".

## 4. Check the plan

Before presenting a written plan, run the read-only checker (standard library; it runs nothing and writes nothing):

```text
python "<this skill>/scripts/plangraph.py" <plan.md | task.NNNN.json> [--previous <earlier plan>]
```

It reports structural gaps (cycles, missing dependencies, slices without acceptance or rollback, an automated command that cannot fail (`echo ok`), uncovered requirements, "done" without a receipt), the dependency order and the ready set; `--previous` reports ids that vanished or changed meaning. Exit 0 clean, 1 findings, 2 unreadable or not in this format. It checks structure, not truth. For a plan kept only in the reply, or in another format, apply the same checks by hand and say so.

## 5. Present, pause, then publish only what was approved

Present the plan with the open questions first. A plan is not a mandate: creating or changing anything outside the repository (issues, milestones, labels, comments, status) waits for the user's approval of that exact set, on that target ([trackers](trackers.md)). Local markdown tickets are the default. Never close, reassign or mark done an existing ticket.

## 6. Keep it living

A multi-session plan is updated as the work moves ([living](living.md)): progress with its receipts, surprises with evidence, options ruled out and why, an append-only decision log, deviations. Work found mid-task and ids: the start page's rule. A plan kept in another format is updated in that format; offer a conversion, never impose one.

## 7. Hand off

Implementation goes to `westack-build` (slice mode), test-first slices to `westack-tdd`, each when installed; otherwise say which is missing and leave the plan as the hand-off. Hand over one ready slice at a time with a short note, not the whole conversation: the plan's path and SHA-256, the slice id, its acceptance and rollback, the authority granted, and what was ruled out ([living](living.md#hand-off)). Critique of an existing plan is `westack-review` (document mode).
