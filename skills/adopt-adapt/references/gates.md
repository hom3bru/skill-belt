# Structured coverage and measurement gates

New runs bind schema **3** in `inputs.json` and require `intake.json` v1. Schema 2 keeps its existing gates. Schema 1 stays legacy with unverified coverage and cannot pass `--complete`.

## Workflow

1. Initialize the source × recipient queue. Resolve identities and capture/read the actual evidence using the existing record helpers.
2. Update the seeded intake nodes and each READY pair's basis/experiment. Partial work validates and renders with its actual outstanding work; there is no forced DISCARD.
3. Save `run.json` and use `finalize` for readback and checked rendering. Add `--complete` only when claiming complete coverage; partial work remains valid. Separate `record-readback`, `validate`, `render` and `check-output` commands remain available.
4. Preserve the generated contract/coverage/recording header and unresolved rows. Exact output checks reject stripped content; they do not intercept unseen chat text.

```text
python -B "<skill-directory>/scripts/aa.py" init RUN --source URL --recipient app=generic
python -B "<skill-directory>/scripts/aa.py" finalize RUN/run.json --complete --output RUN/report.md
python -B "<skill-directory>/scripts/aa.py" queue-extend RUN/run.json NEXT_RUN --source CHILD_URL --reason "New linked artifact"
```

`queue-extend` creates a fresh, exclusive run revision. It preserves old IDs, state history and captured bytes, adds each new source for **every** selected recipient, and records parent snapshots/lineage. The previous run is untouched. Existing/overlapping destinations and linked paths are refused. Work continues at the returned new `run.json`; readback/indexing is pending again. Do not hand-edit the old immutable input queue to hide a discovery.

## Intake nodes

`intake.json` binds `inputs_sha256` to the canonical input manifest and contains one `artifacts` node per source ID. The initializer seeds all fields. Complete coverage needs closed discovery, accounted background research, sufficient captured scope and every registered pair READY.

- `coverage` maps roles to `{state, surface, evidence, note}`. State is `read|not-applicable|unknown`; surface is `full-text|selected-source|abstract|metadata|media`. Read/NA rows cite read same-source captures. All sources need actual body evidence; repository roles are `map,entrypoint,callers,configuration,tests`, paper roles `method,results,limitations`. Explain scoped NA; unknowns remain visible. Abstract/metadata alone cannot establish a paper's method/results/limits, nor can error, empty or login stubs establish a body read. Unread scope may support INCONCLUSIVE, not a completed transfer or negative finding.
- `links[]`: `{url,resolved,source,classification,evidence,reason}`. Source is a queued ID or null; classification `research|non-research`. URLs extracted from read text/HTML/Markdown captures must be accounted for. Relative links use the capture's HTTP origin or source locator. Research edges need matching source identities and their recipient pairs; changed original/final identities additionally cite `resolution_evidence` containing both URLs. Navigation exclusions need reasons. Keep all parent edges and aliases.
- `named_works[]`: `{name,lookup}` points to `lookups[]`: `{id,query,method,status,evidence,matches,note}`. Status `found|not-found|blocked`; found matches name queued source IDs. Declared named work without a resolved lookup stays outstanding. A social source with no research links still needs a recorded background/project search. Background `{status:pending|checked|not-needed,note}` records useful research or why it adds nothing for this scope.
- `attempts[]`: `{method,url,outcome,evidence,note}`, outcome `content|error|stub|not-found`. Captured failures cannot be reused as successful read evidence. `retrieval` records available methods, exhausted boolean and next_step. Exhaustion requires distinct actual methods, all declared alternatives and a next access step; a first failed reader does not establish exhaustion. Honest blocked partial work remains valid.

The parser checks links in supplied read text captures and the declared graph. It cannot discover every hidden media link, identify every unnamed work, authenticate remote origins or decide whether a navigation exclusion is semantically honest. Review those claims against the actual source; never describe this as exhaustive live-web discovery certification.

## Keep uncertain-value experiments open

Every READY v2 `decision` adds:

```json
{
  "basis": {
    "reason": "proposal", "unit": "named smallest mechanism",
    "baseline": "current recipient behavior", "benefit": "hypothesis, not measured gain",
    "added": "burden added or unknown", "removed": "burden removed or unknown",
    "alternative": "smallest local alternative", "evidence": ["SOURCE_CAPTURE", "RECIPIENT_CAPTURE"],
    "measurements": []
  },
  "experiment": {
    "state": "proposed", "hypothesis": "what could help", "baseline": "comparison baseline",
    "test": "smallest isolated discriminating test", "criterion": "quality/correctness and resource criteria",
    "reopen": "what result would change the decision"
  }
}
```

