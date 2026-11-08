#!/usr/bin/env python3
"""Offline schema-v2 study checks. Reads records; executes no candidate or provider."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import NormalDist
import sys

import compare as v1

InputError = v1.InputError
SOURCES = {"reference", "human-adjudicated", "model-adjudicated", "synthetic", "teacher"}


def require(condition, message):
    if not condition:
        raise InputError(message)


def obj(value, required, optional=(), where="object"):
    v1._object(value, required, optional, where)


def version(value):
    require(isinstance(value, dict) and type(value.get("schema_version")) is int and value["schema_version"] == 2,
            "study helper requires schema_version 2; use compare.py for v1")


def digest(value):
    """Semantic seal using v1's exact JSON-token representation, not file bytes."""
    return hashlib.sha256(v1._json_value(value, "seal").encode("utf-8")).hexdigest()


def number(value, name, low=0, high=1):
    if isinstance(value, v1._JSONDecimal):
        value = float(value.token)
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"{name} must be finite in [{low}, {high}]")
    return value


def strings(value, name):
    require(isinstance(value, list), f"{name} must be a list")
    for item in value:
        v1._string(item, name)
    require(len(set(value)) == len(value), f"{name} has duplicates")
    return value


def cases_v2(value):
    version(value)
    obj(value, ("schema_version", "task_id", "oracle", "cases"), ("description",))
    # Reuse the strict v1 output matcher and envelope validation after explicitly
    # validating v2 fields. Never normalize an unsupported envelope into validity.
    plain = copy.deepcopy(value)
    plain["schema_version"] = 1
    oracle = plain["oracle"]
    require(isinstance(oracle, dict) and oracle.get("kind") in SOURCES, "invalid label source")
    if oracle["kind"] == "model-adjudicated":
        oracle["kind"] = "human-adjudicated"  # validation adapter only
    require(isinstance(value["cases"], list), "cases must be a list")
    for row, stripped in zip(value["cases"], plain["cases"]):
        obj(row, ("id", "group_id", "stratum", "expectation", "split"),
            ("input_ref", "input_sha256", "language", "input", "label_source",
             "independent_of_candidate", "label_arm_id", "critical"), "case v2")
        require(row["split"] in ("development", "holdout"), "invalid split")
        require(row.get("label_source", value["oracle"]["kind"]) in SOURCES, "invalid label_source")
        for key in ("independent_of_candidate", "critical"):
            if key in row:
                require(type(row[key]) is bool, f"{key} must be boolean")
        if "label_arm_id" in row:
            v1._string(row["label_arm_id"], "label_arm_id")
        if "input" in row:
            v1._json_value(row["input"], "case.input")
        for key in ("split", "input", "label_source", "independent_of_candidate", "label_arm_id", "critical"):
            stripped.pop(key, None)
    v1.validate_cases(plain)
    groups = {}
    for row in value["cases"]:
        previous = groups.setdefault(row["group_id"], row["split"])
        require(previous == row["split"], "group leaks across development and holdout")
    return {row["id"]: row for row in value["cases"]}


def arm_v2(value, cases, case_hash):
    version(value)
    obj(value, ("schema_version", "arm_id", "case_set_sha256", "records", "artifact_sha256"),
        ("artifact_ref", "provenance", "threshold", "components", "fallback_authorized"), "arm v2")
    v1._digest(value["artifact_sha256"], "artifact_sha256")
    if "threshold" in value:
        number(value["threshold"], "threshold")
    if "fallback_authorized" in value:
        require(type(value["fallback_authorized"]) is bool, "fallback_authorized must be boolean")
    if "components" in value:
        strings(value["components"], "components")
    plain = copy.deepcopy(value)
    plain["schema_version"] = 1
    for key in ("threshold", "components", "fallback_authorized"):
        plain.pop(key, None)
    require(isinstance(value["records"], list), "records must be list")
    for row, stripped in zip(value["records"], plain["records"]):
        obj(row, ("case_id", "status"),
            ("output", "error", "reason", *v1.MEASUREMENTS, "input_valid", "applicable",
             "output_valid", "evidence_valid", "conflict", "score", "critical_error"), "record v2")
        for key in ("input_valid", "applicable", "output_valid", "evidence_valid", "conflict", "critical_error"):
            if key in row:
                require(type(row[key]) is bool, f"{key} must be boolean")
        if "score" in row:
            number(row["score"], "score")
        for key in ("input_valid", "applicable", "output_valid", "evidence_valid", "conflict", "score", "critical_error"):
            stripped.pop(key, None)
    validated = v1.validate_arm(plain, cases, case_hash)
    return {row["case_id"]: {**row, **validated[row["case_id"]]} for row in value["records"]}


