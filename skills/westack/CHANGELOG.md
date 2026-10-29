# Changelog

## 0.3.1 — 2026-10-28

Renamed from estack to westack; no behaviour change; evidence vocabulary v3.

- Name. The package folder `skills/estack` is now `skills/westack`. Front matter says `name: westack`; the description swaps the name and nothing else (449 characters, within the 450 its test enforces); the heading is `# westack`. Host discovery paths, `/westack` and `$westack`, the `.westack/` evidence folder in the task starter, the trigger cases, the package check (`name must be westack`), the test module (`test_westack.py`) and the fixture variables (`WESTACK_FIXTURE`) follow.
- Kept as written, because they record what ran or because their bytes feed a stored hash:
  - Wire identifiers `estack-fingerprint-v1` (the patch fingerprint header), `estack-manifest-v1` and `estack-shape-v1`. Changing them would change every recorded `patch_id` and stored manifest, so records written before the rename would read as stale. `validate.py` carries a comment saying so.
  - Records: the twenty donor decisions, source qualification, build inputs, the artifact review, the continuation findings, every file under `tests/results/`, `tests/acceptance-results.json`, and the changelog entries below.
  - `package-manifest.json` describes the 0.2.0 release, not this package. It moved unchanged to `provenance/estack-0.2.0-package-manifest.json`.
- Evidence vocabulary. `references/evidence-vocabulary.md` is replaced byte for byte by the skill-belt master, v3 (SHA-256 `bde4fc984f4455223956fd9f32f29f61a986ebc9213f5b800a20bf5583debbd2`, 4064 bytes). v3 differs from v2 only in its version label and in naming westack where v2 named estack.
- Rename record. `provenance/lineage.json`.
- Guard. `tests/test_rename_guard.py` fails on any occurrence of the old name outside a listed keep rule, on the double prefix a careless find-and-replace produces, on stale keep entries and on any change to the older changelog entries. The suite has 206 cases (201 before).

## Unreleased — 2026-10-27

The task check now applies supplied host-observed revision, scope and patch to every record, not only final ones. Previously an in-progress record with passing acceptance still validated after the repository moved. Final records must still supply all three. Two regressions cover the checker and CLI paths; the suite has 75 cases. `package-manifest.json`, the release archives and the recorded 0.2.0 receipts still describe 0.2.0.

Later the same day, toward 0.3.0 (unreleased), from an independent review:

- Observed context. `validate.py fingerprint` hashes the allowed paths (skipping `.git`, `__pycache__` and the evidence root) and reads Git HEAD from disk: loose refs, packed-refs, detached HEAD and worktree pointers, with no subprocess. `init --repo` and `task --repo` recompute patch and revision instead of trusting the caller; a disagreeing `--patch` or `--revision` fails. `patch_id` now means that fingerprint in the example and tests, not one artifact's hash. Scope stays an author-chosen label.
- Snapshots. `validate.py snapshot` copies a tested file to `snapshots/<sha256><suffix>` by exclusive create, reusing an identical copy and refusing a mismatched one, so a red-phase receipt survives an in-place fix.
- Immutability under `--previous`. Receipts may only become `stale`. Findings and requirements cannot be removed. Adjudication moves only forward. Requirement text, origin and supersession are fixed.
- Negative controls. Every passing receipt behind a criterion that requires one needs its own failed control on a different artifact.
- Optional schema-1 fields: `decisions[]`, `work_units[].acceptance_ids` and `work_units[].rollback`; modes `plan` and `verify`; evidence type `review`; a nullable `expected_exit`. A frozen 0.2.0 record still validates (new fixture `tests/fixtures/v1-0.2.0`).
- Typed evidence. Reads and reviews may carry null exit codes (both or neither). Runtime receipts need both. Review evidence records that the review ran; defects are findings.
- State entry. An empty history requires `framed`, history starts at `framed`, and verified or complete records need a history. Two rules are deliberately stricter than 0.2.0, which accepted these records: a control on the same artifact, and a verified record with an empty history.
- Authority. Work-unit and authority paths must be portable, work-unit paths must sit inside the allowed paths, and a kind cannot be both allowed and forbidden. `init` adds `--forbid-action` and `--non-goal`.
- CLI. `validate.py reconcile` exposes the uncertain-action recommendation. Docs name exactly the six CLI commands, enforced by a test.
- Front matter. Package check requires name and description and allows `metadata`, `disable-model-invocation`, `license` and `allowed-tools`. It rejects unknown or duplicate keys and descriptions a YAML parser could misread. The description now names the resumable task record, broken-copy controls and passed/failed/not-run reporting, with exclusions; activation is not re-measured.
- Docs. A numbered-record refresh procedure is in build.md, checked end to end against the CLI. Internal decision and case IDs are gone from agent-facing modules. start-task.md runs from the project root with an evidence folder outside the skill. A model and paid-service fallback rule is added. E02 and E14 failure conditions are restored to the original wording. Research-ZIP verification is recorded in provenance. The Windows 8.3-alias assertion is ported from the public copy. Existing CLI subprocess timeouts are raised from 10 s (30 s for Node) to 60 s after load-induced spawn timeouts.
- Tests. Existing tests were updated for the stricter rules without weakening their assertions. Counts are in tests/acceptance-results.json.

