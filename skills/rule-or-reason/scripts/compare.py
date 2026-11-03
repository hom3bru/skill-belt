#!/usr/bin/env python3
"""Describe paired JSON predictions. No candidate, model, network, or shell execution."""
from __future__ import annotations

import argparse
from decimal import Decimal, DecimalException
import hashlib
import json
import math
from pathlib import Path
import sys

MAX_BYTES = 16 * 1024 * 1024
MAX_CASES = 100_000
MEASUREMENTS = ("runtime_llm_calls", "latency_ms", "cost_usd")


class InputError(ValueError):
    """The supplied record does not satisfy the declared comparison contract."""


class _JSONDecimal:
    """Keep a decoded decimal token exact until its role is known."""

    def __init__(self, token):
        self.token = token


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _constant(value):
    raise InputError(f"non-finite JSON number: {value}")


def load_json(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InputError(f"input exceeds {MAX_BYTES} bytes: {path}")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant, parse_float=_JSONDecimal)
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(f"cannot read valid bounded UTF-8 JSON from {path}: {exc}") from exc


def _object(value, required, optional=(), where="object"):
    if not isinstance(value, dict):
        raise InputError(f"{where} must be an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise InputError(f"{where}: missing={sorted(missing)}, unknown={sorted(extra)}")


def _string(value, where):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{where} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise InputError(f"{where} must contain valid Unicode text") from exc


def _version(value, where):
    if type(value) is not int or value != 1:
        raise InputError(f"{where} supports schema_version 1 only")


def _digest(value, where):
    if not isinstance(value, str) or len(value) != 64:
        raise InputError(f"{where} must be a lowercase SHA-256 hex digest")
    if any(char not in "0123456789abcdef" for char in value):
        raise InputError(f"{where} must be a lowercase SHA-256 hex digest")


def _json_value(value, where):
    """Match JSON structures without rounding parsed decimal output tokens."""
    def canonical(item):
        if isinstance(item, _JSONDecimal):
            return item.token
        if item is None or type(item) in (bool, int, float, str):
            return json.dumps(item, ensure_ascii=False, allow_nan=False)
        if isinstance(item, list):
            return "[" + ",".join(canonical(part) for part in item) + "]"
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise TypeError("JSON object keys must be strings")
            return "{" + ",".join(json.dumps(key, ensure_ascii=False) + ":" + canonical(item[key])
                                  for key in sorted(item)) + "}"
        raise TypeError("unsupported JSON value type")

    try:
        result = canonical(value)
        result.encode("utf-8")
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise InputError(f"{where} is not a finite JSON value: {exc}") from exc


def validate_cases(value):
    _object(value, ("schema_version", "task_id", "oracle", "cases"), ("description",),
            "case set")
    _version(value["schema_version"], "case set")
    _string(value["task_id"], "task_id")
    if "description" in value:
        _string(value["description"], "description")
    oracle = value["oracle"]
    _object(oracle, ("kind", "source", "independent_of_candidate"), where="oracle")
    if oracle["kind"] not in ("reference", "human-adjudicated", "synthetic", "teacher"):
        raise InputError("oracle.kind is reference, human-adjudicated, synthetic, or teacher")
    _string(oracle["source"], "oracle.source")
    if type(oracle["independent_of_candidate"]) is not bool:
        raise InputError("oracle.independent_of_candidate must be a boolean declaration")
    cases = value["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise InputError(f"cases must contain 1..{MAX_CASES} entries")
    result = {}
    for row in cases:
        _object(row, ("id", "group_id", "stratum", "expectation"),
                ("input_ref", "input_sha256", "language"), "case")
        for field in ("id", "group_id", "stratum"):
            _string(row[field], f"case.{field}")
        if row["id"] in result:
            raise InputError(f"duplicate case id: {row['id']}")
        for field in ("input_ref", "language"):
            if field in row:
                _string(row[field], f"case.{field}")
        if "input_sha256" in row:
            _digest(row["input_sha256"], "case.input_sha256")
        expectation = row["expectation"]
        _object(expectation, ("status",), ("output",), "expectation")
        if expectation["status"] == "answered":
            if "output" not in expectation:
                raise InputError("answered expectation requires output, including explicit null")
            _json_value(expectation["output"], "expected output")
        elif expectation["status"] == "abstained":
            if "output" in expectation:
                raise InputError("abstained expectation must not contain output")
        else:
            raise InputError("expectation.status is answered or abstained")
        result[row["id"]] = row
    return result


def validate_arm(value, case_ids, expected_digest):
    _object(value, ("schema_version", "arm_id", "case_set_sha256", "records"),
            ("artifact_ref", "artifact_sha256", "provenance"), "arm")
    _version(value["schema_version"], "arm")
    _string(value["arm_id"], "arm_id")
    _digest(value["case_set_sha256"], "case_set_sha256")
    if value["case_set_sha256"] != expected_digest:
        raise InputError("arm case_set_sha256 does not match the exact supplied case-set bytes")
    for key in ("artifact_ref", "provenance"):
        if key in value:
            _string(value[key], key)
    if "artifact_sha256" in value:
        _digest(value["artifact_sha256"], "artifact_sha256")
    rows = value["records"]
    if not isinstance(rows, list) or len(rows) > MAX_CASES:
        raise InputError("records must be a bounded list")
    result = {}
    for supplied_row in rows:
        _object(supplied_row, ("case_id", "status"),
                ("output", "error", "reason", *MEASUREMENTS), "prediction")
        row = dict(supplied_row)
        _string(row["case_id"], "case_id")
        key = row["case_id"]
        if key not in case_ids:
            raise InputError(f"prediction refers to unknown case: {key}")
        if key in result:
            raise InputError(f"duplicate prediction for case: {key}")
        if row["status"] not in ("answered", "abstained", "error"):
            raise InputError("prediction status is answered, abstained, or error")
        if row["status"] == "answered":
            if "output" not in row:
                raise InputError("answered prediction requires output")
            _json_value(row["output"], "prediction output")
        elif "output" in row:
            raise InputError("nonanswered prediction must not contain output")
        for key_name in ("error", "reason"):
            if key_name in row:
                _string(row[key_name], key_name)
        for measurement in MEASUREMENTS:
            datum = row.get(measurement)
            if datum is None:
                continue
            if isinstance(datum, _JSONDecimal):
                try:
                    exact = Decimal(datum.token)
                    if exact < 0:
                        raise InputError(f"{measurement} must be nonnegative")
                    datum = float(exact)
                except DecimalException as exc:
                    raise InputError(f"{measurement} exceeds the supported numeric range") from exc
                row[measurement] = datum
            try:
                valid = type(datum) in (int, float) and math.isfinite(datum) and datum >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise InputError(f"{measurement} must be a finite nonnegative number or null")
            if measurement == "runtime_llm_calls" and type(datum) is not int:
                raise InputError("runtime_llm_calls must be an integer or null")
        result[key] = row
    return result


def _correct(case, record):
    if record is None or record["status"] == "error":
        return False
    expected = case["expectation"]
    if expected["status"] != record["status"]:
        return False
    if expected["status"] == "abstained":
        return True
    return _json_value(expected["output"], "expected") == _json_value(record["output"], "actual")


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize_arm(cases, rows, arm_id):
    outcomes = {}
    strata = {}
    groups = {}
    counts = {"eligible": len(cases), "answered": 0, "abstained": 0,
              "errors": 0, "missing": 0, "correct": 0, "incorrect_answered": 0}
    measured = {key: [] for key in MEASUREMENTS}
    for case_id, case in cases.items():
        record = rows.get(case_id)
        status = record["status"] if record is not None else "missing"
        correct = _correct(case, record)
        outcomes[case_id] = {"status": status, "correct": correct,
                             "group_id": case["group_id"], "stratum": case["stratum"]}
        count_key = {"answered": "answered", "abstained": "abstained",
                     "error": "errors", "missing": "missing"}[status]
        counts[count_key] += 1
        counts["correct"] += int(correct)
        counts["incorrect_answered"] += int(status == "answered" and not correct)
        bucket = strata.setdefault(case["stratum"],
                                    {"eligible": 0, "answered": 0, "correct": 0,
                                     "errors": 0, "abstained": 0, "missing": 0})
        bucket["eligible"] += 1
        bucket[count_key] += 1
        bucket["correct"] += int(correct)
        groups.setdefault(case["group_id"], []).append(correct)
        for key in MEASUREMENTS:
            if record is not None and record.get(key) is not None:
                measured[key].append(record[key])
    measurements = {}
    for key, values in measured.items():
        try:
            total = sum(values) if key == "runtime_llm_calls" else math.fsum(values)
            if not math.isfinite(total):
                raise OverflowError()
        except OverflowError as exc:
            raise InputError(f"{key} aggregate exceeds finite numeric range") from exc
        measurements[key] = {"reported_cases": len(values), "unknown_cases": len(cases) - len(values),
                             "reported_sum": total,
                             "total": total if len(values) == len(cases) else None,
                             "provenance": "caller-supplied; not verified"}
    for bucket in strata.values():
        bucket["accuracy"] = _fraction(bucket["correct"], bucket["eligible"])
        bucket["coverage"] = _fraction(bucket["answered"], bucket["eligible"])
    summary = {
        "arm_id": arm_id, **counts,
        "accuracy": _fraction(counts["correct"], len(cases)),
        "coverage": _fraction(counts["answered"], len(cases)),
        "answer_precision": _fraction(counts["answered"] - counts["incorrect_answered"],
                                      counts["answered"]),
        "groups": len(groups), "group_all_correct": sum(all(items) for items in groups.values()),
        "strata": strata, "measurements": measurements,
    }
    return summary, outcomes


def compare_records(case_set, baseline, candidate, case_set_sha256):
    _digest(case_set_sha256, "comparison case_set_sha256")
    cases = validate_cases(case_set)
    left = validate_arm(baseline, cases, case_set_sha256)
    right = validate_arm(candidate, cases, case_set_sha256)
    if baseline["arm_id"] == candidate["arm_id"]:
        raise InputError("baseline and candidate must have distinct arm_id values")
    before, before_rows = summarize_arm(cases, left, baseline["arm_id"])
    after, after_rows = summarize_arm(cases, right, candidate["arm_id"])
    paired = {"both_correct": 0, "both_incorrect": 0,
              "candidate_only_correct": 0, "baseline_only_correct": 0}
    changes = []
    for case_id in cases:
        a, b = before_rows[case_id]["correct"], after_rows[case_id]["correct"]
        key = ("both_correct" if a and b else "baseline_only_correct" if a else
               "candidate_only_correct" if b else "both_incorrect")
        paired[key] += 1
        changes.append({"case_id": case_id, "baseline": before_rows[case_id],
                        "candidate": after_rows[case_id]})
    return {
        "schema_version": 1, "evidence_scope": "descriptive-authored-records",
        "task_id": case_set["task_id"], "case_set_sha256": case_set_sha256,
        "oracle": case_set["oracle"], "oracle_provenance_verified": False,
        "runtime_model_freedom_verified": False,
        "baseline": before, "candidate": after, "paired": paired,
        "accuracy_difference": after["accuracy"] - before["accuracy"],
        "per_case": changes,
        "limitations": [
            "No candidate was executed and no supplied label, measurement, or provenance was authenticated.",
            "Exact JSON matching only: integer values and decimal tokens are retained; bool differs from number.",
            "No confidence interval, significance test, equivalence proof, or promotion decision is calculated.",
            "Cases and groups are caller-declared; group summaries do not establish statistical independence.",
            "Missing records remain eligible and incorrect; measurement totals are null when any case is unknown.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    hash_parser = commands.add_parser("hash", help="validate and hash exact case-set bytes")
    hash_parser.add_argument("cases", type=Path)
    compare_parser = commands.add_parser("compare", help="describe supplied paired predictions")
    for field in ("cases", "baseline", "candidate"):
        compare_parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        cases, digest = load_json(args.cases)
        if args.command == "hash":
            result = {"schema_version": 1, "case_set_sha256": digest,
                      "case_count": len(validate_cases(cases))}
        else:
            baseline, _ = load_json(args.baseline)
            candidate, _ = load_json(args.candidate)
            result = compare_records(cases, baseline, candidate, digest)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (InputError, RecursionError, OverflowError) as exc:
        print(json.dumps({"error": "invalid_comparison_input", "message": str(exc)}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
