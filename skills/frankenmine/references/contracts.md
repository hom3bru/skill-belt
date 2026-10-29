# Portable dossier contract 1.1

**Schemas.**
- `schemas/run.schema.json` is the current envelope (1.1). `schemas/run-1.0.schema.json` is the frozen 1.0 contract.
- Each record is validated against the schema its `schema_version` names. A 1.0 record therefore parses exactly as before. A 1.0 record that uses a 1.1 field is rejected, and an unsupported version is named.
- Every 1.1 addition is optional in the schema. A 1.0 record can never become design-ready, because the review gate needs 1.1 fields; see "Upgrading a 1.0 record" below.
- `check` implements only the JSON Schema subset these files use: local `$ref`, `type` (one type or a list), `properties`, `required`, `additionalProperties`, `items`, `minItems`, `minLength`, `minimum`, `pattern`, `enum`, `const` and `uniqueItems`. It adds relationship and readiness checks on top, and is not a general schema engine.

**Evidence.**
- Stable IDs connect every group.
- **Source evidence** cites a pinned donor revision, path, line range, observation kind, scope, digest and limitations. Its snapshot path is relative to the run directory and confined to it; links and escapes are rejected. Copy only lawful, bounded source.
- **`supporting_evidence`** is weaker than a source snapshot:
  - `documentation` and `product-observation` need a URL and a `retrieved` date;
  - `screenshot` needs a local snapshot (binary allowed), its sha256 and a retrieved date;
  - `static-graph` is a JSON graph (for example from `inspect-python`) whose `revision` matches its donor;
  - `license-scan` is saved licence-scanner output (ScanCode, ORT, Syft or similar) with `tool`, `tool_version`, snapshot and sha256. The helper reads the output and never installs or runs a scanner.
- Alternatives may cite supporting evidence and donor searches. A seam may cite a static graph of its own donor; rights may cite a licence scan of their own donor. Discoveries and candidate provenance must cite donor source.
- Evidence `kind` is the author's claim. Byte, revision and line checks cannot prove wiring or execution, and an observed claim must cite its authorized trace and be reviewed manually.
- **`discovery_searches`** (optional) record each donor or best-existing search: `source`, optional `query`, `date`, `considered`, `chosen`, `rejected` and `reason`.

**Text.** Unfinished text blocks readiness wherever it appears in the record.
- **Placeholders:** TODO, To do, TBD, WIP, Not yet known, FIXME, or a leading `?`. Also a value of three words or fewer, or a word followed by `:`, when it begins with unknown, pending or unclear. A bare `None` is a placeholder.
- **Nothing to record:** write `none: <reason>` where nothing exists (no effects, no dependencies) and `n/a: <reason>` where a field does not apply.
- **Exempt:** blind spots, limitations and unresolved items.
- **Scaffold marks:** any value starting `TODO(scaffold)` blocks readiness wherever it sits, including in unselected candidates.

**States.**
- Design phases: queued, inspected, candidate, qualified, selected, deferred, rejected, design-reviewed.
- Implementation states: not-started, implemented, tested, demonstrated.
- Design decisions never change implementation state.
- In implementation mode, `check` reports `design-ready; implementation-unverified` until every selected part is tested and its required tests pass.
- Skeletons fail readiness on purpose. Never invent evidence to turn a check green.
- `brief.question` is `product-led` or `exploratory`. Only an exploratory brief may start without requirements.

