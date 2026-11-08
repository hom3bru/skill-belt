# Lifetime and economics record (optional template)

Extend the recipient's existing study/artifact record when present. Otherwise retain a small file beside the experiment. This is a worked record, not a new registry or runtime.

Record artifact + interpreter identity; operation contract and accepted inputs; source/policy/dependency/tool/model versions; case/oracle/exposure seal; last qualification and evidence owner; source-bound witness; downstream consumer; partial effects/checkpoint; counterexamples; expiry and deoptimization triggers; rollback/retirement owner and event. A name or prompt alone cannot establish reuse compatibility.

## Worked identity record

`assets/lifetime.json` contains two assets and distinct dependency closures. `rule` depends on source, policy and interpreter; `source-cache` depends only on source and serializer. Its comment/reviewer annotation is outside execution identity. Reuse requires every recorded closure member to match the present value. Thus a policy or interpreter change invalidates `rule` only; a source change invalidates both. An unrelated annotation invalidates neither.

Before resuming, reconcile any partial write with its actual downstream consumer and retained witness. `partial` is not `complete`; do not silently replay. A checkpoint is complete only when the consumer acknowledges that exact value/witness and effect identity. The example stays `partial`, with explicit operator reconciliation and no replay. Tests check this retained record; they do not implement effect recovery.

## Economics worksheet

`net = avoided incumbent work - candidate runtime - routing/check/fallback - design/synthesis/label/eval - monitoring/revalidation/migration/retirement`.

Use measured volume over a plausible validity horizon; record cold/warm setup and tail latency separately when material. Include local embedding/specialist compute and fallback costs. Unknown costs propagate to unknown net value. The fixture expresses volume as net events (negative values can represent reversals); it never clamps a loss to zero. A cold start with zero events costs 30 units, so net is -30. With -2 net events, unit benefit 3 and setup 30, net is -36. A warm 20-event case yields 30; the 10-event break-even point is a sensitivity calculation, not a predicted workload.

This record is synthetic and unqualified. Any real deployment needs its project's checks and the owner's applicable authority.