def check_obligations(source, plan):
    """Check a declared ordered operation map, not arbitrary code or prose."""
    version(source)
    version(plan)
    obj(source, ("schema_version", "obligations"))
    obj(plan, ("schema_version", "source_sha256", "initial_inputs", "operations"))
    require(plan["source_sha256"] == digest(source), "source seal mismatch")
    available = set(strings(plan["initial_inputs"], "initial_inputs"))
    require(isinstance(plan["operations"], list), "operations must be list")
    operations = {}
    issues = []
    for op in plan["operations"]:
        obj(op, ("id", "kind", "requires", "produces", "depends_on"),
            ("max_retries", "entity", "witness_entity", "reconciliation", "consumer"), "operation")
        v1._string(op["id"], "operation.id")
        require(op["id"] not in operations, "duplicate operation")
        require(op["kind"] in ("rule", "tool", "model", "human_gate", "check"), "invalid operation kind")
        for key in ("requires", "produces", "depends_on"):
            strings(op[key], key)
        if not set(op["requires"]) <= available or not set(op["depends_on"]) <= operations.keys():
            issues.append({"check": "required_input", "operation": op["id"]})
        if "max_retries" in op:
            require(op["max_retries"] is None or (type(op["max_retries"]) is int and op["max_retries"] >= 0),
                    "max_retries is nonnegative integer or null (unbounded)")
        operations[op["id"]] = op
        available.update(op["produces"])
    require(isinstance(source["obligations"], list) and source["obligations"], "empty obligation list")
    seen = set()
    for obligation in source["obligations"]:
        obj(obligation, ("id", "kind", "operation"),
            ("max_retries", "input", "entity", "consumer"), "obligation")
        v1._string(obligation["id"], "obligation.id")
        require(obligation["id"] not in seen, "duplicate obligation")
        seen.add(obligation["id"])
        kind = obligation["kind"]
        require(kind in ("human_gate", "retry_cap", "required_input", "witness_owner", "reconciliation", "consumer"),
                "unknown obligation kind")
        op = operations.get(obligation["operation"])
        if op is None:
            issues.append({"check": "unmapped_obligation", "obligation": obligation["id"]})
            continue
        good = True
        if kind == "human_gate":
            good = op["kind"] == "human_gate" and bool(op["produces"])
        elif kind == "retry_cap":
            cap = obligation.get("max_retries")
            require(type(cap) is int and cap >= 0, "source retry cap required")
            good = type(op.get("max_retries")) is int and op["max_retries"] <= cap
        elif kind == "required_input":
            v1._string(obligation.get("input"), "source input")
            good = obligation["input"] in op["requires"]
        elif kind == "witness_owner":
            v1._string(obligation.get("entity"), "source entity")
            good = op.get("entity") == op.get("witness_entity") == obligation["entity"]
        elif kind == "reconciliation":
            good = isinstance(op.get("reconciliation"), str) and bool(op["reconciliation"].strip())
        elif kind == "consumer":
            v1._string(obligation.get("consumer"), "source consumer")
            consumer = operations.get(obligation["consumer"])
            good = consumer is not None and bool(set(op["produces"]) & set(consumer["requires"]))
        if not good:
            issues.append({"check": kind, "obligation": obligation["id"]})
    return {"passed": not issues, "issues": issues, "source_sha256": digest(source),
            "plan_sha256": digest(plan), "scope": "declared map only; no authority or code verification"}


