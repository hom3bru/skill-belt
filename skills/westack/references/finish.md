# Finish

Reconcile each acceptance condition as passed, failed, inconclusive, blocked or not-run using its actual evidence; an inconclusive condition is reported with what would settle it, never as passed. State concrete changes, exact checks/counts, unrun work, residual risks and delivered artifacts. Report failures against the regression baseline by name in two lists, new and pre-existing. A partial result is useful when labeled partial. A read-only design can be source-audited without runtime validation.

Keep local files, commits, pushed branches, PR creation, merge and deployment as distinct delivery states. “Finish”, “ship-ready” and green CI do not add authority for external side effects. Credentials being present does not authorize inspecting or using them. Do not acquire credentials to complete a readiness assessment.

Before a push to a branch with an open PR or to a protected target, check whether auto-merge or a merge queue is armed. If it is, the push can cause a merge nobody authorized: report it and stop. Changing that setting is itself an action that needs authority. Read delivery state back from the live target; a queued merge or an auto-merge request is not a merge.

A verified state requires current passing evidence for all required criteria and any required independent review of the same patch. A completion marker or caller assertion cannot substitute. Validation is not verification: the helper checks consistency only.

When blocked, name action, target, precise reason, completed work and whether the outcome is denied, pending or uncertain. Continue unaffected authorized work. Provide a safe next step without claiming a forbidden action happened.
