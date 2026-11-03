# Mechanisms for bounded conversion and reliable experiments

Read this when a conversion involves extraction, rule induction, generated artifacts, or an existing experiment facility. These are portable design lessons from source inspection, including observed source-level limitations. They are not copied implementations or proof of recipient benefit. Concrete project citations and checkout identities remain in the owner's local research record.

## Preserve the decision owner and its evidence

Identify the component that owns entity/event selection and each critical output. A downstream formatting or enrichment rule should not acquire authority to select a different entity or transaction simply because a matching number appears elsewhere. When that authority must change, propose an upstream algorithm with its own acceptance tests.

For evidence-bearing tasks, retain a decision witness: source version/hash, coordinate convention, exact spans, selected and rejected candidates, rule/interpreter identity, and contradiction/abstention reasons. Update a value and its witness together. Reject a patch whose source no longer matches, whose evidence belongs to another candidate, or whose existing provenance graph cannot be preserved. Matching text is not proof that the text supports the intended relation.

Coordinate units matter across languages: UTF-8 bytes, UTF-16 code units, Unicode code points, and graphemes are different. Preserve the canonical document before trimming or normalization, or retain an explicit reversible offset map. Test leading whitespace, repeated mentions, non-BMP characters, and the same value attached to a different subject.

**Discriminating control:** supply the correct value with evidence from the wrong entity/event. It must not pass an evidence-grounded decision merely because the value matches. The bundled JSON helper cannot check this relationship; use the task evaluator.

## Bound the generated artifact, then identify its whole execution closure

Prefer an existing trusted interpreter for a small data-only rule artifact when it can express the required change. State writable fields, immutable identities, admitted operators/patterns, size/resource bounds, and ordering semantics. A successful schema or pattern check establishes admission, not semantic quality or OS containment.

Bind candidate identity to the artifact, parent component, interpreter version, admission-validator version, evaluator, runtime, and effective configuration. Hashing only a generated rule list misses behavioral changes in its interpreter. If the language cannot express the proposed fix, say so; do not emit inert source strings and count them as an evaluated candidate.

A rule already present in the recipient is not a new contribution. Trace the real entrypoint through materialization to the interpreted effect. Compare with a disconnected candidate to establish that the evaluation reaches it.

## Validate the received envelope before normalizing it

Keep raw received bytes and parse outcome. Validate original version, required/unknown fields (including nested predicates), types, bounds, and legitimate metadata before constructing the internal representation. Do not replace a supplied unsupported version with the current version, discard unknown members, and then claim that the original proposal passed validation. A documented migration is a different transformation with its own identity and tests.

**Discriminating controls:** unsupported version plus a valid inner rule, an unknown envelope field, duplicate keys, malformed rules, and a legitimate empty proposal. Distinguish invalid input from an explicit decline to propose a rule. Do not use a repair that merely deletes evidence of the invalid member.

## Separate no effect, refusal, fault, and partial application

A nonmatching rule, a matched rule with no value change, an evidence-based refusal, an invalid artifact, and an interpreter exception require different diagnostics. Do not relabel a fault as normal abstention or quietly retain an unreported successful prefix.

Choose the effect contract explicitly. For an atomic rule bundle, stage changes and publish them only after the bundle completes; a fault discards staged effects. If partial application is intended, report the committed prefix, failed operation, resulting state, and recovery/retry behavior. Preserve the input and test both the intended success and a fault after an earlier successful operation.

For external effects, a crash can leave the outcome unknown. Reconcile the operation identity and external state before retrying. Neither rollback nor idempotency can be assumed from a pure-looking function signature.

The helper's per-case error status is descriptive. It does not implement bundle transactions, effect reconciliation, or these finer diagnostics.

## Seal information exposure and execution identities before evaluation

A useful study seal covers source and lock/dependency identity, candidate/baseline configurations, input snapshot, oracle/evaluator, runtime, budgets, sample/cluster rules, and prior exposure. Record pilot cases, prior inspected results, and whether a final set has been used for selection. A later source, oracle, configuration, or exposure change invalidates the old seal for the affected claim.