def route(row, threshold):
    if row is None:
        return "failed"
    # Every acceptance check is explicit: absence is not evidence of validity.
    if row.get("input_valid") is not True or row.get("applicable") is not True:
        return "gated_out"
    if row["status"] == "error":
        return "failed"
    if row.get("conflict") is True:
        return "abstained"
    if row["status"] == "abstained":
        return "abstained"
    if row.get("output_valid") is not True or row.get("evidence_valid") is not True:
        return "failed"
    if number(row.get("score", 0), "score") < threshold:
        return "abstained"
    return "accepted"


def cascade(case_set, baseline, candidate, case_hash, threshold):
    threshold = number(threshold, "threshold")
    cases = cases_v2(case_set)
    left = arm_v2(baseline, cases, case_hash)
    right = arm_v2(candidate, cases, case_hash)
    require(baseline["arm_id"] != candidate["arm_id"], "arms must differ")
    require(candidate.get("fallback_authorized") is True, "fallback must already be authorized")
    records, flow = [], {}
    for key in cases:
        stage = route(right.get(key), threshold)
        accepted = stage == "accepted"
        selected = right.get(key) if accepted else left.get(key)
        flow[key] = stage
        selected = selected or {"case_id": key, "status": "error", "error": "missing fallback"}
        record = {k: v for k, v in selected.items() if k in ("case_id", "status", "output", "error", "reason")}
        # Routing, validation and rule-stage costs belong in the candidate row.
        # A deferred case adds fallback costs; unknown components stay unknown.
        for metric in v1.MEASUREMENTS:
            a = right.get(key, {}).get(metric)
            b = 0 if accepted else left.get(key, {}).get(metric)
            record[metric] = a + b if a is not None and b is not None else None
        record["critical_error"] = bool(selected.get("critical_error", False))
        records.append(record)
    arm = {"schema_version": 2, "arm_id": candidate["arm_id"] + "+fallback:" + baseline["arm_id"],
           "case_set_sha256": case_hash, "artifact_sha256": candidate["artifact_sha256"],
           "threshold": threshold, "components": [candidate["arm_id"], baseline["arm_id"]], "records": records}
    return arm, flow


def label_ok(case_set, case, arm_ids, allowed):
    source = case.get("label_source", case_set["oracle"]["kind"])
    independent = case.get("independent_of_candidate", case_set["oracle"]["independent_of_candidate"])
    return source in allowed and source != "teacher" and independent is True and case.get("label_arm_id") not in arm_ids


