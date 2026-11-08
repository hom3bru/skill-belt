"""Seeded synthetic records only. No real candidate, model, or qualification pilot."""
import copy
import json
from pathlib import Path
import random
import sys

import study


def fixture(seed=20261107, count=600):
    rng = random.Random(seed)
    cases, baseline, candidate = [], [], []
    for i in range(count):
        key = f"case-{i:04d}"
        output = bool(rng.getrandbits(1))
        applicable = i % 4 != 0
        cases.append({"id": key, "group_id": key, "stratum": "negated" if i % 5 == 0 else "ordinary",
                      "split": "development" if i < count // 3 else "holdout",
                      "input": {"policy_flag": output, "negated": i % 5 == 0},
                      "expectation": {"status": "answered", "output": output},
                      "label_source": "synthetic", "independent_of_candidate": True, "critical": True})
        baseline.append({"case_id": key, "status": "answered", "output": not output if i % 20 == 1 else output,
                         "runtime_llm_calls": 1, "latency_ms": 10, "cost_usd": 0.01})
        candidate.append({"case_id": key, "status": "answered" if applicable else "abstained",
                          **({"output": output} if applicable else {}), "input_valid": True,
                          "applicable": applicable, "output_valid": True, "evidence_valid": True,
                          "score": 0.9, "runtime_llm_calls": 0, "latency_ms": 1, "cost_usd": 0})
    case_set = {"schema_version": 2, "task_id": "synthetic-policy-flag",
                "oracle": {"kind": "synthetic", "source": "authored seeded fixture; not independent research",
                           "independent_of_candidate": True}, "cases": cases}
    case_hash = study.digest(case_set)  # API fixture; CLI artifacts use exact-byte file hash
    def arm(name, rows):
        return {"schema_version": 2, "arm_id": name, "case_set_sha256": case_hash,
                "artifact_sha256": study.digest({"fixture": name}), "records": rows}
    base, rule = arm("teacher", baseline), arm("selective-rule", candidate)
    rule["fallback_authorized"] = True
    policy = {"schema_version": 2, "quality": {"kind": "floor", "value": 0.95},
              "critical_error_cap": 0.02, "coverage_target": 0.65, "confidence": 0.95,
              "label_sources": ["synthetic"], "independent_units": "case",
              "utility": {"correct": 1, "wrong": -5, "fallback": -0.2}}
    source = {"schema_version": 2, "obligations": [
        {"id": "approval", "kind": "human_gate", "operation": "approve"},
        {"id": "cap", "kind": "retry_cap", "operation": "rule", "max_retries": 2},
        {"id": "input", "kind": "required_input", "operation": "rule", "input": "approval"},
        {"id": "witness", "kind": "witness_owner", "operation": "rule", "entity": "selected-entity"},
        {"id": "consume", "kind": "consumer", "operation": "rule", "consumer": "consume"},
        {"id": "recover", "kind": "reconciliation", "operation": "rule"}]}
    plan = {"schema_version": 2, "source_sha256": study.digest(source), "initial_inputs": ["source"], "operations": [
        {"id": "approve", "kind": "human_gate", "requires": ["source"], "produces": ["approval"], "depends_on": []},
        {"id": "rule", "kind": "rule", "requires": ["source", "approval"], "produces": ["value+witness"],
         "depends_on": ["approve"], "max_retries": 2, "entity": "selected-entity", "witness_entity": "selected-entity",
         "reconciliation": "inspect partial output before retry; no automatic replay"},
        {"id": "consume", "kind": "tool", "requires": ["value+witness"], "produces": [], "depends_on": ["rule"]}]}
    return case_set, base, rule, case_hash, policy, source, plan


def run():
    cases, base, rule, case_hash, policy, source, plan = fixture()
    tuning = study.sweep(cases, base, rule, case_hash, [0.5, 0.8, 1.0], policy)
    rule["threshold"] = tuning["chosen_threshold"]
    seal = study.seal_study(cases, base, rule, case_hash, policy, rule["threshold"], source, plan)
    decision = study.decide(cases, base, rule, case_hash, policy, seal, source, plan)
    abstain = copy.deepcopy(rule)
    for row in abstain["records"]:
        row.pop("output", None)
        row["status"] = "abstained"
    bad = copy.deepcopy(rule)
    for row, case in zip(bad["records"], cases["cases"]):
        row["applicable"] = True
        row["status"] = "answered"
        row["output"] = not case["expectation"]["output"] if case["input"]["negated"] else case["expectation"]["output"]
    bad_seal = study.seal_study(cases, base, bad, case_hash, policy, bad["threshold"], source, plan)
    bad_decision = study.decide(cases, base, bad, case_hash, policy, bad_seal, source, plan)
    routed = study.score(cases, base, rule, case_hash, rule["threshold"], "holdout")
    always = study.score(cases, base, abstain, case_hash, rule["threshold"], "holdout")
    return {"seed": 20261107, "evidence": "synthetic and unit-tested only; criterion 9 not run",
            "tuning": tuning, "seal": seal, "decision": decision,
            "selective_utility": study.utility(routed, policy), "always_abstain_utility": study.utility(always, policy),
            "negation_sensitive_verdict": bad_decision["verdict"], "negation_sensitive_intervals": bad_decision["intervals"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