Separate shared controls from intentional arm differences. Freeze each arm's declared source/configuration treatment and reject later drift from that treatment; do not reject the experiment merely because its configurations intentionally differ. Use the same inputs and information access for paired arms unless the intervention explicitly changes them. Preserve failed, missing, and blocked arms. Derive results from the sealed eligible population rather than from whichever output files happened to exist. A saved score or self-declared result reference is not authoritative merely because its JSON parses.

When the project already issues study/run/result references, validate and reuse them. Reconcile exact issued references and rederive claims from the underlying sealed records where that interface supports it. Do not invent a second score issuer or run lifecycle in the generic skill.

## Resume work without silently rerunning it

Track scheduled, claimed, running, completed, failed, and interrupted states with durable operation/run identities when the existing system supports them. A verified complete output may be explicitly reused; record that it is reused rather than fresh execution. Retain failed attempts. Reconcile missing outputs and stale claims under the existing contract before scheduling new work.

A status marker is not a verified output, a copied database is not independent-label custody, a clean checkout is not a sandbox, and a registered host runner is not production authority. Inspect the actual command capability and its writes before invoking it. Prefer a read-only capability/status interface for discovery; authorization for investigation does not authorize persistent study writes or evaluation spend.

## Treat learned boundaries as results, not universal laws

Group failures by a falsifiable mechanism rather than by one publisher, entity name, or successful example. State whether the answer is absent, ambiguous, outside the artifact language, inaccessible because of source acquisition, or present but not recoverable by the tested candidate. Those imply different next steps.

A deterministic project can teach reproducible correction and evidence attribution without imposing its model restriction on a multiproject lab. A lab can teach experiment identity and retained failures without justifying a new orchestrator in a small recipient. Preserve these analogy limits when transferring the lesson.

## Make oracle revision and learning eligibility explicit

Keep the engine's explanation separate from the independent assessor's answer, verdict and reason. A generated label, a diagnostic review, a revealed result, and evidence authorized for further learning are different records. Use the recipient's actual custody/release policy.

Represent unavailable source, partial coverage, uncertainty and an inspected source that does not state the answer separately. Unavailable evidence cannot establish absence. A correction should append a source-bound adjudication rather than rewrite the historical grade. Bind released learning evidence to its answer/source/field contract and revision watermark; a new source or answer invalidates that release until rechecked.

**Discriminating controls:** change the oracle answer or recover a different source after release; the old eligibility/result must not silently survive. Try to classify an unavailable document as not-stated; the evaluator should retain uncertainty instead. These controls concern a project evaluator and are not implemented by the generic helper's caller-declared oracle field.

## Propose against the current parent, not a historical story

Replay a reported failure against the current parent/configuration before paying to fix it. Distinguish reproduced current errors from already-fixed historical corrections. Preserve current successes and their evidence, and carry explicit counterexamples into the proposal.

Reuse a previous attempt only when its parent, population, configuration and exposure identity still apply. A repeated failed rule with the same evidence is not new research merely because it has a new description. Bound context excerpts and retain omitted-row counts so a concise brief is not mistaken for the whole corpus.

## Retain a comparator and qualify rollback evidence

Before activation or retirement, preserve the incumbent and declare the independent evidence, exact paired input identity, thresholds, minimum information and authority for rollback. A shared URL is not the same document version; current execution identity and graded source hash matter. Consistency checks or surrogate metrics can trigger investigation without establishing semantic quality.

Do not copy a donor's sample thresholds, estimator, one-bit disclosure mechanism, or statistical labels as universal policy. A caller-supplied significance flag is accounting data, not an independent evaluator. A diagnostic acceptance and production activation can be different authorities; trace the actual gate caller before describing either as enforced. Rule Or Reason adds no background sentinel or automatic rollback authority.

## Preserve different approaches without calling them winners

During bounded exploration, retain genuinely different mechanisms—such as a parser, structured lookup, finite-state procedure, or learned specialist—when they illuminate different parts of the boundary. Keep exploration value distinct from correctness, accepted coverage, measured cost and a selection verdict. A candidate retained for different behavior may still be dominated on measured outcomes.

