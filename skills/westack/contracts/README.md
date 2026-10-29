# One canonical contract

[contract.json](contract.json) is the normative version 1 shape and transition table. [validate.py](../scripts/validate.py) reads it directly; there is no donor-specific task schema.

A task owns requirements, optional decisions, work units, acceptance criteria, actions, evidence, findings, lessons and documentation references. Record identities bind scope, revision and patch; they are not host permissions. Modes are question, investigate, plan, design, build, repair, review, verify or finish. The task state is framed, inspected, planned, authorized-work, implemented, verified, delivered, blocked, needs-decision or partial. Read-only investigation/design/review may deliver source-audited findings without claiming implementation or runtime checks.

## Fields

Generated from contract.json by `tests/field_table.py`; the suite checks that this copy matches. Enum values are in parentheses.

<!-- field-table:start -->
| Object | Required | Optional |
| --- | --- | --- |
| task | schema_version (1), id, mode (question/investigate/plan/design/build/repair/review/verify/finish), size (tiny/bounded/cross-cutting), goal, non_goals, scope_id, revision, patch_id, author_id, authority, host, requirements, work_units, acceptance, actions, evidence, findings, reviews, lessons, docs, history, state (framed/inspected/planned/authorized-work/implemented/verified/delivered/blocked/needs-decision/partial), completion (open/partial/complete/blocked), verification (unverified/source-audited/runtime-tested), independent_review_required, delivery (none/local/committed/pushed/pr/merged/deployed), next_safe_action, blockers | decisions, fingerprint |
| task.authority | allowed_actions, forbidden_actions, allowed_paths | — |
| task.host | name, version, capabilities | — |
| fingerprint | paths, exclude | baseline |
| requirement | id, text, origin (user/repository/assumption), status (active/superseded/parked), supersedes | — |
| decision | id, question, choice, alternatives, origin (user/repository/assumption), status (active/superseded), supersedes | — |
| work_unit | id, goal, depends_on, allowed_paths, status (planned/active/done/blocked) | acceptance_ids, rollback |
| acceptance | id, claim, required, requires_runtime, requires_negative_control, evidence_ids, status (passed/failed/blocked/not-run/inconclusive) | — |
| action | id, kind (read/local-write/install/credential-access/egress/commit/push/pr/merge/deploy/policy-edit), target, target_hash, scope_id, occurrence, decision (pending/approved/denied/stale), outcome (not-applied/applied/uncertain/denied), evidence_ids | — |
| evidence | id, claim_id, type (source/review/unit/contract/integration/e2e/host), revision, patch_id, scope_id, artifact, artifact_sha256, operation, environment, raw_output, raw_sha256, recorded_at, status (passed/failed/blocked/not-run/stale/inconclusive), collected, executed, passed, failed, skipped, exit_code, expected_exit, negative_control, coverage, limitations | claim_ids |
| finding | id, claim, location, consequence, evidence_ids, severity (low/medium/high/critical), severity_rationale, correction, adjudication (open/accepted/rejected/fixed/deferred), rationale, verification_ids | — |
| review | id, author_id, reviewer_id, context_id, patch_id, kind (self/independent), status (completed/not-run), evidence_ids, finding_ids | level (self/fresh-context-same-model/different-model/human) |
| lesson | id, source, scope_id, revision, expires_at, text, status (proposed/revalidated/stale) | — |
| doc | id, source, target_version, observed_version, retrieved_at, revalidate_after, status (current/stale/mismatch) | — |
| event | id, from, to, scope_id, patch_id | reason, grants |
| capability | name, availability (supported/unsupported/unknown), evidence | — |
<!-- field-table:end -->

## Context identities

- `patch_id` is the observed fingerprint: SHA-256 over `estack-fingerprint-v1\n` (a wire identifier from before the rename to westack, kept so existing patch IDs stay valid) followed by sorted lines `<posix path>\0<file sha256>\n` for the files under `fingerprint.paths` (default: the allowed paths). It may be wider than the write paths, so tests and configuration you may not edit still count. `fingerprint.exclude` lists names (matched at any depth) or relative paths left out; the default is `.git`, `__pycache__`, `.pytest_cache`, `node_modules`, `.venv`, `venv`, `.mypy_cache`, `.tox`, `dist`, `build` and `.next`, and a record may replace it. `.git` and the evidence root are always skipped. Only symlinks and junctions are recorded as `link:<target>` and never followed; other reparse points (cloud placeholders) are hashed. A missing requested path is `missing`. Zero hashed files, or an evidence root that equals or contains an observed path, is an error. `init`, `refresh` and `receipt` store the per-file hashes as `manifests/<patch>.json` in the evidence root (self-verifying: the entries must hash to the name), so a mismatch can list the changed files.
- `revision` is the Git HEAD (40 or 64 hex) read from the nearest `.git` at or above `--repo`, the output of `git rev-parse HEAD`, or a label such as `no-vcs`. A nested folder may keep an explicit `--revision` label; the enclosing HEAD is reported.
- `scope_id` is an author-chosen label for the user's current authority. The checker can only compare it; nothing observes it.
- `author_id` is whoever produced the patch under review or verification.

Staleness follows content and authority: a receipt is current when its `patch_id` and `scope_id` match the record. A moved revision with the same patch (for example after a commit) is reported as a note, not staleness.

## Evidence