**Selected candidates.** A selected candidate needs:
- **Seam.** Every seam dimension, plus `seam.evidence` that includes source evidence from its own donor.
- **Basics.** Evidence, a need and a falsifier. `need` may be one requirement ID or a list.
- **Reuse.** Closure, a route and rights. A `reimplementation` declares `basis`: `code` (rewritten from the donor's source) or `idea` (rebuilt from the documented behaviour).
- **Placement.** Contract, owner, caller, recovery, update plan, and acceptance and negative-control tests.
- **Donor.** Evidence, rights evidence and discoveries must come from the candidate's own donor. The donor must be reviewed and pinned: a full commit, or `<immutable-tag>@sha256:<digest>`; `unpinned`, branches, `HEAD` and floating tags fail.
- **Rights.** Rights must be reviewed, with a `category` (open-source, source-available, proprietary, public-domain or task-authored); `unknown` blocks. A code route (dependency, narrow-port, ffi, process, rpc, wasm, or reimplementation with basis `code`) needs rights route `licensed-reuse` or `permission`, and source-available or proprietary code needs `permission`. `idea-only` rights allow only pattern-only or reimplementation from the idea.
- **Retained dependencies.** On a dependency, narrow-port, ffi, process, rpc or wasm route, `closure` lists structured items `{name, pin, category, disposition}` (disposition retain, replace, bridge, exclude or unresolved; optional `license`, `obligations`, `evidence`), or reads `none: <reason>`. A retained or bridged item needs an exact pin (commit, tag@sha256 or one exact version); an unknown category or unresolved disposition blocks, and a source-available or proprietary item needs `permission`.
- **Languages.** `source_language` must be one of the donor's languages and must agree with the extensions of the candidate's own evidence files (a small map: `.js` JavaScript, `.ts` TypeScript, `.py` Python, `.rs` Rust, `.go` Go, and so on; unmapped extensions are ignored). `target_language` must equal the brief's; for process/FFI/RPC/WASM routes it is the receiving side.
- **Semantic deltas.** All 13 dimensions, none unknown, are required only when a reuse route moves behaviour across a language boundary. Reuse routes are dependency, narrow-port, ffi, process, rpc, wasm and reimplementation. A not-applicable delta needs only `dimension`, `status` and `reason`; every other delta also needs donor and target semantics, conversion and a test.
- **Protocol.** Process and rpc routes need a protocol that is not entirely `n/a`.

**Ownership and interactions.**
- Ownership keys are unique after normalising case, whitespace and separators.
- A candidate's `owner` must appear in `ownership`. Each key it `touches` needs an ownership entry.
- Every selected pair needs an interaction record:
  - `independent`: every part declares non-empty `touches`, the touches share no key, and a rationale is given.
  - `compatible` or `resolved`: evidence, plus a required test whose purpose is `interaction` or `integration`.
  - `conflict` or `unknown`: blocks readiness.
- A key touched by three or more selected parts needs one group record whose `components` include all of them, `compatible` or `resolved`, verified by an `integration` test. Pairwise records do not cover it.
- Higher-order risks also need the global review.

**Decision.**
- Alternatives must include best-existing, minimal-fresh and fusion, with tradeoffs. Each may carry `dimensions` (`name`, numeric `value`, `direction` higher or lower is better); a dimension keeps one direction across alternatives. `report` prints the non-dominated (Pareto) set and the dominated alternatives, and notes when the decision chooses a dominated one; the decision still needs its rationale.
- Every requirement must be covered under every decision: by a selected candidate's `need`, or in `requirement_coverage`, which maps requirements to selected candidate IDs, `new:<component>` for authored code and `existing:<product>` for a best-existing product.
- **`fusion`** needs at least one selected donor unit on a reuse route.
- **`minimal-fresh` and `best-existing`** may keep only pattern-only lessons selected.

**Review and blockers.**
- A donor-led discovery that duplicates a target-led one is rejected.
- The review records `author`, `reviewer` and `independence`: `self`, `fresh-context-same-model`, `different-model` or `human`. Readiness needs an accepted disposition, a reviewer who is not the author, a level other than `self`, at least one finding, and `review.report` `{path, sha256}`: the reviewer's saved report inside the run root, which must name the recorded reviewer and level. The 1.0 `independent` boolean must agree with the level.
- `unresolved` holds design blockers only and must be empty before readiness. Resolve a blocker with evidence or a documented scope reduction, never by deletion alone. Reasoned donor deferrals do not block a bounded design.

**Tests, receipts and product files.**
- Test status is not-run, pass, fail, skipped or blocked, and executed statuses need receipts.
- An oracle may not be a source-evidence snapshot or sit in a folder that holds one.
- Several receipts for one test need unique `sequence` numbers. The latest decides the status; earlier failures are kept and reported.
- A passing latest receipt needs positive case counts and hash-verified raw output and oracle. A negative control needs observed detection.
- Each receipt has its own raw output, unless every receipt sharing it declares `raw_shared: <reason>`.
- `artifacts` lists the product files with `path`, `sha256`, `origin` (reused, adapted or authored) and the `candidates` they implement; reused or adapted files name their donor `unit` and need a part on a code route. Receipts list the `artifacts` (path and sha256) they tested; `check` re-hashes them, and a latest receipt whose files changed is stale. A `tested` or `demonstrated` part needs artifacts of its own, listed by the latest receipts of its acceptance test and negative control.

**Authoring helpers.** `stamp RUN --output NEW` fills every missing file hash (evidence, supporting evidence, oracles, raw outputs, artifacts, review report) and missing evidence revisions into a new record; a recorded hash that disagrees with its file is reported, never rewritten. `scaffold` appends a candidate stub (seam, rights and, across languages, the 13 deltas) whose values are `TODO(scaffold)` placeholders and adds an unresolved line, so the record stays blocked until it is filled.

## Upgrading a 1.0 record

There is no migrate command. Upgrade by hand, then run `check`:
1. Set `schema_version` to `"1.1"`.
2. Add `review.author` and `review.independence`, and drop or align the `independent` boolean.
3. For each selected candidate, add `seam.evidence`, `rights.category`, `touches`, and `basis` on a reimplementation.
4. Give interactions an `interaction` or `integration` test, or mark a disjoint pair `independent`.
5. Add `requirement_coverage` for any requirement no selected candidate's `need` covers.
6. For an accepted review, save the reviewer's report in the run root and add `review.report`.
7. In implementation mode, add `artifacts` and the `artifacts` each latest receipt tested.

Every remaining readiness message names the field to add or the rule to meet.