def score(case_set, baseline, candidate, case_hash, threshold, split=None, allowed=None):
    cases = cases_v2(case_set)
    hybrid, flow = cascade(case_set, baseline, candidate, case_hash, threshold)
    left = arm_v2(baseline, cases, case_hash)
    right = arm_v2(candidate, cases, case_hash)
    combined = {r["case_id"]: r for r in hybrid["records"]}
    selected = {k: c for k, c in cases.items() if split is None or c["split"] == split}
    counts = dict.fromkeys(("eligible", "gated_out", "attempted", "valid", "correct", "wrong",
                           "abstained", "failed", "fallback", "deferred", "teacher_agreed", "routed_correct"), 0)
    counts["eligible"] = len(selected)
    paired = dict.fromkeys(("both_correct", "candidate_only_correct", "baseline_only_correct", "both_incorrect"), 0)
    excluded, critical, outcomes = [], 0, []
    ids = {baseline["arm_id"], candidate["arm_id"], hybrid["arm_id"],
           *baseline.get("components", []), *candidate.get("components", [])}
    for key, case in selected.items():
        stage = flow[key]
        accepted = stage == "accepted"
        row = right.get(key)
        counts["attempted"] += int(row is not None and stage != "gated_out")
        counts["gated_out"] += int(stage == "gated_out")
        counts["valid"] += int(row is not None and row["status"] == "answered" and
                               row.get("output_valid") is True and row.get("evidence_valid") is True and
                               stage != "gated_out" and row.get("conflict") is not True)
        counts["abstained"] += int(stage == "abstained")
        counts["failed"] += int(stage == "failed")
        counts["fallback"] += int(not accepted)
        counts["deferred"] += int(not accepted)
        a, b = v1._correct(case, left.get(key)), v1._correct(case, combined[key])
        counts["correct"] += int(b)
        counts["wrong"] += int(not b)
        counts["routed_correct"] += int(accepted and v1._correct(case, row))
        same = row is not None and left.get(key) is not None and prediction(row) == prediction(left[key])
        counts["teacher_agreed"] += int(accepted and same)
        eligible_label = label_ok(case_set, case, ids, allowed or SOURCES)
        if eligible_label:
            paired["both_correct" if a and b else "baseline_only_correct" if a else
                   "candidate_only_correct" if b else "both_incorrect"] += 1
            critical += int(combined[key].get("critical_error", False) or (case.get("critical", False) and not b))
        else:
            excluded.append(key)
        outcomes.append({"case_id": key, "stage": stage, "baseline_correct": a,
                         "hybrid_correct": b, "label_eligible": eligible_label})
    n = len(selected)
    routed = n - counts["fallback"]
    summaries = {}
    for name, rows in (("baseline", left), ("candidate", right), ("hybrid", combined)):
        summaries[name] = v1.summarize_arm(selected, rows, name)[0]
    return {"schema_version": 2, "counts": counts, "arms": summaries, "paired": paired,
            "critical_errors": critical, "excluded_labels": excluded, "per_case": outcomes,
            "routed_coverage": v1._fraction(routed, n),
            "teacher_agreement": v1._fraction(counts["teacher_agreed"], routed),
            "correctly_routed_coverage": v1._fraction(counts["routed_correct"], n),
            "provenance_verified": False, "runtime_model_freedom_verified": False,
            "scope": "authored records; correctness counters include declared labels; verdict excludes ineligible labels"}


def prediction(row):
    if row is None:
        return "missing"
    return v1._json_value({k: row[k] for k in ("status", "output") if k in row}, "prediction")


def policy_v2(policy):
    version(policy)
    obj(policy, ("schema_version", "quality", "critical_error_cap", "coverage_target", "confidence",
                 "label_sources", "utility", "independent_units"))
    quality = policy["quality"]
    obj(quality, ("kind", "value"))
    require(quality["kind"] in ("floor", "noninferiority"), "quality kind must be floor or noninferiority")
    number(quality["value"], "quality value")
    for key in ("critical_error_cap", "coverage_target"):
        number(policy[key], key)
    require(0.5 < number(policy["confidence"], "confidence") < 1, "confidence must lie in (0.5, 1)")
    require(policy["independent_units"] == "case", "grouped inference requires recipient statistics")
    strings(policy["label_sources"], "label_sources")
    require(bool(policy["label_sources"]) and set(policy["label_sources"]) <= SOURCES - {"teacher"},
            "verdict labels cannot be teacher labels")
    obj(policy["utility"], ("correct", "wrong", "fallback"))
    for key, value in policy["utility"].items():
        number(value, "utility." + key, -1e6, 1e6)
    return policy


def utility(report, policy):
    c, u = report["counts"], policy["utility"]
    return sum(c[key] * number(u[key], "utility", -1e6, 1e6) for key in ("correct", "wrong", "fallback"))


def sweep(case_set, baseline, candidate, case_hash, thresholds, policy):
    policy_v2(policy)
    require(bool(thresholds), "at least one threshold required")
    results = []
    for threshold in thresholds:
        report = score(case_set, baseline, candidate, case_hash, threshold, "development", policy["label_sources"])
        require(report["counts"]["eligible"] > 0 and not report["excluded_labels"], "development needs eligible labels")
        results.append({"threshold": number(threshold, "threshold"), "utility": utility(report, policy),
                        "routed_coverage": report["routed_coverage"], "wrong": report["counts"]["wrong"]})
    chosen = max(results, key=lambda r: (r["utility"], r["threshold"]))
    return {"schema_version": 2, "split": "development", "results": results,
            "chosen_threshold": chosen["threshold"], "policy_sha256": digest(policy)}


