#!/usr/bin/env python3
"""westack-health helper. Standard library only; reads files (and PATH, for detect), runs no tool, writes nothing.

  python healthcheck.py detect    <repo>                         the declared `## Health Stack`, else tools found from files
  python healthcheck.py score     <results.json>                 category scores, the weighted score, coverage, a history line
  python healthcheck.py history   <history.jsonl> <results.json> the trend against the last run with the same coverage
  python healthcheck.py recommend <results.json>                 categories below 10, ranked by weight times deficit

results.json (westack-health-results-1) records what the agent ran: per category `ran` (command, exit, counts, log and
its sha256), `skipped` (reason: the tool is missing or nothing to check) or `error` (the capture failed; reason).
Exit codes: 0 ok; 1 invalid input, or history shows a decline; 2 not scored (nothing ran, or a capture failed); 64 usage
or unreadable input. The numbers live in references/thresholds.json.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

RESULTS_FORMAT = "westack-health-results-1"
STATUSES = ("ran", "skipped", "error")
THRESHOLDS = Path(__file__).resolve().parent.parent / "references" / "thresholds.json"
EXIT_OK, EXIT_FAIL, EXIT_UNSCORED, EXIT_USAGE = 0, 1, 2, 64
ALIASES = {"test": "tests", "type": "typecheck", "types": "typecheck", "dead": "deadcode", "dead-code": "deadcode",
           "shellcheck": "shell"}


class UsageError(Exception):
    pass


def load_json(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read {path}: {exc}")


def thresholds() -> dict:
    return load_json(THRESHOLDS)


def one_decimal(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def label(score: int, t: dict) -> str:
    for floor, name in t["labels"]:
        if score >= floor:
            return name
    return t["labels"][-1][1]


def category_score(cat: str, entry: dict, t: dict) -> tuple:
    """(score, detail) for a category that ran."""
    code, counts = entry.get("exit"), entry.get("counts") or {}
    if cat == "index":
        verdict = counts.get("verdict")
        return t["index"][verdict], f"westack-onboard doctor {verdict}"
    if cat == "tests":
        executed, passed, failed = counts.get("executed"), counts.get("passed"), counts.get("failed")
        if executed == 0:
            return 0, "no tests executed: not a pass"
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (executed, passed, failed)):
            if code == 0:
                return t["tests"]["passed_without_count"], "exit 0 but counts unknown: never CLEAN without counts"
            return t["failed_without_count"], f"exit {code}, counts unknown"
        if failed == 0 and code == 0:
            return 10, f"{passed}/{executed} passed"
        if failed == 0:
            return t["failed_without_count"], f"exit {code} with no failed test counted"
        rate = passed / executed
        for above, score in t["tests"]["pass_rate_above"]:
            if rate > above:
                return score, f"{passed}/{executed} passed ({rate:.1%})"
        return t["tests"]["else"], f"{passed}/{executed} passed ({rate:.1%})"
    band = t["count_bands"][cat]
    n = counts.get(band["count"])
    if not isinstance(n, int) or n == 0:
        if code == 0:
            return 10, f"0 {band['count']}"
        return t["failed_without_count"], f"exit {code}, no {band['count']} counted"
    for below, score in band["below"]:
        if n < below:
            return score, f"{n} {band['count']}"
    return band["else"], f"{n} {band['count']}"


def validate(results: dict, t: Optional[dict] = None) -> list:
    t = t or thresholds()
    if results.get("format") != RESULTS_FORMAT:
        return [f"format must be {RESULTS_FORMAT}"]
    errors = []
    if not str(results.get("repo", "")).strip():
        errors.append("repo is required")
    cats = results.get("categories")
    if not isinstance(cats, dict) or not cats:
        return errors + ["categories is required: every weighted category, ran, skipped or error"]
    for cat in cats:
        if cat not in t["weights"]:
            errors.append(f"{cat}: not a weighted category ({', '.join(t['weights'])})")
    for cat in t["weights"]:
        entry = cats.get(cat)
        if not isinstance(entry, dict):
            errors.append(f"{cat}: missing; record it as ran, skipped (with the reason) or error")
            continue
        status = entry.get("status")
        if status not in STATUSES:
            errors.append(f"{cat}: status must be one of {', '.join(STATUSES)}")
        elif status == "ran":
            if not str(entry.get("command", "")).strip():
                errors.append(f"{cat}: a run names its command")
            if not isinstance(entry.get("exit"), int) or isinstance(entry.get("exit"), bool):
                errors.append(f"{cat}: a run records the checker's own exit code")
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("log_sha256", ""))):
                errors.append(f"{cat}: a run keeps its full log and its sha256")
            c = entry.get("counts") or {}
            if cat == "index" and c.get("verdict") not in t["index"]:
                errors.append(f"index: counts.verdict must be one of {', '.join(t['index'])} (westack-onboard doctor)")
            if cat == "tests" and all(isinstance(c.get(k), int) for k in ("executed", "passed", "failed")) \
                    and c["passed"] + c["failed"] != c["executed"]:
                errors.append("tests: passed plus failed must equal executed (count errors as failed; skipped "
                              "tests are not executed)")
        elif not str(entry.get("reason", "")).strip():
            errors.append(f"{cat}: {status} needs a reason")
    return errors


def score(results: dict, t: Optional[dict] = None) -> dict:
    t = t or thresholds()
    errors = validate(results, t)
    if errors:
        return {"status": "invalid", "errors": errors}
    cats = results["categories"]
    out, scored, skipped, failed_capture = {}, [], {}, {}
    for cat, weight in t["weights"].items():
        entry = cats[cat]
        if entry["status"] == "ran":
            value, detail = category_score(cat, entry, t)
            out[cat] = {"score": value, "label": label(value, t), "weight": weight, "detail": detail,
                        "command": entry["command"], "exit": entry["exit"]}
            scored.append(cat)
        elif entry["status"] == "skipped":
            out[cat] = {"score": None, "label": "SKIPPED", "weight": weight, "detail": entry["reason"]}
            skipped[cat] = entry["reason"]
        else:
            out[cat] = {"score": None, "label": "ERROR", "weight": weight, "detail": entry["reason"]}
            failed_capture[cat] = entry["reason"]
    coverage = {"scored": scored, "skipped": skipped, "errors": failed_capture,
                "checked": f"{len(scored)}/{len(t['weights'])}"}
    if failed_capture:
        status, composite = "not scored: capture failed", None
    elif not scored:
        status, composite = "not scored: no checks ran", None
    else:
        total = sum(t["weights"][c] for c in scored)
        composite = one_decimal(sum(out[c]["score"] * t["weights"][c] for c in scored) / total)
        for c in scored:
            out[c]["effective_weight"] = one_decimal(100 * t["weights"][c] / total)
        status = "partial coverage" if skipped else "scored"
    result = {"status": status, "composite": composite, "coverage": coverage, "categories": out}
    if composite is not None:
        line = {"date": results.get("date"), "branch": results.get("branch"), "revision": results.get("revision"),
                "score": composite}
        line.update({c: out[c]["score"] for c in t["weights"]})
        result["history_line"] = line
    return result


def recommend(results: dict, t: Optional[dict] = None) -> dict:
    t = t or thresholds()
    s = score(results, t)
    if s["status"] == "invalid":
        return s
    order = list(t["weights"])
    below = [(c, v) for c, v in s["categories"].items() if v["score"] is not None and v["score"] < 10]
    below.sort(key=lambda cv: (-cv[1]["weight"] * (10 - cv[1]["score"]), order.index(cv[0])))
    pri = t["priorities"]
    return {"status": s["status"], "recommendations": [
        {"rank": i + 1, "category": c, "priority": pri[min(i, len(pri) - 1)], "score": v["score"],
         "weight": v["weight"], "impact": v["weight"] * (10 - v["score"]), "detail": v["detail"]}
        for i, (c, v) in enumerate(below)]}


def history(lines: list, results: dict, t: Optional[dict] = None) -> tuple:
    t = t or thresholds()
    s = score(results, t)
    if s["status"] == "invalid":
        return EXIT_FAIL, s
    if s["composite"] is None:
        return EXIT_UNSCORED, {"trend": "none", "reason": s["status"]}
    rows = lines[-t["history_rows"]:]
    if not rows:
        return EXIT_OK, {"trend": "first run", "current": s["composite"]}
    current_set = set(s["coverage"]["scored"])
    last = rows[-1]
    last_set = {c for c in t["weights"] if last.get(c) is not None}
    if last_set != current_set:
        return EXIT_OK, {"trend": "coverage changed: not comparable", "current": s["composite"],
                         "previous": last.get("score"), "previous_scored": sorted(last_set),
                         "current_scored": sorted(current_set)}
    delta = one_decimal(s["composite"] - last["score"])
    declines = [{"category": c, "previous": last[c], "current": s["categories"][c]["score"],
                 "delta": s["categories"][c]["score"] - last[c]}
                for c in t["weights"] if c in current_set and s["categories"][c]["score"] < last[c]]
    trend = "improving" if delta > 0 else "declining" if delta < 0 else "unchanged"
    return (EXIT_FAIL if trend == "declining" else EXIT_OK), {
        "trend": trend, "current": s["composite"], "previous": last["score"], "delta": delta, "declines": declines,
        "rows": len(rows)}


def read_history(path) -> list:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc}")
    rows = []
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.strip():
            try:
                rows.append(json.loads(raw))
            except ValueError as exc:
                raise UsageError(f"{path}:{n}: not a JSON line: {exc}")
    return rows


SECTION = re.compile(r"^##\s+Health Stack\s*$", re.M)


def declared(text: str) -> Optional[dict]:
    """The `## Health Stack` section's `- category: command` lines, or None when there is no section."""
    m = SECTION.search(text)
    if not m:
        return None
    body = text[m.end():]
    nxt = re.search(r"^#{1,2}\s", body, re.M)
    body = body[:nxt.start()] if nxt else body
    found = {}
    for line in body.splitlines():
        lm = re.match(r"^\s*[-*]\s*([\w-]+)\s*:\s*(.+?)\s*$", line)
        if lm:
            cat = ALIASES.get(lm.group(1).lower(), lm.group(1).lower())
            found[cat] = lm.group(2)
    return found


