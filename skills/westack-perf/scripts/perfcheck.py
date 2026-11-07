#!/usr/bin/env python3
"""westack-perf measurement helper. Standard library only; reads files, runs nothing, writes nothing.

  python perfcheck.py summarize <run.json>                 median, range and count per metric
  python perfcheck.py compare   <baseline.json> <run.json> per-metric status and a verdict
  python perfcheck.py budget    <run.json>                 page budgets: pass, warning, fail and a grade
  python perfcheck.py validate  <run.json>                 the run file's shape
  python perfcheck.py history   <runs.jsonl>               medians per saved run, oldest first

A metric's unit comes from its name: *_ms timing, *_bytes size, total_requests a count, anything else unitless.
Exit codes: 0 ok (compare: faster or no measurable difference; budget: no fail); 1 invalid, slower, a warning, a
budget failure or inconclusive; 64 usage or unreadable input. Numbers live in references/thresholds.json.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Optional

RUN_FORMAT = "westack-perf-run-1"
KINDS = ("page", "command", "request")
THRESHOLDS = Path(__file__).resolve().parent.parent / "references" / "thresholds.json"
EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 64


class UsageError(Exception):
    pass


def load_json(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read {path}: {exc}")


def thresholds() -> dict:
    return load_json(THRESHOLDS)


def unit(metric: str) -> str:
    if metric.endswith("_ms"):
        return "timing"
    if metric.endswith("_bytes"):
        return "size"
    if metric == "total_requests":
        return "count"
    return "unitless"


def summarize(run: dict) -> dict:
    values = {}
    for r in run.get("runs", []):
        for metric, v in r.get("metrics", {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                values.setdefault(metric, []).append(v)
    return {m: {"median": statistics.median(vs), "min": min(vs), "max": max(vs), "n": len(vs)} for m, vs in values.items()}


def errors_in(run: dict) -> int:
    return sum(int(r.get("errors", 0) or 0) for r in run.get("runs", []))


def metric_status(metric: str, base: dict, cur: dict, t: dict) -> dict:
    b, c = base["median"], cur["median"]
    delta = c - b
    spread = max(base["max"] - base["min"], cur["max"] - cur["min"])
    pct = (delta / b * 100) if b else None
    out = {"metric": metric, "baseline": b, "current": c, "delta": delta, "pct": None if pct is None else round(pct, 1),
           "spread": spread}
    if abs(delta) <= spread:
        out["status"] = "no measurable difference"
        return out
    if delta < 0:
        out["status"] = "improved"
        return out
    kind = unit(metric)
    if kind == "timing":
        r = t["timing"]
        if delta > r["regression_abs_ms"] or (pct is not None and pct > r["regression_pct"]):
            out["status"] = "regression"
        elif pct is not None and pct > r["warning_pct"]:
            out["status"] = "warning"
        else:
            out["status"] = "ok"
    elif kind == "size":
        r = t["size"]
        out["status"] = "regression" if pct is not None and pct > r["regression_pct"] else (
            "warning" if pct is not None and pct > r["warning_pct"] else "ok")
    elif kind == "count":
        out["status"] = "warning" if pct is not None and pct > t["count"]["warning_pct"] else "ok"
    else:
        r = t["unitless"]
        out["status"] = "regression" if delta > r["regression_abs"] else ("warning" if delta > r["warning_abs"] else "ok")
    return out


def compare(baseline: dict, current: dict, t: Optional[dict] = None) -> dict:
    t = t or thresholds()
    sb, sc = summarize(baseline), summarize(current)
    rows = [metric_status(m, sb[m], sc[m], t) for m in sorted(set(sb) & set(sc))]
    statuses = {r["status"] for r in rows}
    if "regression" in statuses:
        verdict = "slower"
    elif "warning" in statuses:
        verdict = "slower (warning)"
    elif "improved" in statuses:
        verdict = "faster"
    else:
        verdict = "no measurable difference"
    reasons = []
    for name, side in (("baseline", baseline), ("current", current)):
        n = min((s["n"] for s in summarize(side).values()), default=0)
        if n < t["min_runs"]:
            reasons.append(f"{name} has {n} runs; at least {t['min_runs']} per side are needed")
        if errors_in(side):
            reasons.append(f"{name} had {errors_in(side)} errors: a fast failure is not a fast run")
    if verdict != "no measurable difference" and not str(current.get("limiter", "")).strip():
        reasons.append("a difference is claimed but no limiter is named")
    if not rows:
        reasons.append("no metric is measured on both sides")
    if reasons:
        verdict = "inconclusive"
    return {"verdict": verdict, "reasons": reasons, "metrics": rows,
            "only_baseline": sorted(set(sb) - set(sc)), "only_current": sorted(set(sc) - set(sb))}


def budget(run: dict, t: Optional[dict] = None) -> dict:
    t = t or thresholds()
    s = summarize(run)
    rows = []
    for metric, limit in t["budgets"].items():
        if metric not in s:
            rows.append({"metric": metric, "budget": limit, "status": "n/a"})
            continue
        v = s[metric]["median"]
        status = "fail" if v >= limit else ("warning" if v >= t["budget_warning_ratio"] * limit else "pass")
        rows.append({"metric": metric, "budget": limit, "actual": v, "status": status})
    measured = [r for r in rows if r["status"] != "n/a"]
    below = sum(1 for r in measured if r["status"] in ("pass", "warning"))
    if not measured:
        grade = "n/a"
    elif below == len(measured):
        grade = "A"
    elif below * 3 >= len(measured) * 2:
        grade = "B"
    elif below * 2 >= len(measured):
        grade = "C"
    else:
        grade = "D"
    return {"grade": grade, "below_budget": below, "measured": len(measured), "metrics": rows}


def validate(run: dict) -> list:
    errors = []
    if run.get("format") != RUN_FORMAT:
        return [f"format must be {RUN_FORMAT}"]
    if run.get("kind") not in KINDS:
        errors.append(f"kind must be one of {', '.join(KINDS)}")
    for key in ("target", "claim"):
        if not str(run.get(key, "")).strip():
            errors.append(f"{key} is required (claim: the sentence you expect to ship, written before measuring)")
    if run.get("kind") == "page":
        if not str(run.get("driver", "")).strip():
            errors.append("a page run names its browser driver")
        for key in ("os", "browser", "viewport", "cache"):
            if key not in run.get("environment", {}):
                errors.append(f"environment.{key} is required for a page run")
    elif not str(run.get("environment", {}).get("machine", "")).strip():
        errors.append("environment.machine is required (CPU, load, build mode)")
    runs = run.get("runs", [])
    if not runs:
        errors.append("runs is empty: nothing was measured")
    for n, r in enumerate(runs, 1):
        if not r.get("metrics"):
            errors.append(f"runs[{n}] has no metrics")
        if "errors" not in r:
            errors.append(f"runs[{n}] counts its errors (0 when none)")
    return errors


def history(path) -> list:
    rows = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc}")
    for line in lines:
        if line.strip():
            run = json.loads(line)
            rows.append({"at": run.get("at"), "target": run.get("target"),
                         "medians": {m: v["median"] for m, v in summarize(run).items()}})
    return sorted(rows, key=lambda r: str(r["at"]))


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = __doc__.split("\n\n")[1]
    try:
        if not argv:
            raise UsageError("no command")
        cmd, args = argv[0], argv[1:]
        if cmd == "summarize" and len(args) == 1:
            print(json.dumps(summarize(load_json(args[0])), indent=2))
            return EXIT_OK
        if cmd == "compare" and len(args) == 2:
            result = compare(load_json(args[0]), load_json(args[1]))
            print(json.dumps(result, indent=2))
            return EXIT_OK if result["verdict"] in ("faster", "no measurable difference") else EXIT_FAIL
        if cmd == "budget" and len(args) == 1:
            result = budget(load_json(args[0]))
            print(json.dumps(result, indent=2))
            return EXIT_FAIL if any(r["status"] == "fail" for r in result["metrics"]) else EXIT_OK
        if cmd == "validate" and len(args) == 1:
            errors = validate(load_json(args[0]))
            print(json.dumps({"status": "valid" if not errors else "invalid", "errors": errors}, indent=2))
            return EXIT_OK if not errors else EXIT_FAIL
        if cmd == "history" and len(args) == 1:
            print(json.dumps(history(args[0]), indent=2))
            return EXIT_OK
        raise UsageError(f"unknown command or wrong arguments: {' '.join(argv)}")
    except UsageError as exc:
        print(f"perfcheck.py: {exc}\n{usage}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
