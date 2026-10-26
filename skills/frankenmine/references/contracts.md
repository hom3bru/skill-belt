# Portable dossier contract 1.0

`schemas/run.schema.json` defines the typed JSON envelope. `scripts/frankenmine.py check` implements its documented JSON Schema subset (local $ref, type, properties, required, additionalProperties, items, minItems, minLength, minimum, pattern, enum, const, uniqueItems) plus relationship and readiness checks. It is not a general JSON Schema engine.

Stable IDs connect donors, evidence, discoveries, candidates and tests. A source snapshot path is relative to the run's directory and confined there; symlinks and escapes are rejected for evidence. Copy only lawfully available, appropriately bounded source into the run. Evidence includes pinned donor revision/path, line range, observation type, scope, digest and limitations. Author-tested is a reported source property, not locally observed.

Design phases are queued, inspected, candidate, qualified, selected, deferred, rejected, design-reviewed. Implementation states are not-started, implemented, tested, demonstrated. Design decisions do not mutate implementation state. Default skeletons deliberately fail readiness. Do not fill unknowns with invented evidence to turn a checker green.

Each selected candidate needs a qualified seam (all required dimensions), evidence, target need, falsifier, closure, route, rights, contract, owner/caller/recovery/update, acceptance and negative-control test references. Each cross-language selection needs all semantic dimensions. State and policy keys are unique ownership decisions across the product.

For selected units, evidence, rights evidence and discovery links must include the candidate's own donor. A nonempty closure must explain retained dependencies or why there are none. Use consistent language labels (case is ignored): `source_language` must appear in the donor's languages; `target_language` names the product's caller/runtime language from the brief. For native process/FFI/RPC/WASM routes, the retained donor language remains the source language and the target denotes the receiving side of the bridge. These labels make semantic-delta requirements checkable; they do not prove actual language identity.

Acceptance references must have purpose product, adapter or integration; a negative control or donor-parity check alone cannot stand in for product acceptance. Required acceptance, control, interaction and applicable delta tests may remain not-run in a design, but fail/skipped/blocked statuses prevent readiness. Runtime tested claims require passing acceptance and control even for candidates later deferred or rejected.

Every selected pair needs an interaction disposition; higher-order risks have an explicit review. Alternatives include best-existing, minimal-fresh and fusion with tradeoffs and a decision rationale. A non-fusion choice may finish without selected donor units. Independent review, accounting for every donor, two-way discovery and frozen test specifications are design gates.

`unresolved` contains design blockers and must be empty before readiness. Keep optional follow-ups in the dossier narrative. Resolve a blocker with evidence or explicitly reduce scope and document its effect; never delete it solely to pass a checker. Reasoned donor deferrals do not automatically block a bounded design.

Evidence `kind` records the author's claimed observation level. The helper checks snapshot bytes, revision and line range for all kinds, including observed; it cannot prove that code is wired or was executed. An observed claim must cite its authorized trace/receipt and scope in the record and undergo manual review. A flag, matching hash or self-declared independent review cannot authenticate an observer or authorize execution.

Tests store specification plus status not-run/pass/fail/skipped/blocked. Passing tests require a matching receipt with positive case counts and hash-verified raw output/oracle. Negative controls require their own observed detection, not a passed label alone. Runtime claims remain bounded by the report's explicit evidence and authorship limits.
