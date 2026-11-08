# Offline studies, schema v2

Use `compare.py` for unchanged schema-v1 inputs. `study.py` requires explicit schema_version 2. Both use the strict v1 matcher (exact decimal tokens, Unicode, bool/number distinction), bounded JSON loader, duplicate-key rejection and measurement validation. Standard-library Python only. No candidate, model, subprocess or provider is executed by `study.py`; the unit suite may run the local CLI.

When a recipient already has its own shadow and statistics facility, use that facility (and any local private navigation profile), not this generic inference path. For correlated units the helper returns Insufficient evidence rather than pretending cases are independent. Repeated stochastic runs remain separate studies; v2 does not implement replicate aggregation or multiplicity control.

## Request interface

`python scripts/study.py COMMAND --request request.json` prints one JSON result and changes no input files. Exit 0 means a result was produced, including rejected plans and unsupported conversions. Exit 2 means invalid input. Redirect output to an authorized artifact. Each request embeds the following named JSON objects; unknown request fields fail. Omitted required fields fail.

| Command | Request fields | Result |
| --- | --- | --- |
| obligations | source, plan | passed + named issues; declared maps only |
| cascade | case_set, baseline, candidate, case_hash, threshold | arm + per-case flow |
| score | same as cascade; optional split, allowed | all three arms, flow counters, provenance exclusions |
| sweep | case_set, baseline, candidate, case_hash, thresholds, policy | development utility/coverage/wrong for each threshold, chosen threshold |
| seal | case_set, baseline, candidate, case_hash, policy, threshold, source, plan | immutable study content and digest |
| decide | case_set, baseline, candidate, case_hash, policy, seal, source, plan | one of four scoped verdicts and reasons |
| packet | case_set, baseline, candidate, case_hash, seed, agreements | public packet + private sealed_key |
| ingest | case_set, packet, key, answers, case_hash | revised case_set + sampled shared-error estimate |

`case_hash` is the exact-byte SHA-256 of the frozen case JSON file, supplied by its custodian. APIs take decoded objects plus this digest, as v1 does. The seal additionally binds a semantic case-content digest, so changing decoded cases while retaining the old byte-hash token fails `decide`. Semantic hashes preserve decimal-token spellings through the v1 serializer; they do not equal pretty-printed file hashes. Hashes provide consistency, not authentication, timestamps or proof that holdout was never seen. Freeze and retain the seal before running the final arm. Any renewed tuning/exposure needs a fresh study and holdout.

`python scripts/demo.py` generates the seeded synthetic end-to-end result. `demo.fixture()` exposes the complete worked case, arm, policy, obligation source and plan objects; it is not a production rule or a qualification pilot. `assets/obligations-request.json` is a small directly runnable CLI request.

## Cases and predictions

V2 case-set root uses the v1 fields, with schema_version 2. Oracle kind additionally allows model-adjudicated. Each case adds required `split` (development or holdout), optional `input` (sanitized data for adjudication), `label_source` (reference, human-adjudicated, model-adjudicated, synthetic, teacher), `independent_of_candidate` (boolean declaration), `label_arm_id` (originating arm when labels came from an arm), and `critical` (a contract violation on this case is critical). Other v1 optional fields still work. Group IDs cannot cross splits.

V2 arms retain v1 fields and require `artifact_sha256`. Optional threshold, components and fallback_authorized are declared treatment metadata. Each prediction retains v1 fields and optionally declares input_valid, applicable, output_valid, evidence_valid, conflict, score [0,1] and critical_error. All flags are booleans. Acceptance requires explicit true input/applicability/output/evidence checks, no conflict, answered status and score at least threshold. Absent score is zero. Missing records and errors remain eligible; invalid output/evidence fails closed. Each cost measurement includes all first-stage routing, validation and local specialist work. Fallback costs are added only when deferred; unknown components keep the total null. Zero model-call counts authenticate nothing.

Scoring returns eligible, gated_out, attempted, valid, correct, wrong, abstained, failed, fallback and deferred. These are stage counters, not disjoint buckets: eligible partitions into gated_out + abstained + failed + accepted (accepted = eligible - fallback). Attempted excludes gated-out and missing rows; valid means a structurally/evidentially valid answered first-stage output, including a valid answer deferred below threshold. Correct/wrong describe hybrid final contract outcomes, including missing/fault outcomes. The per-case flow explains the overlap. Ordinary baseline, candidate and hybrid summaries retain missing predictions and abstentions in their denominators.

Routed coverage is first-stage accepted / eligible. Teacher agreement is exact agreement with baseline among accepted cases; it is imitation, not truth. Correctly routed coverage is accepted-and-declared-correct / eligible. Descriptive counters can include teacher/self labels, but `excluded_labels` flags them and `decide` excludes them from verdict evidence. A verdict requires all holdout labels to be independent, policy-allowed and not from either evaluated arm. All provenance_verified/runtime_model_freedom_verified flags remain false.

