#!/usr/bin/env python3
"""westack-qa report helper. Standard library only; reads files, runs no browser, writes nothing.

  python qacheck.py score    <report.json>              compute the health score the report must carry
  python qacheck.py validate <report.json>              check the report's shape, evidence and score
  python qacheck.py diff     <before.txt> <after.txt>   line diff of two accessibility snapshots
  python qacheck.py compare  <baseline.json> <report.json>   fixed, new and score delta (like coverage only)
  python qacheck.py expect   <report.json> <expect.json>     every planted defect was found (evals)
  python qacheck.py loop     <report.json>              fix loop: continue, check in with the user, or stop
  python qacheck.py monitor  <baseline.json> <checks.json>   monitor: confirmed alerts, observations, status
  python qacheck.py dx       <plan-dx.json> <live-dx.json>   DX audit: live scores against a plan review's

`validate` also checks a developer-experience record (westack-dx-record-1, references/dx-audit.md).
Exit codes: 0 ok (loop: continue); 1 the report is invalid, a check failed, an expected defect is missing, the
loop must stop or check in, or a live DX score fell short of the plan; 2 cannot tell (a comparison refused because
coverage, environment, product or persona differ); 64 usage or unreadable input.
The numbers live in references/thresholds.json.
"""
from __future__ import annotations

import difflib
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

REPORT_FORMAT = "westack-qa-report-1"
MODES = ("quick", "full", "diff-aware", "regression")
RUNTIME = ("passed", "failed", "blocked", "not-run")
FIX_STATUS = ("verified", "best-effort", "reverted", "deferred")
THRESHOLDS = Path(__file__).resolve().parent.parent / "references" / "thresholds.json"
EXIT_OK, EXIT_FAIL, EXIT_UNSURE, EXIT_USAGE = 0, 1, 2, 64


class UsageError(Exception):
    pass