def seal_study(case_set, baseline, candidate, case_hash, policy, threshold, source, plan):
    policy_v2(policy)
    cases = cases_v2(case_set)
    arm_v2(baseline, cases, case_hash)
    arm_v2(candidate, cases, case_hash)
    check_obligations(source, plan)
    require(any(c["split"] == "holdout" for c in cases.values()), "holdout required")
    body = {"schema_version": 2, "case_set_sha256": case_hash, "case_content_sha256": digest(case_set),
            "policy_sha256": digest(policy),
            "threshold": number(threshold, "threshold"), "baseline_id": baseline["arm_id"],
            "candidate_id": candidate["arm_id"], "baseline_artifact": baseline["artifact_sha256"],
            "candidate_artifact": candidate["artifact_sha256"], "source_sha256": digest(source),
            "plan_sha256": digest(plan)}
    return {**body, "seal_sha256": digest(body)}


def wilson(successes, n, confidence=0.95):
    require(type(n) is int and type(successes) is int and 0 <= successes <= n and n > 0, "invalid binomial counts")
    confidence = number(confidence, "confidence")
    require(0 < confidence < 1, "confidence must lie in (0,1)")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0., center - half), min(1., center + half)]


def mcnemar(wins, losses):
    require(type(wins) is int and type(losses) is int and wins >= 0 and losses >= 0, "invalid discordant counts")
    n = wins + losses
    if not n:
        return 1.
    # Log-probabilities avoid underflow from starting a recurrence at 2**-n.
    k = min(wins, losses)
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) - n * math.log(2)
            for i in range(k + 1)]
    peak = max(logs)
    return min(1., 2 * math.exp(peak) * math.fsum(math.exp(x - peak) for x in logs))


def newcombe(both, wins, losses, neither, confidence=0.95):
    """Paired Newcombe method 10, Wilson square-and-add, adjusted correlation."""
    require(all(type(x) is int and x >= 0 for x in (both, wins, losses, neither)), "invalid paired counts")
    n = both + wins + losses + neither
    require(n > 0, "empty paired table")
    p, q = (both + wins) / n, (both + losses) / n
    lp, up = wilson(both + wins, n, confidence)
    lq, uq = wilson(both + losses, n, confidence)
    # Newcombe corrects positive association only; negative phi must survive.
    denominator = math.sqrt((both + wins) * (losses + neither) * (both + losses) * (wins + neither))
    cross_product = both * neither - wins * losses
    adjusted = max(0., cross_product - n / 2) if cross_product > 0 else cross_product
    rho = adjusted / denominator if denominator else 0.
    lower = math.sqrt(max(0., (p - lp)**2 + (uq - q)**2 - 2 * rho * (p - lp) * (uq - q)))
    upper = math.sqrt(max(0., (up - p)**2 + (q - lq)**2 - 2 * rho * (up - p) * (q - lq)))
    return [max(-1., p - q - lower), min(1., p - q + upper)]


