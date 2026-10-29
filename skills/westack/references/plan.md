# Plan

Select the smallest coherent authorized change. For a multi-step task record work units, dependencies, allowed paths, acceptance conditions, checks and a proportional rollback. Include affected consumers or explain a verified adapter that preserves their contract. Use one workflow owner and one task record.

Separate product choices from implementation steps when they remain unresolved. Reuse approved design decisions; do not reopen them without evidence. Record alternatives only when their tradeoff affects the result. A tiny correction need not acquire a planning document.

In a task record, a work unit may name its `acceptance_ids` and a `rollback`; material choices go in `decisions` (question, choice, alternatives, origin, status, supersedes). A later choice supersedes an earlier decision rather than rewriting it.

An action's authority is bound to its scope, kind, target/patch and occurrence. A local-edit plan does not authorize remote writes; a plan approved for one target does not authorize a changed action. Preserve forbidden actions across Build, Verify and Finish.

Task record work_units form a dependency graph. The validator catches missing dependencies, cycles, unknown acceptance links and work-unit paths outside the record's allowed paths, but cannot establish that a plan includes every real caller. Confirm that through source inspection and an integration path.