Derive a mechanism description from inspected behavior and dependencies. A caller-supplied hash or a constant label cannot prove diversity or enforce a taxonomy. A cost axis present in a schema but lacking measurements is unknown, not an optimized objective. Use an existing archive if useful; do not add one to a small task merely to follow this reference.

## Diagnose population changes and bundled interventions

Use the current real workflow as the primary comparator, alongside a simple baseline where informative. If the candidate also changes source acquisition, caching, prompt/context, model choice, or review policy, declare those interventions and isolate their effects where the decision requires attribution. A two-factor bundled change may need a 2×2 comparison; this is a question-specific design, not a universal requirement.

If corpus versions differ, report within-stratum rates, stratum weights and newly unmatched strata. An easier mix can raise aggregate accuracy without an improved algorithm; a harder mix can lower it while every shared stratum improves. A rate/mix decomposition is a diagnostic and does not recover the causal effect that a frozen paired comparison would identify. The bundled helper reports declared strata but implements no mix decomposition or causal attribution.

## Make timing resolve the actual performance decision

Retain warmup policy, cold/warm scope, repeated durations, unit counts, execution order, thrown/timeout outcomes and actual end-to-end time. Rotate or counterbalance order when cache, thermal, background load or source-service timing can favor an arm. Repeated effects require their own state/replay/authorization contract.

Judge the declared limit with uncertainty appropriate to that measurement. Relative variation can be diagnostic while the full justified interval is safely within a limit; an interval crossing the limit is inconclusive. If no valid interval is available, a point estimate does not satisfy a requirement for interval-based evidence. Timing repeats do not add independent semantic correctness cases, and the sum of supplied per-case latency is not wall time.

## Account for selection before the candidate runs

For gate, ranker, router or intake conversions, freeze the population before selection, the decision clock, feature values, policy/configuration versions and resource allowance. Retain every admitted, deferred, skipped and unavailable decision under both arms. Evaluate what downstream work was lost or gained, not just quality among the selected cases. Frozen replay should use captured features rather than today's mutable ranking tables.

A candidate can appear equivalent because the evaluated subset excludes the cases its gate discarded. Test a decision reversal under the same budget and keep that counterfactual visible. The recipient's ranking weights are product policy; a replayable ranking is not evidence those weights are optimal.

## Retain downstream work before marking input consumed

Locate cursors, ETags, offsets, deduplication keys and acknowledgment writes that stop an input from being revisited. Commit consumption only after the dependent output or durable recovery work is retained. Test interruption immediately before and after that boundary, including the case where a later retry would otherwise deduplicate away unfinished work.

Distinguish transport failure, parse failure, unchanged input and successful processing. A cache validator may establish protocol-level reuse but not unchanged semantic dependencies. Apply this lesson through the existing queue/checkpoint contract; it does not justify building a queue for a small pure function.

## Evaluate joint coherence and derived-state invalidation

For structured outputs, build and select a coherent candidate relation before filling authoritative fields. Individually plausible fields can combine two different entities, transactions or time periods into a false record. Declare tie behavior and test reordered equivalent observations, distinct equally plausible candidates, historical mentions and conflicting evidence. Source order is not a neutral tie-breaker.

State which outputs the replacement may change, which upstream authority it preserves, and which derived records must be invalidated or rebuilt together. Updating a field while retaining an old semantic graph, policy decision, aggregate, cache entry or provenance projection can leave internally inconsistent output. Verify the real caller actually uses the claimed authority; an imported or documented policy function can be unwired.

## Keep case identity independent of the predicted answer

Use immutable input/case identity, independent-unit grouping, observation/evidence identity, prediction identity and judgment revision for their different purposes. A corrected predicted amount or name must not create a new evaluation unit and erase the old failure. Count near copies, evidence-row unions and repeated reviews according to their real dependence, not as new independent corroboration.

Retain source attribution at judgment time and a revision/supersession order. Later diagnostic acceptance is not automatically independent field-level ground truth. Check migration and fallback paths before claiming an existing repository has fully adopted a stronger identity design.