def decide(case_set, baseline, candidate, case_hash, policy, seal, source, plan):
    expected = seal_study(case_set, baseline, candidate, case_hash, policy, seal.get("threshold"), source, plan)
    require(digest(expected) == digest(seal), "study seal/policy/artifact/threshold mismatch")
    require("threshold" in candidate and number(candidate["threshold"], "candidate.threshold") ==
            number(seal["threshold"], "seal.threshold"), "candidate threshold differs from frozen study")
    report = score(case_set, baseline, candidate, case_hash, seal["threshold"], "holdout", policy["label_sources"])
    obligations = check_obligations(source, plan)
    cases = [c for c in cases_v2(case_set).values() if c["split"] == "holdout"]
    reasons, intervals = [], {}
    n = len(cases)
    if not obligations["passed"]:
        reasons.append("obligation check failed")
    if report["excluded_labels"]:
        reasons.append("holdout labels excluded: self-labelled, teacher, dependent or policy-disallowed")
    if len({c["group_id"] for c in cases}) != n:
        reasons.append("correlated groups require recipient-native inference")
    verdict = "Insufficient evidence"
    if not reasons:
        confidence = number(policy["confidence"], "confidence")
        c, p = report["counts"], report["paired"]
        intervals = {"accuracy_wilson": wilson(c["correct"], n, confidence),
                     "critical_error_wilson": wilson(report["critical_errors"], n, confidence),
                     "routed_coverage_wilson": wilson(n - c["fallback"], n, confidence),
                     "paired_difference_newcombe": newcombe(p["both_correct"], p["candidate_only_correct"],
                                                           p["baseline_only_correct"], p["both_incorrect"], confidence),
                     "mcnemar_exact_two_sided_p": mcnemar(p["candidate_only_correct"], p["baseline_only_correct"])}
        q = policy["quality"]
        quality = intervals["accuracy_wilson"] if q["kind"] == "floor" else intervals["paired_difference_newcombe"]
        target = number(q["value"], "quality") * (1 if q["kind"] == "floor" else -1)
        passed = quality[0] >= target and intervals["critical_error_wilson"][1] <= number(policy["critical_error_cap"], "cap") and intervals["routed_coverage_wilson"][0] >= number(policy["coverage_target"], "coverage")
        failed = quality[1] < target or intervals["critical_error_wilson"][0] > number(policy["critical_error_cap"], "cap") or intervals["routed_coverage_wilson"][1] < number(policy["coverage_target"], "coverage")
        if passed:
            verdict = "Bounded conversion supported" if c["fallback"] else "Conversion supported"
            reasons.append("all declared quality, critical-error and routed-coverage bounds pass")
        elif failed:
            verdict = "Conversion not supported"
            reasons.append("a declared requirement is outside its confidence interval")
        else:
            reasons.append("an interval crosses a declared requirement")
    return {"schema_version": 2, "verdict": verdict, "reasons": reasons, "intervals": intervals,
            "obligations": obligations, "report": report, "policy_sha256": digest(policy),
            "scope": "supplied holdout records only; per-component intervals, not simultaneous; no promotion authority",
            "provenance_verified": False, "runtime_model_freedom_verified": False}


def adjudication_packet(case_set, baseline, candidate, case_hash, seed, agreements):
    cases = cases_v2(case_set)
    left, right = arm_v2(baseline, cases, case_hash), arm_v2(candidate, cases, case_hash)
    require(baseline["arm_id"] != candidate["arm_id"], "arms must differ")
    require(type(seed) is int and type(agreements) is int and agreements >= 0, "integer seed and nonnegative agreement count required")
    rng = random.Random(seed)
    different = [k for k in cases if prediction(left.get(k)) != prediction(right.get(k))]
    different_ids = set(different)
    same = [k for k in cases if k not in different_ids]
    require(agreements <= len(same), "requested agreement sample exceeds population")
    chosen = different + rng.sample(same, agreements)
    rng.shuffle(chosen)
    rows, mapping = [], {}
    for i, key in enumerate(chosen):
        token = f"item-{i:06d}"
        swap = bool(rng.getrandbits(1))
        a, b = (right.get(key), left.get(key)) if swap else (left.get(key), right.get(key))
        def anonymous(row):
            return {k: row[k] for k in ("status", "output") if k in row} if row else {"status": "missing"}
        # Never copy provenance, expectations, arm ids, or source refs into packet.
        rows.append({"id": token, "input": cases[key].get("input"), "A": anonymous(a), "B": anonymous(b)})
        mapping[token] = {"case_id": key, "A": candidate["arm_id"] if swap else baseline["arm_id"],
                          "B": baseline["arm_id"] if swap else candidate["arm_id"],
                          "selection": "disagreement" if key in different_ids else "agreement-sample"}
    secret = {"schema_version": 2, "seed": seed, "case_set_sha256": case_hash,
              "baseline_sha256": digest(baseline), "candidate_sha256": digest(candidate), "mapping": mapping}
    packet = {"schema_version": 2, "key_commitment": digest(secret), "items": rows}
    key = {**secret, "packet_sha256": digest(packet)}
    return {"packet": packet, "sealed_key": key,
            "custody": "Give only packet to adjudicator; custodian withholds seed/key and identifying inputs. Hash seal is not encryption."}


