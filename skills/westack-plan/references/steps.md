# Planning steps 1 to 3, and rigour

Read for every size but tiny, before proposing. Then [publish](publish.md).

## Rigour

**Rigour is a separate choice.** Size follows scope; rigour follows the cost of being wrong. When a wrong plan would be expensive, hard to undo and invisible from inside, add research before freezing it and a review by someone other than its author (`westack-review`, document mode), and write that reason into the plan; importance alone ("it's central") is not a reason.

## 1. Research before proposing

Read first, ask second ([research](research.md)). The request in full; the repository's instructions; the decisions already made (ADRs, decision logs, earlier plans, the host's memory, a task record); the code to change, its callers and its **consumers**: everything that reads what it produces (clients, jobs, exports, reports, schemas, generated code, docs). Search the whole repository for the symbol, route, table, field or file format, not only imports. Find the project's real check commands. Write down what exists, with file:line, before proposing anything.

Explore what can be discovered; ask only about preferences and trade-offs, each with a recommended answer.

## 2. Keep decisions apart from steps

- **Product choices** (what users see, scope, policy, compatibility promises, anything costly to reverse) belong to the user. An open one is a question with a recommended answer; a slice that waits on it is blocked and says why. Proceed past it only on an answer or an assumption the user accepted, written down as such.
- **Implementation choices** are the planner's, made from the code with evidence. Record alternatives only when the trade-off changes the result.
- A decision already recorded stands. Reopen it only with new evidence, as a question to the user.

## 3. Slice

Vertical slices, each the thinnest change across the layers it touches, that leaves the system working and can be shown or checked alone ([slices](slices.md)). Prefactoring first, the riskiest unknown early, consumers never broken between slices (add beside, migrate, then remove). Every slice carries: a stable id, what it delivers (requirement ids), its dependencies, its paths, the consumers it touches, its acceptance and its rollback. The plan opens with the outcome the user will see, and each slice says in one line how it serves that outcome; a slice whose line only restates its own mechanism is cut or flagged as drift.

- **Acceptance** is something a check or a person could fail. *Automated*: the exact command and the observable result (for a behaviour change, a test that fails before and passes after). *Human-only*: what a person checks; only that person's confirmation passes it.
- **Rollback** in proportion: revert the slice's commit for code; a down migration, backup or expand-contract for data; a flag for behaviour; "irreversible" said plainly, with the approval it needs at build time.
- **Coverage**: every active requirement is delivered by a slice; every consumer is in a slice or kept working by a verified adapter.
- **A blind second plan** (large or architectural change only; propose it, never impose it): a fresh-context planner given only the request drafts its own; list the disagreements as decisions, each with a recommendation, and build only after the user chooses (core `critique.md`).