## Blinded adjudication and agreement sampling

Compose the hybrid first if that is the target comparison, then call packet on baseline versus hybrid. It includes every output/status disagreement plus N seeded random agreement cases. Item IDs and A/B assignments are shuffled. Expectations, provenance, case IDs and arm names are absent. The custodian must sanitize `input` itself to remove arm-identifying or answer-leaking content and supply adequate evidence. Missing input is visible null; it must not be adjudicated as if evidence existed.

Separate packet from sealed_key immediately: give only packet to the adjudicator. Seed and full key stay with the custodian; hash commitments are not encryption or an access-control system. An adjudicator who receives the returned bundle was not blinded.

Answers require schema_version 2, packet_sha256, blind:true, key_disclosed:false, label_source human-adjudicated or model-adjudicated, independent_of_candidate boolean, and records [{id, expectation}]. Expectation uses the v1 status/output contract. Ingest rejects explicit nonblindness, key disclosure, packet/key tampering, duplicate/unknown IDs or incomplete answers. It cannot detect a lying declaration. It retains sampled agreement n, shared_errors and error_rate; this estimates shared error on sampled agreements only. It does not treat the biased disagreement-heavy sample as whole-population absolute accuracy. Unadjudicated teacher-labelled cases remain excluded; a floor verdict may therefore remain Insufficient evidence. Ingest changes case-set content: reissue exact-byte hashes on arm envelopes and seal a newly identified independently evaluated study; do not claim a pre-existing seal survived relabeling.

## Policy, bounds and verdict

Policy requires schema_version 2, quality:{kind:floor|noninferiority,value:[0,1]}, critical_error_cap, coverage_target, confidence in (0.5,1), label_sources (nonempty; teacher forbidden), independent_units:"case", and utility:{correct,wrong,fallback} (finite signed weights). A noninferiority value is the allowed loss, so compare the paired interval against -value. `critical` cases count every hybrid failure as critical; explicit critical_error flags also count. Missing critical-error annotations cannot establish that a task's critical error taxonomy was complete.

Sweep reads development outcomes only, maximizes the declared utility, and breaks ties toward higher thresholds. This heuristic does not certify a threshold. Freeze the chosen threshold and policy before holdout; declare candidate.threshold to match the seal. Seal binds policy, case bytes and content, both artifact/arm identities, source/plan and threshold. Any mismatch is invalid input. `decide` checks obligations again; failed obligations, excluded labels or repeated holdout groups block support.

Proportions use two-sided Wilson score intervals. Paired differences use Newcombe's paired method 10 (Wilson square-and-add with adjusted correlation), alongside an exact two-sided conditional McNemar p-value. Wilson/Newcombe intervals are approximate, **not exact confidence guarantees**; McNemar is exact. The design explicitly permits Wilson. Confidence is per component, not joint/simultaneous; no multiple-testing or sequential-stopping guarantee is claimed. A zero observed critical count still has a positive upper bound, so a zero-risk cap cannot be certified from finite data. McNemar tests equality, not a noninferiority margin; the declared margin is judged using the paired interval.

Support requires lower quality/coverage bounds and upper critical-error bound to meet policy, plus the obligation check. Any residual fallback produces Bounded conversion supported; no fallback produces Conversion supported. A requirement wholly outside its interval yields Conversion not supported. A crossing interval or missing evidence yields Insufficient evidence. These verdicts concern these supplied records and policy only; they execute nothing and confer no promotion authority.

## Published numerical controls

- [CAMIS Wilson worked example](https://psiaims.github.io/CAMIS/SAS/ci_for_prop.html): 36/154 at 95%, 0.17390–0.30659.
- [CAMIS paired Newcombe worked example](https://psiaims.github.io/CAMIS/R/ci_for_paired_prop.html): table [[20,15],[6,5]], 0.002602–0.369943.
- [Newcombe's original paper, Table III](https://www.site.uottawa.ca/~nat/Courses/csi5388/Newcombe.1998.pdf): method-10 table (36,12,2,0), 0.0569–0.3404; (0,30,0,0), 0.8395–1; (27,0,0,27), -0.0351–0.0351. These exercise negative correlation and boundaries. Only positive correlation gets the continuity correction.
- [University of Zurich example](https://rdrr.io/rforge/biostatUZH/man/confIntPairedProportion.html): Altman table 6.2 [[14,5],[0,22]]; exact two-sided McNemar is 2/2^5 = 0.0625 (the last arithmetic is derived).

Tests compare these fixed values, edge cases and the seeded control arms. This validates numerical mechanics, not the independence assumptions, real-world contract, effectiveness of the skill or provenance custody.
