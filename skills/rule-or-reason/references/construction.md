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

Rule Or Reason supplies offline record checks and guidance. It does not deploy artifacts, install donor dependencies, monitor production, automatically retire models, or authorize evaluations. See [lifetime.md](lifetime.md) for a retained identity and economics example.

## Obligation-preserving operation map (0.2)

Inventory every source must/never/ask/at-most clause manually with its source citation. Keyword extraction alone cannot establish completeness. For each obligation name the operation that enforces it. Retain typed inputs/outputs, dependencies, applicability, operation kind (rule/tool/model/human gate/check), retry maximum, partial-effect reconciliation, value+witness, downstream consumer and independent check. An operation record is a checkable plan, not a new runtime or permission token.

The complete worked source and plan are `assets/obligations-source.json` and `assets/obligations-plan.json`. Their flow is:

1. `approve`: human gate consumes `source`, yields `approval` to the host.
2. `rule`: consumes `source` and `approval`, depends on `approve`, has at most two retries, and produces `value+witness` bound to `selected-entity`.
3. `consume`: depends on `rule` and consumes that exact value+witness.

The source lists approval, retry cap, required approval input, witness owner, consumer and reconciliation obligations. `plan.source_sha256` is the helper's semantic digest of the source list. `study.py obligations --request assets/obligations-request.json` checks the declared ordered map. A missing operation yields `unmapped_obligation`; a changed human kind, unbounded retry, unavailable required input, or another entity's witness fails its named check. Empty maps and unsupported versions are invalid inputs.

Inspect real code and caller tests separately: a forged complete map, idle gate or dishonest source list can pass static checks. Bind effectful operations to the approval result as a required input, and check real downstream use. `tests/test_study.py` includes all five required broken plans and unused-gate, disconnected-consumer and recovery controls. A successful map check is necessary, never sufficient for deployment.

## Selective conversion recipe

Validate original input → known-state/applicability gate → candidate → validate output and source-bound evidence together → accept only within scope. Conflicts fail closed. Otherwise record abstention/fault/gate failure and defer to the already-authorized fallback; do not silently add model repair. Hosted embedding/validator failure is a fault, never a valid match. Treat Unicode/locale changes and stale policy as reasons to revalidate the applicability contract.

On development cases, sweep declared thresholds against the stated utility, then freeze policy, source, plan, artifact identities and threshold before holdout. Record rule-stage routing/check/embedding/runtime costs in candidate rows; deferred cases add fallback costs. The hybrid is an ordinary scored arm. An always-abstaining rule is the fallback-only control; negation-sensitive high coverage is the error control. The seeded [demo](../scripts/demo.py) demonstrates both with synthetic records, not a real rule execution.