def load_json(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read {path}: {exc}")


def thresholds() -> dict:
    return load_json(THRESHOLDS)


def round_half_up(x: float) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def console_score(errors: int, t: dict) -> int:
    for bucket in t["console_buckets"]:
        if bucket["max_errors"] is None or errors <= bucket["max_errors"]:
            return bucket["score"]
    raise UsageError("thresholds.json: console_buckets has no open-ended last bucket")


def compute_score(report: dict, t: Optional[dict] = None) -> dict:
    """Category scores for the tested categories and the weighted final score (None when nothing was tested)."""
    t = t or thresholds()
    tested = [c for c in t["weights"] if c in set(report.get("tested", []))]
    cats = {}
    for cat in tested:
        if cat == "console":
            cats[cat] = console_score(len(report.get("console_errors", [])), t)
        elif cat == "links":
            cats[cat] = max(0, 100 - t["link_deduction"] * len(report.get("links", {}).get("broken", [])))
        else:
            lost = sum(t["deductions"][i["severity"]] for i in report.get("issues", [])
                       if i.get("category") == cat and i.get("confirmed", True) and i.get("severity") in t["deductions"])
            cats[cat] = max(0, 100 - lost)
    if not tested:
        return {"status": "not scored", "value": None, "categories": {}, "provisional": False}
    weight = sum(t["weights"][c] for c in tested)
    value = round_half_up(sum(cats[c] * t["weights"][c] for c in tested) / weight)
    return {"status": "scored", "value": value, "categories": cats, "provisional": len(tested) < len(t["weights"])}


def validate(report: dict, t: Optional[dict] = None) -> list:
    if report.get("format") == DX_FORMAT:
        return validate_dx(report)
    t = t or thresholds()
    errors = []
    if report.get("format") != REPORT_FORMAT:
        return [f"format must be {REPORT_FORMAT}"]
    if report.get("mode") not in MODES:
        errors.append(f"mode must be one of {', '.join(MODES)}")
    for key in ("target", "grant"):
        if not str(report.get(key, "")).strip():
            errors.append(f"{key} is required")
    if report.get("mode") == "regression" and not report.get("baseline"):
        errors.append("a regression report names its baseline")
    tested = report.get("tested", [])
    unknown = [c for c in tested if c not in t["weights"]]
    if unknown:
        errors.append(f"unknown tested categories: {unknown}")
    runtime = report.get("runtime", [])
    for r in runtime:
        if r.get("status") not in RUNTIME:
            errors.append(f"runtime {r.get('id')}: status must be one of {', '.join(RUNTIME)}")
        if r.get("status") == "not-run" and not str(r.get("why", "")).strip():
            errors.append(f"runtime {r.get('id')}: a not-run check says why")
    if not report.get("driver"):
        if not report.get("degraded"):
            errors.append("no driver: the report must be marked degraded")
        if any(r.get("status") != "not-run" for r in runtime) or not runtime:
            errors.append("no driver: every runtime check is not-run")
        if tested:
            errors.append("no driver: nothing was tested in a browser")
    else:
        env = report.get("environment", {})
        for key in ("os", "browser", "headless", "viewport", "device_pixel_ratio"):
            if key not in env:
                errors.append(f"environment.{key} is required with a driver")
    seen = set()
    for issue in report.get("issues", []):
        iid = issue.get("id")
        if iid in seen:
            errors.append(f"issue {iid} is repeated")
        seen.add(iid)
        if issue.get("severity") not in t["deductions"]:
            errors.append(f"issue {iid}: severity must be one of {', '.join(t['deductions'])}")
        if issue.get("category") not in t["weights"]:
            errors.append(f"issue {iid}: category must be one of {', '.join(t['weights'])}")
        elif issue.get("category") not in tested:
            errors.append(f"issue {iid}: its category {issue.get('category')} is not among the tested categories")
        if not issue.get("evidence"):
            errors.append(f"issue {iid}: evidence is required")
        if not str(issue.get("title", "")).strip() or not str(issue.get("page", "")).strip():
            errors.append(f"issue {iid}: title and page are required")
    keys = [(e.get("message"), e.get("source")) for e in report.get("console_errors", [])]
    if len(keys) != len(set(keys)):
        errors.append("console_errors must be deduplicated by message and source")
    broken = [b.get("url") for b in report.get("links", {}).get("broken", [])]
    if len(broken) != len(set(broken)):
        errors.append("links.broken must list each destination once")
    expected = compute_score(report, t)
    claimed = report.get("score", {})
    for key in ("status", "value", "categories", "provisional"):
        if claimed.get(key) != expected[key]:
            errors.append(f"score.{key} is {claimed.get(key)!r}; the rubric gives {expected[key]!r}")
    if "fix_loop" in report:
        errors.extend(validate_fix_loop(report["fix_loop"]))
    return errors


def validate_fix_loop(loop: dict) -> list:
    errors = []
    if not str(loop.get("edit_grant", "")).strip():
        errors.append("fix_loop: edit_grant names the paths the user allowed")
    for n, fix in enumerate(loop.get("fixes", []), 1):
        where = f"fix_loop.fixes[{n}]"
        issue = fix.get("issue", {})
        if not all(str(issue.get(k, "")).strip() for k in ("id", "title", "category", "page")):
            errors.append(f"{where}: issue needs id, title, category and page")
        status = fix.get("status")
        if status not in FIX_STATUS:
            errors.append(f"{where}: status must be one of {', '.join(FIX_STATUS)}")
        if status in ("verified", "best-effort", "reverted") and not fix.get("files"):
            errors.append(f"{where}: an applied fix lists its files")
        if status == "verified" and not fix.get("recheck"):
            errors.append(f"{where}: a verified fix carries its re-check evidence")
        if status == "verified" and not (fix.get("test") or str(fix.get("test_missing", "")).strip()):
            errors.append(f"{where}: name the regression test, or say in test_missing why there is none")
        if status in ("best-effort", "deferred") and not str(fix.get("why", "")).strip():
            errors.append(f"{where}: {status} says why")
        if fix.get("commit") and not loop.get("commit_grant"):
            errors.append(f"{where}: a commit without commit_grant")
    return errors


def loop_decision(report: dict, t: Optional[dict] = None) -> dict:
    """Continue, check in with the user, or stop, by the fix-loop rule in thresholds.json."""
    rule = (t or thresholds())["fix_loop"]
    fixes = [f for f in report.get("fix_loop", {}).get("fixes", []) if not f.get("test_only")]
    applied = [f for f in fixes if f.get("status") in ("verified", "best-effort", "reverted")]
    stop, ask = [], []
    reverts = sum(1 for f in applied if f["status"] == "reverted")
    if reverts >= rule["max_reverts"]:
        stop.append(f"{reverts} reverts")
    unrelated = [f["issue"].get("id") for f in applied if f.get("unrelated_files")]
    if unrelated:
        stop.append(f"a fix edited a file unrelated to its issue ({', '.join(map(str, unrelated))})")
    streak = 0
    for f in applied:
        streak = streak + 1 if len(f.get("files", [])) > rule["wide_fix_files"] else 0
        if streak >= rule["wide_fix_streak"]:
            stop.append(f"{streak} fixes in a row each touched more than {rule['wide_fix_files']} files")
            break
    if len(applied) >= rule["hard_cap"]:
        stop.append(f"the hard cap of {rule['hard_cap']} fixes")
    remaining = [i.get("severity") for i in report.get("issues", []) if i.get("confirmed", True)]
    if remaining and all(s == "low" for s in remaining):
        stop.append("only low issues remain")
    if applied and (len(applied) % rule["checkpoint_every"] == 0 or applied[-1]["status"] == "reverted"):
        ask.append("check-in due: every %d fixes and after a revert" % rule["checkpoint_every"])
    return {"decision": "stop" if stop else ("ask" if ask else "continue"), "stop": stop, "ask": ask,
            "fixes_counted": len(applied)}


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def check_findings(base: dict, page: dict, rule: dict) -> dict:
    """What one check of one page shows against its baseline: {key: (severity, message)}. Changes, not absolutes."""
    found = {}
    if not page.get("loaded", False):
        found[("load",)] = ("critical", "the page did not load")
        return found
    known = set(base.get("console_errors", []))
    for msg in page.get("console_errors", []):
        if msg not in known:
            found[("console", msg)] = ("high", f"new console error: {msg}")
    b_ms, ms = base.get("load_ms"), page.get("load_ms")
    if isinstance(b_ms, (int, float)) and isinstance(ms, (int, float)) and b_ms > 0 and ms > rule["slow_factor"] * b_ms:
        found[("slow",)] = ("medium", f"load {ms} ms is over {rule['slow_factor']}x the baseline {b_ms} ms")
    known_broken = set(base.get("broken", []))
    for url in page.get("broken", []):
        if url not in known_broken:
            found[("broken", url)] = ("low", f"new broken link: {url}")
    return found


def monitor(baseline: dict, checks: dict, t: Optional[dict] = None) -> dict:
    """Alerts only for a pattern seen on persist_checks consecutive checks; a shorter run of it is an observation."""
    rule = (t or thresholds())["monitor"]
    base_pages = {p["url"]: p for p in baseline.get("pages", [])}
    streak, alerts, observations = {}, {}, []
    seq = checks.get("checks", [])
    for k, check in enumerate(seq, 1):
        seen = set()
        for page in check.get("pages", []):
            for key, (sev, msg) in check_findings(base_pages.get(page["url"], {}), page, rule).items():
                full = (page["url"],) + key
                seen.add(full)
                start = streak.get(full, (k, sev, msg))[0]
                streak[full] = (start, sev, msg)
                if k - start + 1 >= rule["persist_checks"] and full not in alerts:
                    alerts[full] = {"severity": sev, "page": page["url"], "message": msg,
                                    "first_seen": start, "confirmed_at": k, "resolved_at": None}
        for full in [f for f in streak if f not in seen]:
            start, sev, msg = streak.pop(full)
            if full in alerts:
                alerts[full]["resolved_at"] = k
            else:
                observations.append({"severity": sev, "page": full[0], "message": msg, "first_seen": start,
                                     "gone_at": k, "kind": "transient"})
    for full, (start, sev, msg) in streak.items():
        if full not in alerts:
            observations.append({"severity": sev, "page": full[0], "message": msg, "first_seen": start,
                                 "kind": "pending"})
    pages = {}
    for url in sorted({p["url"] for c in seq for p in c.get("pages", [])} | set(base_pages)):
        sevs = [a["severity"] for a in alerts.values() if a["page"] == url]
        pages[url] = "broken" if "critical" in sevs else ("degraded" if sevs else "healthy")
    order = ["healthy", "degraded", "broken"]
    status = max(pages.values(), key=order.index) if pages else "healthy"
    return {"format": "westack-qa-monitor-1", "checks": len(seq), "status": status, "pages": pages,
            "alerts": sorted(alerts.values(), key=lambda a: (SEVERITY_RANK[a["severity"]], a["confirmed_at"])),
            "observations": observations, "rule": rule}


def issue_key(issue: dict) -> tuple:
    return issue.get("category"), issue.get("page"), " ".join(str(issue.get("title", "")).lower().split())


def compare(baseline: dict, report: dict) -> tuple:
    """(exit code, result). Refused (2) when coverage or environment differ: compare like with like only."""
    reasons = []
    if sorted(baseline.get("tested", [])) != sorted(report.get("tested", [])):
        reasons.append("tested categories differ")
    for key in ("os", "browser", "headless", "viewport", "device_pixel_ratio"):
        if baseline.get("environment", {}).get(key) != report.get("environment", {}).get(key):
            reasons.append(f"environment.{key} differs")
    if reasons:
        return EXIT_UNSURE, {"status": "refused", "reasons": reasons}
    before = {issue_key(i): i["id"] for i in baseline.get("issues", [])}
    after = {issue_key(i): i["id"] for i in report.get("issues", [])}
    b, a = baseline.get("score", {}).get("value"), report.get("score", {}).get("value")
    return EXIT_OK, {"status": "compared", "fixed": sorted(before[k] for k in before.keys() - after.keys()),
                     "new": sorted(after[k] for k in after.keys() - before.keys()),
                     "score_delta": (a - b) if isinstance(a, int) and isinstance(b, int) else None}


def expect_monitor(result: dict, wanted: dict) -> list:
    problems = []
    for w in wanted.get("alerts", []):
        hits = [a for a in result.get("alerts", []) if a["severity"] == w["severity"] and a["page"].endswith(w["page"])
                and any(m.lower() in a["message"].lower() for m in w["match"]) and a["confirmed_at"] == w["confirmed_at"]]
        if not hits:
            problems.append(f"expected a {w['severity']} alert on {w['page']} confirmed at check {w['confirmed_at']}")
    early = [a for a in result.get("alerts", []) if a["confirmed_at"] < wanted.get("no_alert_before", 0)]
    if early:
        problems.append(f"alerts confirmed before check {wanted['no_alert_before']}: {[a['message'] for a in early]}")
    if wanted.get("status") and result.get("status") != wanted["status"]:
        problems.append(f"status is {result.get('status')}, expected {wanted['status']}")
    return problems


def expect(report: dict, wanted: dict, t: Optional[dict] = None) -> list:
    """Problems with the report against the planted defects; empty means every one was found."""
    if report.get("format") == "westack-qa-monitor-1":
        return expect_monitor(report, wanted)
    problems = [f"invalid report: {e}" for e in validate(report, t)]
    if not report.get("driver"):
        problems.append("the report names no driver, so no browser run produced it")
    for d in wanted.get("defects", []):
        found = [i for i in report.get("issues", [])
                 if i.get("category") == d["category"] and str(i.get("page", "")).endswith(d["page"])
                 and any(m.lower() in (str(i.get("title", "")) + " " + json.dumps(i.get("evidence", []))).lower()
                         for m in d["match"])]
        if not found:
            problems.append(f"planted defect {d['id']} ({d['category']} on {d['page']}) was not found")

    def matches(i, d):
        text = (str(i.get("title", "")) + " " + json.dumps(i.get("evidence", []))).lower()
        return i.get("category") == d["category"] and str(i.get("page", "")).endswith(d["page"]) \
            and any(m.lower() in text for m in d["match"])

    for d in wanted.get("fixed", []):
        fixes = [f for f in report.get("fix_loop", {}).get("fixes", []) if matches(f.get("issue", {}), d)]
        if not any(f.get("status") == "verified" for f in fixes):
            problems.append(f"defect {d['id']} has no verified fix in fix_loop")
        if any(matches(i, d) for i in report.get("issues", [])):
            problems.append(f"defect {d['id']} still appears among the remaining issues")
    return problems


def snapshot_diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        "previous snapshot", "current snapshot"))


