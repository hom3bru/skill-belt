# Evaluation and the recorded-output helper

Use the recipient's established harness when it provides the appropriate oracle and population controls. The bundled helper is an offline descriptive utility, not an experiment runner or a substitute for those controls.

## Declare the experiment

Record task and decision contracts, allowed approximation, critical errors, abstention policy, relevant population, unit/group/stratum definitions, construction/validation/final splits, exposure history, baseline/candidate identities, evaluation method, budgets, stopping rule, and deployment restrictions.

Keep declared facts distinct from verified facts. Teacher labels establish teacher agreement. Synthetic cases establish behavior on authored cases. Neither becomes independent natural-population accuracy through a hash, a second model, or repeated evaluation.

Use matched inputs and information access. If a baseline has external knowledge, a different time reference, a hidden cache, or a richer input, name it. When the treatment intentionally changes acquisition or available information, evaluate that as a different intervention rather than claiming algorithm-only benefit.

For inference, choose a method suited to the task, independent unit, pairing, sampling, and stopping rule. Cluster correlated cases. Select sample size based on the effect/tolerance and variability. Do not interpret an interval crossing a declared tolerance as support. Repeated candidate selection requires accounting for multiplicity or a fresh final evaluation.

## Reuse the existing study contract

Apply the [study identity and recovery checklist](mechanisms.md) when the recipient already has an experiment facility. Bind source, lock/dependency, interpreter/admission, evaluator, runtime, effective configuration, sealed inputs/oracle, and prior exposure. Preserve exact issued run/result references and distinguish fresh execution from verified reuse. The helper does not replace those controls or evaluate source-to-value relationships.

For gate/ranker/router conversions, freeze the population before selection and retain both arms' admitted/deferred/skipped decision vectors at the same allowance. Quality among selected cases does not measure discarded opportunities. Keep case identity independent of predicted values and retain judgment revisions without counting repeat evidence/reviews as independent cases. See mechanisms.md for routing counterfactuals, population-mix diagnostics and joint-output controls.

## Separate outcomes

Report correctness, accepted-case precision/quality, coverage, appropriate and unnecessary abstention, critical errors, errors/timeouts/missing outputs, end-to-end effect, runtime model calls, construction and operating costs, latency, repeatability, maintenance, and invalidation conditions.

A result may be correct but expensive, cheap but wrong, stable but incorrect, accurate only on a narrow subset, or promising but underpowered. Report these dimensions separately. A composite score requires an explicit decision policy and visible component values.

For stochastic systems, retain per-run and per-item outputs and deployment identity. Cache replay is not a fresh execution. For model-free claims, inspect transitive dependencies and use authorized runtime instrumentation or a suitable no-provider/no-network trial. Supplied zero counts alone cannot prove absence of inference.

## Actual helper commands

Python 3.10+; standard library only. Replace SKILL_DIR and the input paths with real paths:

~~~text
python "SKILL_DIR/scripts/compare.py" hash "cases.json"
python "SKILL_DIR/scripts/compare.py" compare --cases "cases.json" --baseline "baseline.json" --candidate "candidate.json"
~~~

The first validates a case set and prints its exact-byte SHA-256 and case count. Freeze the case file, then put that digest in both arm files. Whitespace changes alter the digest. The second validates and summarizes the records, prints JSON, and changes no input files. Redirect stdout to an authorized output file if needed.

Exit 0 means a descriptive report was produced, even if the candidate gets every case wrong. Exit 2 means invalid input or command usage. Neither status declares product acceptance. No candidate source is imported or executed, and no network/provider call is made by the helper.

## Case-set format

~~~json
{
  "schema_version": 1,
  "task_id": "bounded-decision",
  "oracle": {
    "kind": "synthetic",
    "source": "authored development contract",
    "independent_of_candidate": true
  },
  "cases": [
    {
      "id": "case-1",
      "group_id": "family-1",
      "stratum": "ordinary",
      "language": "ja",
      "expectation": {"status": "answered", "output": "東京"}
    },
    {
      "id": "case-2",
      "group_id": "family-2",
      "stratum": "missing-evidence",
      "expectation": {"status": "abstained"}
    }
  ]
}
~~~

Required root fields: schema_version, task_id, oracle, cases. Optional description is a nonempty string. Oracle kind is reference, human-adjudicated, synthetic, or teacher; source is a nonempty provenance statement; independent_of_candidate is a caller declaration, not verified custody.

