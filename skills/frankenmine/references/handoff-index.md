# Optional continuation index

Use the index when a long machine-record synthesis needs a compact recovery view. For a narrative-only run, retain a short continuation section with the baseline, exact donor/contract IDs, owner/source links, unresolved decision and next authorized slice. No universal board or conversion is required.

From any directory (outputs never go inside the skill folder):

```powershell
python "<skill-directory>/scripts/frankenmine.py" handoff "<run-root>/run.json" --output "<run-root>/HANDOFF.json"
python "<skill-directory>/scripts/frankenmine.py" handoff "<run-root>/run.json" --decisions "<prior>/decisions.json" --output "<run-root>/HANDOFF-WITH-JOINS.json"
```

Ownership conflicts are grouped by normalized key, as in `check`. A pair dispositioned `independent` with disjoint touches needs no interaction receipt; an invalid independence claim stays pending. Receipts are listed in `sequence` order with the latest marked.

This reads the existing schema, uses the existing validator and writes a disposable projection. It never changes records, fetches sources, runs recorded commands, schedules work or calls a model. Output names must be unused. A malformed envelope or duplicate stable IDs cannot produce an index. A valid incomplete envelope produces a blocked index and exit 2; exit 0 reports record consistency, with no product or host qualification.

Read `next`, then its authoritative `source` and `owners`. `pending` retains the other decisions. Deterministic order is ownership conflicts, manifest join failures, unresolved or unverified interactions, selected contract checks/contracts/integration gaps, review, recorded blockers, remaining validator errors and, in design mode, the authorization step. Order helps resumption; it does not grant implementation or execution permission. The view preserves the brief's authorization and each contract's approval boundary. Owner links show recorded declarations, including both sides of a conflict. Missing owners remain empty rather than fabricated. JSON pointer locators refer to the exact field in the linked source file; a viewer may ignore the pointer fragment, so use `path` plus `pointer` when necessary. Paths are local and the derived view should be regenerated after moving a run.

`donors` preserves queued/reviewed/deferred accounting and reasons; `contracts` preserves qualified/selected design phase separately from not-started/implemented/tested/demonstrated implementation declarations. `verification` reports only bounded recorded acceptance/control consistency and shows their receipts, raw-output links and exact IDs. Shared tests list `shared_by`; the schema permits shared acceptance and cannot establish semantic per-donor ownership merely from names. Disconnected receipt/test references and mismatched candidate provenance remain blocked by the existing checks. Every contract's integration field is `verified` (an integration acceptance, or an interaction or integration test of a pair or group that includes the part, passed with intact bytes), `declared` (such a test exists but has not passed) or `not-recorded`. Passing a package or baseline check does not supply missing integration evidence. In design mode, not-run tests are expected rather than pending, and the last pending item is the implementation authorization: the user's explicit approval and an isolated output root, recorded before the mode changes.

An optional manifest is checked with the existing registration parser. Only exact IDs and source URLs join; source mismatches and absent donors block the view. Run-only donors remain explicit, and manifest metadata never qualifies a donor. No fuzzy matching, alias merging or state import occurs.

Recorded test `status` remains the author's status even if its bytes are invalid; inspect `integrity`, `errors` and `validation_errors` before relying on it. Changed/missing oracle or raw bytes, missing receipts and failed controls cannot silently pass. `current-bytes-consistent` checks only current bytes and structural counts. The record has no receipt timestamps, so temporal freshness is always unknown. A scheduled item, selected design, implementation declaration, passing check or packaged artifact never establishes demonstrated benefit. The helper leaves benefit not established and preserves existing independent-review gates; it cannot authenticate reviewers or observations.

The authored interruption cases exercise recovery, missing integration, failed controls, stale bytes, deferrals, conflicting ownership and disconnected joins. They do not measure independent human recovery effort, general agent effectiveness, runtime product benefit or host qualification.