# Developer-experience records. The rubric is the core's references/dx.md; westack-review's dxcheck.py checks the
# same format for plans. The ids and tiers are repeated here so the check runs without the core or that skill.
DX_FORMAT = "westack-dx-record-1"
DX_DIMENSIONS = ("getting-started", "api-cli", "errors", "docs", "upgrade", "environment", "community", "measurement")
DX_MARKS = ("tested", "partial", "inferred")
DX_TIERS = ("champion", "competitive", "needs-work", "red-flag")


def dx_tier(minutes: float) -> str:
    if minutes < 2:
        return "champion"
    if minutes <= 5:
        return "competitive"
    if minutes <= 10:
        return "needs-work"
    return "red-flag"


def dx_overall(dims: list) -> Optional[float]:
    scores = [d.get("score") for d in dims if isinstance(d.get("score"), int) and not isinstance(d.get("score"), bool)]
    return round(sum(scores) / len(scores), 1) if scores else None


def dx_weakest(marks: list) -> Optional[str]:
    """tested only when every mark is tested, inferred only when every mark is inferred, otherwise partial."""
    if not marks or any(m not in DX_MARKS for m in marks):
        return None
    if all(m == "tested" for m in marks):
        return "tested"
    if all(m == "inferred" for m in marks):
        return "inferred"
    return "partial"


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_dx(record: dict) -> list:
    errors = []
    if record.get("format") != DX_FORMAT:
        return [f"format must be {DX_FORMAT}"]
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
    minutes, steps = tthw.get("minutes"), tthw.get("steps") or []
    if not is_number(minutes) or minutes < 0:
        errors.append("tthw.minutes must be a number")
    elif tthw.get("tier") != dx_tier(minutes):
        errors.append(f"tthw.tier is {tthw.get('tier')!r}; {minutes} minutes is {dx_tier(minutes)!r}")
    if not steps:
        errors.append("tthw.steps lists the steps counted")
    if tthw.get("evidence") not in DX_MARKS:
        errors.append(f"tthw.evidence must be one of {', '.join(DX_MARKS)}")
    dims = record.get("dimensions") or []
    ids = [d.get("id") for d in dims]
    for d in DX_DIMENSIONS:
        if ids.count(d) != 1:
            errors.append(f"dimension {d} must appear exactly once (found {ids.count(d)})")
    for d in dims:
        where = f"dimension {d.get('id')}"
        if d.get("id") not in DX_DIMENSIONS:
            errors.append(f"{where}: not a rubric dimension")
        score = d.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 10:
            errors.append(f"{where}: score must be a whole number from 0 to 10")
        if d.get("evidence") not in DX_MARKS:
            errors.append(f"{where}: evidence must be one of {', '.join(DX_MARKS)}")
        if not str(d.get("gap", "")).strip():
            errors.append(f"{where}: say what a 10 looks like and the gap")
        if kind == "live" and not (isinstance(d.get("refs"), list) and d["refs"]
                                   and all(str(r).strip() for r in d["refs"])):
            errors.append(f"{where}: a live score needs refs (a command and its exit code, a screenshot hash or a file:line)")
    if kind == "plan" and (any(d.get("evidence") in ("tested", "partial") for d in dims)
                           or tthw.get("evidence") in ("tested", "partial")):
        errors.append("a plan review ran nothing: every mark is inferred")
    if kind == "live" and steps:
        marks = []
        for i, s in enumerate(steps, 1):
            if not isinstance(s, dict):
                errors.append(f"tthw step {i}: a live step is an object with step, minutes, evidence and ref")
                continue
            if not str(s.get("step", "")).strip() or not str(s.get("ref", "")).strip():
                errors.append(f"tthw step {i}: step and ref are required")
            if not is_number(s.get("minutes")) or s["minutes"] < 0:
                errors.append(f"tthw step {i}: minutes must be a number")
            if s.get("evidence") not in DX_MARKS:
                errors.append(f"tthw step {i}: evidence must be one of {', '.join(DX_MARKS)}")
            marks.append(s.get("evidence"))
        if all(isinstance(s, dict) and is_number(s.get("minutes")) for s in steps) and is_number(minutes):
            total = round(sum(s["minutes"] for s in steps), 1)
            if round(minutes, 1) != total:
                errors.append(f"tthw.minutes is {minutes}; the steps add up to {total}")
        weakest = dx_weakest(marks)
        if weakest and tthw.get("evidence") != weakest:
            errors.append(f"tthw.evidence is {tthw.get('evidence')!r}; the step marks make it {weakest!r}")
    want = dx_overall(dims)
    if record.get("overall") != want:
        errors.append(f"overall is {record.get('overall')!r}; the mean of the scores is {want!r}")
    return errors