Each case requires id, group_id, stratum, and expectation. Optional language, input_ref, and input_sha256 record provenance; the helper does not open input_ref or verify that referenced artifact. There are no automatic exclusions or weights. Exclude unsupported units explicitly before freezing and retain their flow record in the study outside this file.

Expectations have status answered with a required output (including explicit null), or status abstained without output. An expected abstention can therefore be correct; a candidate abstaining on an answerable case is incorrect.

## Arm format

~~~json
{
  "schema_version": 1,
  "arm_id": "candidate-v1",
  "case_set_sha256": "EXACT_DIGEST_RETURNED_BY_HASH_COMMAND",
  "provenance": "recorded by an authorized project harness",
  "records": [
    {
      "case_id": "case-1",
      "status": "answered",
      "output": "東京",
      "runtime_llm_calls": 0,
      "latency_ms": 0.2,
      "cost_usd": 0
    },
    {
      "case_id": "case-2",
      "status": "abstained",
      "reason": "required evidence is absent"
    }
  ]
}
~~~

The digest token in this explanatory example must be replaced before use. Working, fully populated synthetic examples are in assets/.

Required root fields: schema_version, arm_id, case_set_sha256, records. Optional artifact_ref, artifact_sha256, and provenance are declarations; an artifact hash is validated for shape but not re-read or authenticated. Baseline and candidate arm IDs must differ.

Each prediction requires case_id and status answered, abstained, or error. Answered requires output; other statuses forbid it. Optional error and reason are nonempty strings. runtime_llm_calls is a nonnegative integer or null; latency_ms and cost_usd are finite nonnegative numbers or null. Missing measurements remain unknown. Prediction order does not matter. Unknown or duplicate case IDs are rejected. Missing predictions become missing outcomes.

## Quantities and limits

- eligible: every case in the frozen case set.
- correct: strict output match for expected answers, plus appropriately matched abstentions.
- accuracy: correct divided by eligible.
- coverage: answered divided by eligible.
- answer_precision: correct answered outputs divided by answered; null when nothing is answered.
- incorrect_answered, errors, abstained, missing: visible counts without denominator deletion.
- group_all_correct: number of caller-declared groups whose every case is correct; descriptive only.
- strata: the same descriptive counts, accuracy, and coverage per declared stratum.
- paired: both correct, both incorrect, baseline-only correct, candidate-only correct on the same cases.
- measurements: reported_cases, unknown_cases, reported_sum, and total; total is null unless every eligible case supplies that measurement.

The sum of per-case latency is not batch wall-clock time or a latency percentile. Runtime/cost fields are supplied measurements, not observations made by this utility. A total of zero runtime calls still leaves runtime_model_freedom_verified false.

Equality sorts JSON object keys but preserves array order, case, Unicode text, and boolean-versus-number distinctions. Integer values are decoded exactly (so -0 and 0 coincide); decimal/exponent output tokens retain their spelling without binary-float rounding. Thus 1, 1.0, and 1.00 differ, as do distinct large decimals. This is strict representation matching, not mathematical equivalence. Latency and cost measurements use finite floating-point aggregation and may be rounded; they are separate from output equality. Task-specific normalization must be independently specified and applied in the project evaluator before creating comparable values. No fuzzy match, custom code evaluator, confidence interval, statistical test, noninferiority gate, or promotion gate is bundled.

Each UTF-8 JSON input is bounded to 16 MiB; case and record lists are bounded to 100,000 entries. Duplicate JSON keys, unsupported schema versions, unknown fields, malformed statuses, invalid digests, and nonfinite/negative measurements are rejected. Input documents remain untrusted data.

## Testing Rule Or Reason

Package validation and helper unit tests check package mechanics. A forward trial checks how an agent follows instructions on that particular scenario. Neither proves a general improvement.

For qualification, freeze representative tasks containing obvious conversions, partial opportunities, unsuitable reasoning tasks, missing evidence, unfamiliar languages, multilingual inputs, dynamic dependencies, and deceptive teacher labels. Compare the same agent with and without this skill at comparable budgets. Use independent graders and repeated runs where necessary. Score useful supported conversions, incorrect acceptance, appropriate abstention, generalization, user outcome, effort, and permission preservation. Retain negative results and all attempts.
