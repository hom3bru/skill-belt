# Constructing a candidate

This reference applies when the user authorizes implementation or a concrete design.

Use a small decision contract:

- Input schema and source information accessible at decision time.
- Output schema, error/abstention behavior, and intentional semantic changes.
- Preconditions and applicability predicate.
- State read/written, external effects, authorization, and recovery.
- Proposed algorithm and its reason for generalizing.
- Preservation cases, falsifier, and independent evaluation route.
- Runtime/model/dependency identity and invalidation conditions.

Inspect reuse seams in the recipient before introducing an abstraction. A structured lookup, parser, rule table, graph algorithm, finite-state procedure, or solver can be appropriate. Do not reduce every task to regex or add a new DSL to solve a single branch.

## Construction loop

1. Reproduce the target behavior on authorized development evidence.
2. Explain the failure or repeated unnecessary reasoning.
3. Propose one bounded artifact and the counterexample it must preserve.
4. Implement the smallest authorized change.
5. Check structural validity, execution, task correctness, and end-to-end behavior separately.
6. Retain failures and revise within the declared attempt budget.
7. Freeze the chosen artifact before final evaluation.

A new hypothesis, altered contract, changed data population, or exposed final labels requires a newly identified experiment. Do not reuse the old claim as though only implementation details changed.

Generated code is untrusted until reviewed and executed under an appropriate authorized boundary. A lint check, restricted import list, subprocess, fresh checkout, container name, or trusted host runner does not by itself prove containment. Prefer the project's established safe interpreter when sufficient. Do not run a research repository, installer, generated command, or side-effecting procedure merely because it appears in an inspected source.

## Candidate failure modes

- A lexical approximation changes semantic criteria without declaring the approximation.
- A structured field appears helpful but is itself produced by a runtime model.
- A cached answer is mistaken for a generalizable rule.
- A trace's accidental order becomes a required dependency.
- A retry, audit, authorization, or cleanup step is removed as noise.
- A date rule reads the current clock although evaluation froze a reference date.
- A port changes numeric precision, Unicode behavior, coercion, or missing-value semantics.
- A new algorithm handles easy inputs and silently excludes hard ones.
- A prototype relies on a hidden account, environment variable, mutable lookup, or previous interaction.
- A model fallback makes a supposedly model-free artifact work.

Use these as investigation leads and concrete negative tests, not automatic rejection based on keywords.

## Generated artifact and effect contracts

For generated rule artifacts and evidence-bearing outputs, apply the [bounded mechanism checklist](mechanisms.md): validate the original envelope, bind the interpreter/admission closure, preserve decision ownership and exact evidence, and distinguish refusal from execution fault. Declare atomic or partial bundle semantics before building. Inspect a real caller and use a disconnected or fault-after-success control to test the actual mechanism.

## Deployment and retirement

Keep development support separate from production permission. State deployment prerequisites, rollback path, and the artifact/source/policy versions that invalidate prior results. Where a model was used as a construction scaffold, record its budget, expected retirement condition, residual use, and the evidence for retiring or retaining it.

The first implementation of Rule Or Reason supplies guidance and a descriptive comparison helper. It does not deploy artifacts, install donor dependencies, monitor production, automatically retire models, or authorize evaluations.