2026-10-28, toward 0.3.0 (unreleased), from a second independent review and a source-level review of all twenty donors. Schema stays version 1; every new field and enum value is additive.

- Finish conditions only get stricter. Under `--previous`, within an unchanged scope, acceptance criteria cannot be removed, and their claim, `required`, `requires_runtime` and `requires_negative_control` cannot weaken. `independent_review_required` cannot be dropped, unfinished work units and reviews cannot be removed, and forbidden actions and non-goals cannot shrink. Relaxing needs a new scope in the same version plus a history event with a `reason`. Decisions follow the requirement rule: never removed, fixed content, active → superseded only. Removing an allowed action is a scope change; adding one needs an event whose `grants` names it. `task --chain DIR` checks every numbered version against its predecessor and reports gaps.
- Record helpers. `validate.py receipt` appends one receipt to the next numbered version: it snapshots the artifact, hashes the raw output, derives the counts and status, refuses when the repository moved, and with `--link` points the named criteria at it. `validate.py refresh` writes the next version from the observed context. It stales passed receipts whose patch or scope changed, resets dependent criteria and verification, stales old-scope approvals and appends a history event; `--scope`/`--relax`/`--grant` need `--reason`. Both write by exclusive create and execute nothing. Optional `evidence[].claim_ids` lets one run back several criteria. Events may carry `reason` and `grants`; a same-state event needs a reason.
- Fingerprint definition. Records store `fingerprint: {paths, exclude, baseline}`. Observed paths may be wider than the write paths (`init --observe-path`), and the default excludes cover `.git`, `__pycache__`, `.pytest_cache`, `node_modules`, `.venv`, `venv`, `.mypy_cache`, `.tox`, `dist`, `build` and `.next`, which a record may replace (`--exclude`, `--no-default-excludes`). `.git` and the evidence root are always skipped. Zero hashed files is an error, as is an evidence root that equals or contains an observed path, and allowed paths must lie inside the observed paths. `manifests/<patch>.json` keeps self-verifying per-file hashes, so a mismatch lists the added, modified and removed files, and `task` reports changed files outside every work unit's paths (`outside_work_units`, relative to the baseline).
- Content-bound staleness. Receipts, controls, reconciliations, fixed findings and reviews are current when patch and scope match. A moved revision with the same patch is reported in `notes` instead of failing, so committing verified work keeps its evidence. Final records still need the observed revision, scope and patch. The E11 test now moves the patch; a revision-only change is deliberately informational.
- Matched controls. A negative control must have the same evidence type, the same operation and the same collected count as the passing receipt, on a different artifact, for the same claim and scope. The same collected count is the compatibility rule: a crash before collection or a narrower selection does not count. The control's patch may differ, so a red run against the pre-fix file serves.
- Stale rules. A receipt can be marked stale only once its patch or scope differs from the record's, and stale receipts keep their counts, timestamp and files.
- Mismatch messages name the recorded and observed values and, with a stored manifest, the changed files.
- Review independence. Reviews may record `level` (self, fresh-context-same-model, different-model, human). An independent review cannot be `self`, a self review cannot claim more, and a required independent review needs a level other than self.
- Smaller fixes:
  - `reconcile` answers `report-unauthorized-effect` when an effect appears without an approved decision.
  - Front matter accepts `compatibility` (1–500 characters) and a leading UTF-8 BOM.
  - Build and repair records finish only with a `verified` event after their last `implemented` event.
  - `--repo` in a subdirectory finds the Git root upward and reports it, an explicit `--revision` labels a nested folder, and "no .git found" is reported.
  - Only symlink and junction reparse tags count as links; cloud placeholders are hashed.
- Docs:
  - contracts/README.md carries a field table generated from contract.json (`tests/field_table.py`), with a matching test.
  - build.md documents `receipt`, `refresh` and `--chain` in place of the seven hand steps.
  - verify.md adds a disposable git-worktree recipe for broken-copy controls and the claim-strength mapping.
  - tiny-repair.md no longer asks a no-record repair for snapshots or a repeated red run.