def ingest_adjudication(case_set, packet, key, answers, case_hash):
    cases = cases_v2(case_set)
    version(packet)
    version(key)
    obj(packet, ("schema_version", "key_commitment", "items"))
    obj(key, ("schema_version", "seed", "case_set_sha256", "baseline_sha256", "candidate_sha256", "mapping", "packet_sha256"))
    secret = {k: v for k, v in key.items() if k != "packet_sha256"}
    require(packet.get("key_commitment") == digest(secret) and key.get("packet_sha256") == digest(packet), "adjudication seal mismatch")
    require(key.get("case_set_sha256") == case_hash, "adjudication case seal mismatch")
    version(answers)
    obj(answers, ("schema_version", "packet_sha256", "blind", "key_disclosed", "label_source", "independent_of_candidate", "records"))
    require(answers["packet_sha256"] == digest(packet), "answer packet mismatch")
    require(answers["blind"] is True and answers["key_disclosed"] is False, "adjudication was not blind")
    require(answers["label_source"] in ("human-adjudicated", "model-adjudicated"), "invalid adjudicator source")
    require(type(answers["independent_of_candidate"]) is bool, "independence declaration required")
    require(isinstance(answers["records"], list), "answers records must be list")
    mapping = key["mapping"]
    require(isinstance(mapping, dict) and isinstance(packet["items"], list), "invalid packet/key collections")
    require(set(mapping) == {r["id"] for r in packet["items"]}, "key mapping mismatch")
    rows = {}
    for row in answers["records"]:
        obj(row, ("id", "expectation"))
        require(row["id"] in mapping and row["id"] not in rows, "unknown/duplicate adjudication id")
        rows[row["id"]] = row
    require(rows.keys() == mapping.keys(), "incomplete adjudication")
    result = copy.deepcopy(case_set)
    output = {c["id"]: c for c in result["cases"]}
    agreement_errors = 0
    items_by_id = {item["id"]: item for item in packet["items"]}
    for token, row in rows.items():
        case_id = mapping[token]["case_id"]
        require(case_id in cases, "key refers to unknown case")
        case = output[case_id]
        case["expectation"] = row["expectation"]
        case["label_source"] = answers["label_source"]
        case["independent_of_candidate"] = answers["independent_of_candidate"]
        case.pop("label_arm_id", None)
        item = items_by_id[token]
        agreement_errors += int(mapping[token]["selection"] == "agreement-sample" and prediction(item["A"]) != prediction(row["expectation"]))
    cases_v2(result)
    sampled = sum(m["selection"] == "agreement-sample" for m in mapping.values())
    return {"case_set": result, "agreement_sample": {"n": sampled, "shared_errors": agreement_errors,
            "error_rate": v1._fraction(agreement_errors, sampled)},
            "provenance_verified": False, "limitations": "Blindness/independence are declarations; sampled agreements do not establish full-population absolute accuracy."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("obligations", "cascade", "score", "sweep", "seal", "decide", "packet", "ingest"))
    parser.add_argument("--request", type=Path, required=True, help="schema-v2 request JSON; see evaluation.md")
    args = parser.parse_args(argv)
    try:
        request, _ = v1.load_json(args.request)
        require(isinstance(request, dict), "request must be object")
        functions = {"obligations": check_obligations, "cascade": cascade, "score": score,
                     "sweep": sweep, "seal": seal_study, "decide": decide,
                     "packet": adjudication_packet, "ingest": ingest_adjudication}
        import inspect
        function = functions[args.command]
        signature = inspect.signature(function)
        require(not (request.keys() - signature.parameters.keys()), "unknown request fields")
        result = function(**request)
        if args.command == "cascade":
            result = {"arm": result[0], "flow": result[1]}
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        # Preserve exact decimal output tokens through the v1 serializer.
        print(v1._json_value(result, "report"))
        return 0
    except (InputError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        print(json.dumps({"error": "invalid_study_input", "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