Allowed reasons: `proposal,unresolved,research-lead,no-benefit,assumption-mismatch,net-burden,policy,already-covered`. Purpose/domain/language and missing measurements are invalid rejection reasons. A blocked experiment keeps the same fields plus `condition`, naming what would make a lawful discriminating test possible. This proposes a test; it does not authorize execution.

DISCARD needs an evidenced negative basis or retained `research-lead`. A cost/bloat rejection needs donor and recipient facts about the transfer unit and a measured, static or estimated burden basis. Unknown costs cannot justify rejection. Estimates and an unmeasured pilot can support ADAPT-with-prerequisite. No universal numeric cutoff applies.

Schema-3 retained leads add `flips_to` (ADAPT or ADAPT-with-prerequisite), `seam_evidence` (read recipient IDs), and `cluster` (one ID per recipient and matching test). Match `promising_check` to `test`. Mismatch rejections name `basis.assumption` and cite read donor and recipient evidence.

Identical `shared_prerequisite: {id,test,criterion,reopen,evidence}` can group one recipient's leads. Use read recipient evidence. Optional `condition` marks a blocked prerequisite. Keep donor experiments.

A shared capture/probe may answer distinct questions when one recipient entrypoint and workload yield every observation. Put collection scope in `test`, pair-specific criteria in `criterion`, and their decision effects in `reopen`. Independent collection actions stay separate.

## Measurements and numeric claims

`ledger.measurements[]` rows have unique `id`, `status`, `metric`, `unit`, `scope`. Basis `measurements` and claim `measurement_refs` name these IDs. Keep rows consistent when sharing an ID.

| Status | Required support |
| --- | --- |
| `unknown` | note; numeric values/receipts absent or null. Unknown is never zero or measured failure. |
| `estimated` | read evidence, assumptions, and finite ordered `range:{low,high}` or qualitative text. No execution receipt or TESTED/OBSERVED upgrade. |
| `reported` | finite value plus read source capture containing that number; stays CLAIMED, not our measurement. |
| `static` | metric `captured-bytes|captured-lines|captured-files`, matching unit, and baseline/candidate `{evidence:[IDs],value}`. Values are recomputed from those selected captures; they do not establish runtime savings or full-repo burden. |
| `measured` | exact comparison payload below plus eligible same-pair execution `receipt` ID and passing positive `check` ID. |

A measured row flattens this payload beside id/status/scope/receipt/check:

```json
{
  "metric": "total-cost", "unit": "USD", "workload": "same declared input batch",
  "denominator": "per batch", "sample_size": 10,
  "baseline": {"value": 100, "revision": "PAIR_BASELINE_REVISION"},
  "candidate": {"value": 80, "revision": "PAIR_CANDIDATE_REVISION"}
}
```

The named positive execution check's JSON `detail` must equal this payload. Existing verification binds that detail to captured stdout, tool/harness/input hashes and eligible check results. Merely naming a passing receipt does not substantiate handwritten values. Revisions must belong to the pair, sample size is positive, and values must be finite. Status-specific fields reject hidden values or receipts incompatible with the declared status.

Common asserted numeric cost/performance statements require measurement references. For measured/static statements, use the helper `aa.measurement_statement(row)` verbatim as the claim text or numeric summary; it derives metric, units, workload/scope, revisions, values, percentage and direction from that row. Keep other interpretation in separate qualitative context. This prevents a toy counter's arithmetic from being attached to an unrelated production-latency claim. Estimates accept interior values of their stated ranges and may coexist with unrelated unknown costs. Reported quantities cite read source material of the claim's subject. Estimates/reported quantities remain CLAIMED. Experiment targets use the proposal or `kind:experiment, status:unvalidated, level:claimed`; no measurement receipt is needed to propose a test. The gates check declared relationships and common quantitative forms, not arbitrary prose entailment or a harness's scientific validity.

## Saved records and index receipts

`record-readback` reads actual saved JSON, checks it and records its byte hash in the sidecar. Later edits invalidate that receipt; refresh explicitly. An optional `--index index.json` is a contained captured JSON receipt `{record_sha256,source_ids,item_ids}` binding all IDs. A matching captured index is not authentication that an external catalog was updated. The report states recorded/indexed/pending scope accurately. Validation/status never writes or repairs records. Complete coverage requires checked durable recording; partial/unindexed research remains visible and resumable.