- Inconclusive result. `inconclusive` is a receipt and acceptance status: it ran, but the result can't settle the claim (flaky outcome, missing oracle, environment limitation or ambiguous observation). Never counts as passed; record why and what would settle it. An inconclusive receipt needs `limitations`, cannot back a passing criterion or serve as a control, and a required inconclusive criterion blocks completion. `receipt --status inconclusive --link` records one. The shared vocabulary master is updated separately by its owner; this package's copy is untouched.
- Donor guidance adopted into the modules (SKILL.md stays lean):
  - verify.md: a regression baseline before the change, with failing tests compared and reported by name, pre-existing ones included; receipts record variable names and versions, never values; tooling errors are blocked, the same command is retried at most twice, and a check is never silently swapped; expected values derived independently, broken copies from realistic mutations, and a paired run showing legitimate behaviour still passes.
  - finish.md: new and pre-existing failures reported separately; armed auto-merge or a merge queue checked before a push.
  - review.md: after a confirmed defect, the same pattern is searched in scope, and an empty result names its coverage.
  - frame.md: only questions with settled prerequisites are batched, each with a recommended answer; facts are looked up, not asked; vague quantifiers are never resolved silently.
  - build.md: writes to hooks, build steps or CI configuration are deferred execution and need explicit scope.
  - hosts: Codex permission profiles cover local commands only (`permission_surfaces` in capabilities.json).
  - The SKILL.md description now leads with its trigger.
- Provenance. decisions.json records each donor's source-level grade, drift and observed licence (`source_review`, dated 2026-10-28): present for seventeen (D06, D16 and D18 re-confirmed), wired for D12, claimed for D14 and D15. Five attributions are corrected:
  - D01: the pin delegates to an exhaustive interview; "decision-changing questions only" is estack's.
  - D04: broken-copy controls are estack's.
  - D07: the richer revision e8d856f0 is cited, and the pin is kept.
  - D13: the donor CLI's `--version` is credited.
  - D20: "no deployment or credential use" is estack's.

  source-qualification.json, continuation.md and RIGHTS.md are updated to match.
- Tests:
  - `tests/test_round2.py` (62 cases) covers each round-2 change and the reviewer's fooling cases.
  - `tests/test_donor_review.py` (13 cases) covers `inconclusive`, the description order and the adopted guidance.
  - Twelve existing tests or their fixtures were updated to the new rules.
- Later, not now: per-receipt input binding narrower than the whole patch, an mtime cache for large fingerprints, and a host Stop-hook recipe.
- Not doing: mutation testing, signed attestations and `.gitignore` parsing.
- Activation is still not re-measured, including after the description reorder; `tests/trigger-cases.json` needs a live run.

## 0.2.0 — 2026-10-26

Continued the existing synthesis with Frankenmine. Added optional canonical task startup, six starter checks, source-qualified lifecycle/recovery guidance, and 24 adversarial relationship/path regressions. The 73-case suite includes all previous cases. Corrected the previous uncertain-action positive fixture to observe the action itself rather than borrow an unrelated acceptance receipt; original behavior assertions remain. A review-added case preserves historical completed writes after the current path scope narrows.

Negative controls now bind to current claims and actual failing cases; uncertain actions need current passing action evidence; current-scope applied actions need an allowed kind; renamed denied occurrences cannot approve replay. Completion accounts for recorded work and requirement supersession is acyclic. JSON parsing is bounded/finite, evidence hashing streams large regular files, and package scanning rejects junctions before traversal.

Qualified a bounded D06/D16/D18 source subset without executing or transplanting donors. Corrected D06 attribution: verifier lifecycle comes from its generator; good/broken controls are estack additions; non-author same-patch review is separately corroborated by shipping. Other donor depths and broader host/model qualification remain explicit limits.

## 0.1.0 — 2026-10-26

First independently authored standalone estack skill. Added one entrypoint, selective workflow modules, shared versioned records, host declarations, provenance/rights notes, examples, deterministic consistency checks and pilot fixtures.

Local suite: 43/43 passing with no skipped tests. Six newly exposed false-acceptance counterexamples were corrected: unrelated claim receipts, empty required acceptance, unrun review evidence, stale finding verification, pending actions labeled applied, and unrelated old runtime receipts. Node fixture execution explicitly selects TAP for stable test-count evidence. Earlier failing runs are retained.

Design supplied through the parent task message; research ZIP transfer remained unavailable and was explicitly removed as a build prerequisite. No claim of Library byte materialization or archive verification. Live model behavior, non-author host review and actual host enforcement remain unqualified.


Provenance correction: filled D14-D20 source URLs, Archon supporting anchors/evidence note and optional pstack shipping URL from verified parent catalogue records. Inspection limits are retained; no donors were fetched, audited or executed. Workflow code and test fixtures are unchanged.