def detect(repo: Path, t: Optional[dict] = None) -> dict:
    t = t or thresholds()
    for name in ("AGENTS.md", "CLAUDE.md"):
        p = repo / name
        if p.is_file():
            stack = declared(p.read_text(encoding="utf-8", errors="replace"))
            if stack is not None:
                cats = {c: ({"command": stack[c], "source": f"{name} Health Stack"} if c in stack and
                            stack[c].lower() not in ("none", "-") else
                            {"command": None, "reason": f"{name} Health Stack declares none"})
                        for c in t["weights"]}
                unknown = sorted(set(stack) - set(t["weights"]))
                return {"source": f"{name} Health Stack", "categories": cats, "unknown": unknown}
    def has(*names):
        return any((repo / n).exists() for n in names)
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8", errors="replace") if has("pyproject.toml") else ""
    package = {}
    if has("package.json"):
        try:
            package = json.loads((repo / "package.json").read_text(encoding="utf-8"))
        except ValueError:
            package = {}
    shell_files = sorted(str(p.relative_to(repo)) for p in repo.rglob("*.sh")
                         if not {".git", "node_modules", ".venv", "venv"} & set(p.parts))
    found = {}
    if has("tsconfig.json"):
        found["typecheck"] = ("npx tsc --noEmit", "tsconfig.json")
    elif "[tool.mypy]" in pyproject or has("mypy.ini"):
        found["typecheck"] = ("mypy .", "mypy configuration")
    elif "[tool.pyright]" in pyproject or has("pyrightconfig.json"):
        found["typecheck"] = ("pyright", "pyright configuration")
    if has("biome.json", "biome.jsonc"):
        found["lint"] = ("npx biome check .", "biome.json")
    elif any(repo.glob("eslint.config.*")) or any(repo.glob(".eslintrc*")):
        found["lint"] = ("npx eslint .", "eslint configuration")
    elif "[tool.ruff" in pyproject or has("ruff.toml", ".ruff.toml"):
        found["lint"] = ("ruff check .", "ruff configuration")
    if (package.get("scripts") or {}).get("test"):
        found["tests"] = ("npm test", "package.json scripts.test")
    elif "[tool.pytest" in pyproject or has("pytest.ini", "conftest.py"):
        found["tests"] = ("python -m pytest", "pytest configuration")
    if has("knip.json", "knip.jsonc", ".knip.json"):
        found["deadcode"] = ("npx knip", "knip configuration")
    elif "[tool.vulture]" in pyproject:
        found["deadcode"] = ("vulture .", "vulture configuration")
    if shell_files:
        if shutil.which("shellcheck"):
            found["shell"] = ("shellcheck " + " ".join(shell_files), f"{len(shell_files)} shell scripts")
    found["index"] = (f'python <westack-onboard>/scripts/codeindex.py doctor --repo "{repo}"',
                      "westack-onboard, when installed: record its verdict; no index at all is skipped, not ERR")
    cats = {}
    for c in t["weights"]:
        if c in found:
            cats[c] = {"command": found[c][0], "source": found[c][1]}
        elif c == "shell" and shell_files:
            cats[c] = {"command": None, "reason": f"{len(shell_files)} shell scripts, shellcheck not on PATH"}
        elif c == "shell":
            cats[c] = {"command": None, "reason": "no shell scripts"}
        else:
            cats[c] = {"command": None, "reason": "no configuration found; declare it in a Health Stack section"}
    return {"source": "detected from files", "categories": cats, "unknown": []}


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    usage = __doc__.split("\n\n")[1]
    try:
        if not argv:
            raise UsageError("no command")
        cmd, args = argv[0], argv[1:]
        if cmd == "detect" and len(args) == 1:
            repo = Path(args[0])
            if not repo.is_dir():
                raise UsageError(f"not a folder: {repo}")
            print(json.dumps(detect(repo), indent=2))
            return EXIT_OK
        if cmd == "score" and len(args) == 1:
            result = score(load_json(args[0]))
            print(json.dumps(result, indent=2))
            if result["status"] == "invalid":
                return EXIT_FAIL
            return EXIT_UNSCORED if result["composite"] is None else EXIT_OK
        if cmd == "recommend" and len(args) == 1:
            result = recommend(load_json(args[0]))
            print(json.dumps(result, indent=2))
            return EXIT_FAIL if result["status"] == "invalid" else EXIT_OK
        if cmd == "history" and len(args) == 2:
            code, result = history(read_history(args[0]), load_json(args[1]))
            print(json.dumps(result, indent=2))
            return code
        raise UsageError(f"unknown command or wrong arguments: {' '.join(argv)}")
    except UsageError as exc:
        print(f"healthcheck.py: {exc}\n{usage}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