Evidence has claim, observed artifact hash/revision/patch, operation, environment, raw output digest, executed/pass/fail/skip counts, status, negative-control evidence and coverage limits. Optional `claim_ids` lets one run back several claims. Files use portable relative slash paths under the selected evidence root; `validate.py receipt` snapshots the artifact and hashes the raw output for you. Types `source` and `review` run no process: both exit fields are null (or both integers). Runtime types need both. A review receipt records that the review ran; defects are findings. A digest cannot prove who ran a command. The root and current context supplied to validation must come from the host/user, not a candidate's untrusted instructions.

A receipt may be marked `stale` only when its patch or scope differs from the record's, and a stale receipt keeps its counts, timestamp and files.

Receipts and acceptance criteria may be `inconclusive`: it ran, but the result can't settle the claim (flaky outcome, missing oracle, environment limitation or ambiguous observation). Never counts as passed; record why and what would settle it. An inconclusive receipt must say so in `limitations`, cannot back a passing criterion or serve as a negative control, and a required inconclusive criterion blocks completion.

Review findings bind author/reviewer context, patch, location, consequence, evidence, severity rationale, correction, adjudication and verification. Self-review stays self-review. A review may record its independence `level` from the shared vocabulary (self, fresh-context-same-model, different-model, human); an independent review cannot be `self`, and a required independent review needs a recorded level other than `self`. The helper cannot authenticate reviewer identity.

## History and snapshots

Append history events once with unique IDs. An empty history means state framed; a nonempty history starts at framed; verified or complete records need one. A same-state event (from equals to) is a note and needs a `reason`; `grants` on an event records action kinds the user granted. Build and repair records finish only with a `verified` event after their last `implemented` event. Supplied patch and scope bind every record: a difference fails until the record is refreshed, and final records must supply revision, scope and patch.

With `--previous` (or `--chain` for every numbered version in order), the helper checks append-only history, preserved action outcomes, receipts that change only to `stale`, findings, requirements and decisions that are never removed, adjudication that moves only forward (open → accepted, rejected, deferred or fixed; accepted → deferred or fixed; deferred → fixed), requirements whose text, origin and supersession stay fixed while status moves active ↔ parked or to superseded, and decisions whose question, choice, alternatives, origin and supersession stay fixed while status moves only active → superseded.

Finish conditions only get stricter within a scope: acceptance criteria are never removed, and their claim, `required`, `requires_runtime` and `requires_negative_control` never weaken; `independent_review_required` is never dropped; unfinished work units and reviews are never removed; forbidden actions and non-goals are never removed. Relaxing any of these needs a new `scope_id` in the same version plus a history event under that scope with a `reason`. Removing an allowed action kind is a scope change; adding one within a scope needs a new event whose `grants` names it, with a `reason`. Without a prior snapshot the helper cannot detect deletion. Keep numbered snapshots through the host's existing storage; no service is installed.

Reconciliation states are applied/not-applied/uncertain/denied. Inspect uncertain targets before replay; caller observations are not independent proof. An effect observed as applied without an approved decision is reported (`report-unauthorized-effect`). Examples use synthetic identities and cannot authorize real mutations.

Resolving uncertainty against `--previous` requires current passing evidence whose claim is the action ID. For a criterion that requires a negative control, every passing receipt names its own control: a failed receipt for the same claim and scope, with actual failing cases and no skips, of the same type and operation and with the same collected count, on a different artifact. The same collected count is the compatibility rule: both runs selected the same cases, so a crash before collection or a narrower selection cannot stand in. The control may come from an earlier patch, so a red run against the pre-fix file qualifies. Process failure alone is insufficient. Current-scope approved actions still need an allowed action kind after they are applied, and no kind may be both allowed and forbidden. Reintroducing an identical denied occurrence under another ID cannot approve it. Historical applied actions remain retainable after a scope change. Complete records require all recorded work units done; work-unit paths must be portable and inside the allowed paths, and allowed paths must be inside `fingerprint.paths`. Reduce scope explicitly or retain a partial outcome when work remains. Requirement and decision supersession is acyclic.

## Optional fields and the starter

Version 1 accepts optional `decisions[]`, `fingerprint`, `work_units[].acceptance_ids`, `work_units[].rollback`, `evidence[].claim_ids`, `reviews[].level`, and `history[].reason`/`grants`. Records without them stay valid; `tests/fixtures/v1-0.2.0` is a frozen 0.2.0 record checked by the suite.

The optional `validate.py init` starter creates this same version-1 shape. It requires caller-selected output/evidence scope and observed context (`--repo`, or `--revision` with `--patch`), records `--forbid-action`, `--non-goal`, `--observe-path` and `--exclude` (or `--no-default-excludes`), refuses replacement and starts open/unverified with no receipts or action decisions. Supplied allowed actions record an existing scope snapshot; they do not grant permission. JSON records are capped at 8 MiB; evidence digests stream regular files so large artifacts need not be loaded into memory. Package validation rejects symlinks and junctions before directory traversal, strips a leading UTF-8 byte-order mark, and accepts only the front-matter keys name, description, metadata, disable-model-invocation, license, allowed-tools and compatibility (1–500 characters). All path checks remain diagnostic, with no concurrent-filesystem sandbox claim.

The checker supports the contract's deliberately small type/required/enum/range vocabulary. Reject extra keys and malformed JSON. It is not a general JSON Schema implementation, runtime, policy engine or OS boundary. Version changes require explicit migration; do not silently reinterpret old records.