def dx_compare(plan: dict, live: dict, t: Optional[dict] = None) -> tuple:
    """A live audit against a plan review of the same product for the same developer: the boomerang check."""
    t = t or thresholds()
    drop = t["dx"]["alert_drop"]
    invalid = {name: errs for name, errs in (("plan", validate_dx(plan)), ("live", validate_dx(live))) if errs}
    if invalid:
        return EXIT_FAIL, {"status": "invalid", "errors": invalid}
    reasons = []
    if plan.get("kind") != "plan" or live.get("kind") != "live":
        reasons.append("the first record must be a plan review and the second a live audit")
    if plan["product"].strip() != live["product"].strip():
        reasons.append(f"different products: {plan['product']!r} vs {live['product']!r}")
    if plan["persona"]["who"].strip() != live["persona"]["who"].strip():
        reasons.append("different personas: every score is for one named developer")
    if reasons:
        return EXIT_UNSURE, {"status": "refused", "reasons": reasons}
    planned = {d["id"]: d["score"] for d in plan["dimensions"]}
    rows, alerts = [], []
    for d in live["dimensions"]:
        before, after = planned[d["id"]], d["score"]
        alert = after < before - drop
        rows.append({"id": d["id"], "plan": before, "live": after, "delta": after - before,
                     "live_evidence": d["evidence"], "alert": alert})
        if alert:
            alerts.append(d["id"])
    pt, lt = plan["tthw"], live["tthw"]
    tthw_alert = DX_TIERS.index(lt["tier"]) > DX_TIERS.index(pt["tier"])
    if tthw_alert:
        alerts.append("tthw")
    result = {"status": "fell-short" if alerts else "as-planned", "alert_drop": drop, "dimensions": rows,
              "tthw": {"plan_minutes": pt["minutes"], "live_minutes": lt["minutes"],
                       "delta": round(lt["minutes"] - pt["minutes"], 1), "plan_tier": pt["tier"],
                       "live_tier": lt["tier"], "alert": tthw_alert},
              "overall": {"plan": plan["overall"], "live": live["overall"],
                          "delta": round(live["overall"] - plan["overall"], 1)},
              "alerts": alerts}
    return (EXIT_FAIL if alerts else EXIT_OK), result


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    usage = __doc__.split("\n\n")[1]
    try:
        if not argv:
            raise UsageError("no command")
        cmd, args = argv[0], argv[1:]
        if cmd == "score" and len(args) == 1:
            print(json.dumps(compute_score(load_json(args[0])), indent=2))
            return EXIT_OK
        if cmd == "validate" and len(args) == 1:
            errors = validate(load_json(args[0]))
            print(json.dumps({"status": "valid" if not errors else "invalid", "errors": errors}, indent=2))
            return EXIT_OK if not errors else EXIT_FAIL
        if cmd == "diff" and len(args) == 2:
            texts = []
            for p in args:
                try:
                    texts.append(Path(p).read_text(encoding="utf-8"))
                except OSError as exc:
                    raise UsageError(f"cannot read {p}: {exc}")
            print(snapshot_diff(*texts) or "(no change)")
            return EXIT_OK
        if cmd == "compare" and len(args) == 2:
            code, result = compare(load_json(args[0]), load_json(args[1]))
            print(json.dumps(result, indent=2))
            return code
        if cmd == "monitor" and len(args) == 2:
            result = monitor(load_json(args[0]), load_json(args[1]))
            print(json.dumps(result, indent=2))
            return EXIT_OK if result["status"] == "healthy" else EXIT_FAIL
        if cmd == "loop" and len(args) == 1:
            result = loop_decision(load_json(args[0]))
            print(json.dumps(result, indent=2))
            return EXIT_OK if result["decision"] == "continue" else EXIT_FAIL
        if cmd == "dx" and len(args) == 2:
            code, result = dx_compare(load_json(args[0]), load_json(args[1]))
            print(json.dumps(result, indent=2))
            return code
        if cmd == "expect" and len(args) == 2:
            problems = expect(load_json(args[0]), load_json(args[1]))
            print(json.dumps({"status": "found" if not problems else "missing", "problems": problems}, indent=2))
            return EXIT_OK if not problems else EXIT_FAIL
        raise UsageError(f"unknown command or wrong arguments: {' '.join(argv)}")
    except UsageError as exc:
        print(f"qacheck.py: {exc}\n{usage}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
