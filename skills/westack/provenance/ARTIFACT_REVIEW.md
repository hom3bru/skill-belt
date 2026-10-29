# Independent final artifact review

Date: 2026-10-26. Scope: Estack copied continuation and Frankenmine 0.1.2 continuation helper. Reviewer responsibility: read-only artifact/code/contract review and bounded authored local probes. No source retrieval, third-party donor execution, installation or host qualification was performed by this review.

## Disposition

Accepted for a bounded experimental prototype continuation, with the existing release limitations retained. No demonstrated critical issue remains from this pass. This is an artifact review, not a blanket certification of agent behavior, reviewer authenticity, permissions, exactly-once effects or comparative benefit.

## Finding resolved during review

A retained old-scope applied local-write was incorrectly checked against the narrowed current allowed paths. The root agent corrected the guard to retain historical applied writes while checking current-scope and not-yet-applied writes. The original authored previous/current snapshots are preserved in `historical-local-write/`; rechecking them after the fix returns no errors. A separate regression now covers the actual local-write path case, beyond the earlier historical commit test.

## Verification

- Independently reran 24 adversarial relationship/path tests: 24 passed, 0 failed, 0 skipped.
- Independently reran six task-starter tests: six passed, 0 failed, 0 skipped.
- Used Estack's actual init CLI for a new bounded build. It created the canonical framed/open/unverified record with no actions, evidence or acceptance claims.
- Used Frankenmine's actual init --decisions CLI with two authored source declarations and injected approval/review metadata. It registered both as queued, retained no evidence/receipts, and did not promote the metadata to qualification. The resulting check returned the intended nonzero incomplete state.
- Inspected source and continuation tests for generic manifest registration, URL-declared full-commit pins, non-fetching behavior, strict JSON, duplicate IDs, malformed URLs, missing input and exclusive output.
- Reviewed starter/contract/continuation documentation for authority boundaries, historical actions, observation strength and proportionate usage.

Exact commands, stdout/stderr, source SHA-256 values and smoke records are in `final-smoke-results.json` and `startup-smoke/`. Per-test results are in `test_frankenmine_regressions.py.results.json` and `test_task_start.py.results.json`. (Note added 2026-10-27: these files, and `historical-local-write/` above, belong to the review's working directory and are not included in this package.)

## Usability and limits

The Estack starter removes manual transcription of the large canonical envelope while keeping tiny conversational tasks available. Required observed context is explicit. Acceptance, real observations and approvals still require task-specific work; the starter does not fabricate them. Streaming artifact hashes bound memory while allowing large regular artifacts; the 8 MiB JSON limit remains a record limit.

Frankenmine's continuation route now covers advancing an existing multi-donor synthesis through an authorized slice. It preserves baseline/evidence, supports a narrative dossier when full machine interchange is unnecessary, registers all supplied decisions before triage, and permits bounded source qualification with explicit deferrals. The selected changes support continued product work without requiring a fresh audit of every donor. Ordinary transfers into unrelated established recipients remain separately routed.

Evidence records and metadata remain author-supplied. Neither package can authenticate observers or permissions, infer complete source closure, enforce hostile concurrent filesystem boundaries, prove remote replay safety, or establish model/host effectiveness. Full representative-product benefit and independent host/model qualification remain separate work.
