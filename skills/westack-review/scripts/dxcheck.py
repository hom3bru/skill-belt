#!/usr/bin/env python3
"""Check a developer-experience record (westack-dx-record-1). Standard library only; reads one file, writes nothing.

  python dxcheck.py record <dx.json>

The rubric is the core's references/dx.md; its dimension ids and time-to-hello-world tiers are repeated here so the
check runs without the core. Exit codes: 0 valid; 1 invalid; 64 usage or unreadable input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

FORMAT = "westack-dx-record-1"
DIMENSIONS = ("getting-started", "api-cli", "errors", "docs", "upgrade", "environment", "community", "measurement")
EVIDENCE = ("tested", "partial", "inferred")
TIERS = (("champion", 0, 2), ("competitive", 2, 5), ("needs-work", 5, 10), ("red-flag", 10, None))


def tier_for(minutes: float) -> str:
    if minutes < 2:
        return "champion"
    if minutes <= 5:
        return "competitive"
    if minutes <= 10:
        return "needs-work"
    return "red-flag"


def overall(dims: list) -> Optional[float]:
    scores = [d.get("score") for d in dims if isinstance(d.get("score"), int)]
    return round(sum(scores) / len(scores), 1) if scores else None


def check(record: dict) -> list:
    errors = []
    if record.get("format") != FORMAT:
        return [f"format must be {FORMAT}"]
    kind = record.get("kind")
    if kind not in ("plan", "live"):
        errors.append("kind must be plan or live")
    if not str(record.get("product", "")).strip():
        errors.append("product is required")
    persona = record.get("persona") or {}
    for key in ("who", "goal", "environment", "knows"):
        if not str(persona.get(key, "")).strip():
            errors.append(f"persona.{key} is required: every score is for one named developer")
    tthw = record.get("tthw") or {}
    minutes = tthw.get("minutes")
    if not isinstance(minutes, (int, float)) or minutes < 0:
        errors.append("tthw.minutes must be a number")
    elif tthw.get("tier") != tier_for(minutes):
        errors.append(f"tthw.tier is {tthw.get('tier')!r}; {minutes} minutes is {tier_for(minutes)!r}")
    if not tthw.get("steps"):
        errors.append("tthw.steps lists the steps counted")
    if tthw.get("evidence") not in EVIDENCE:
        errors.append(f"tthw.evidence must be one of {', '.join(EVIDENCE)}")
    dims = record.get("dimensions") or []
    ids = [d.get("id") for d in dims]
    for d in DIMENSIONS:
        if ids.count(d) != 1:
            errors.append(f"dimension {d} must appear exactly once (found {ids.count(d)})")
    for d in dims:
        where = f"dimension {d.get('id')}"
        if d.get("id") not in DIMENSIONS:
            errors.append(f"{where}: not a rubric dimension")
        score = d.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 10:
            errors.append(f"{where}: score must be a whole number from 0 to 10")
        if d.get("evidence") not in EVIDENCE:
            errors.append(f"{where}: evidence must be one of {', '.join(EVIDENCE)}")
        if not str(d.get("gap", "")).strip():
            errors.append(f"{where}: say what a 10 looks like and the gap")
    if kind == "plan":
        if any(d.get("evidence") in ("tested", "partial") for d in dims) or tthw.get("evidence") in ("tested", "partial"):
            errors.append("a plan review ran nothing: every mark is inferred")
    want = overall(dims)
    if record.get("overall") != want:
        errors.append(f"overall is {record.get('overall')!r}; the mean of the scores is {want!r}")
    return errors


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "record":
        print("usage: dxcheck.py record <dx.json>", file=sys.stderr)
        return 64
    try:
        record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"dxcheck.py: cannot read {argv[1]}: {exc}", file=sys.stderr)
        return 64
    errors = check(record)
    print(json.dumps({"status": "valid" if not errors else "invalid", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
