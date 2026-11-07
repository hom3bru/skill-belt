#!/usr/bin/env python3
"""westack-retro metrics. Standard library only; reads saved files, runs no command, writes nothing.

  python retro.py metrics  <gitlog.txt> --since YYYY-MM-DD [--until YYYY-MM-DD] [--you EMAIL]
  python retro.py compare  <previous.json> <current.json>
  python retro.py discover <sessions-root> [<sessions-root> ...] --since YYYY-MM-DD

<gitlog.txt> is the saved output of exactly this command, run by the agent (read-only):

  git log <ref> --since=<since>T00:00:00 [--until=<until>T00:00:00] --date=iso-strict --numstat
      --pretty=format:@@%H%x1f%an%x1f%ae%x1f%aI%x1f%P%x1f%s%x1f%(trailers:key=Co-authored-by,valueonly,separator=%x3b)

`discover` reads local agent session logs (JSONL with a "cwd" field, as Claude Code and Codex write them) and
lists the repositories worked in since a date. Exit codes: 0 ok; 1 nothing in the window (an empty or stale
window is not a quiet week); 64 usage or unreadable input.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

SESSION_GAP_MIN = 45
DEEP_MIN, MEDIUM_MIN = 50, 20
SIZE_BUCKETS = ((100, "small"), (500, "medium"), (1500, "large"))
TYPES = ("feat", "fix", "refactor", "test", "docs", "chore", "perf", "ci", "build", "style")
TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]*\.py$|_test\.(py|go|rb)$|\.(test|spec)\.[a-z]+$", re.I)
AI_COAUTHOR = re.compile(r"noreply@anthropic\.com|claude|copilot|codex|cursor|openai", re.I)
WEIGHT_CAP = 20


class UsageError(Exception):
    pass


def parse_log(text: str) -> list:
    commits, cur = [], None
    for line in text.splitlines():
        if line.startswith("@@"):
            parts = line[2:].split("\x1f")
            if len(parts) < 6:
                raise UsageError("a commit line lacks the fields of the documented --pretty format")
            sha, name, email, when, parents, subject = parts[:6]
            trailers = parts[6] if len(parts) > 6 else ""
            cur = {"sha": sha, "author": name, "email": email.lower(), "when": datetime.fromisoformat(when),
                   "merge": len(parents.split()) > 1, "subject": subject,
                   "coauthors": [t.strip() for t in trailers.split(";") if t.strip()], "files": []}
            commits.append(cur)
        elif cur is not None and line.strip():
            cols = line.split("\t")
            if len(cols) == 3:
                ins = int(cols[0]) if cols[0].isdigit() else 0
                dele = int(cols[1]) if cols[1].isdigit() else 0
                cur["files"].append((cols[2], ins, dele))
    return commits


def commit_type(subject: str) -> str:
    m = re.match(r"^(\w+)(\([^)]*\))?!?:", subject)
    return m.group(1).lower() if m and m.group(1).lower() in TYPES else "other"


def sessions(times: list) -> list:
    if not times:
        return []
    times = sorted(times)
    out, start, last = [], times[0], times[0]
    for t in times[1:]:
        if (t - last) > timedelta(minutes=SESSION_GAP_MIN):
            out.append((start, last))
            start = t
        last = t
    out.append((start, last))
    return [round((b - a).total_seconds() / 60) for a, b in out]


def streak(days: set) -> tuple:
    if not days:
        return 0, None
    anchor = max(days)
    n, d = 0, anchor
    while d in days:
        n, d = n + 1, d - timedelta(days=1)
    return n, anchor.isoformat()


def metrics(commits: list, since: date, until: Optional[date], you: Optional[str]) -> dict:
    inwin = [c for c in commits if c["when"].date() >= since and (until is None or c["when"].date() < until)]
    work = [c for c in inwin if not c["merge"]]
    ins = sum(i for c in work for _, i, _ in c["files"])
    dele = sum(d for c in work for _, _, d in c["files"])
    test_ins = sum(i for c in work for p, i, _ in c["files"] if TEST_PATH.search(p))
    sess = sessions([c["when"] for c in work])
    types = Counter(commit_type(c["subject"]) for c in work)
    sizes = Counter()
    for c in work:
        loc = sum(i + d for _, i, d in c["files"])
        sizes[next((name for limit, name in SIZE_BUCKETS if loc < limit), "xl")] += 1
    file_changes = Counter(p for c in work for p, _, _ in c["files"])
    top_dirs = Counter((p.split("/")[0] + "/") if "/" in p else "./" for c in work for p, _, _ in c["files"])
    focus_dir, focus_n = (top_dirs.most_common(1)[0] if top_dirs else (None, 0))
    biggest = max(work, key=lambda c: sum(i + d for _, i, d in c["files"]), default=None)
    authors = defaultdict(lambda: {"commits": 0, "insertions": 0, "deletions": 0, "test_insertions": 0})
    for c in work:
        a = authors[c["email"]]
        a["name"] = c["author"]
        a["commits"] += 1
        a["insertions"] += sum(i for _, i, _ in c["files"])
        a["deletions"] += sum(d for _, _, d in c["files"])
        a["test_insertions"] += sum(i for p, i, _ in c["files"] if TEST_PATH.search(p))
    ai = sum(1 for c in work if any(AI_COAUTHOR.search(x) for x in c["coauthors"]))
    human_coauthors = Counter(x for c in work for x in c["coauthors"] if not AI_COAUTHOR.search(x))
    days = {c["when"].date() for c in work}
    team_streak = streak(days)
    you_streak = streak({c["when"].date() for c in work if you and c["email"] == you.lower()}) if you else None
    hours = Counter(c["when"].hour for c in work)
    latest = max((c["when"] for c in commits), default=None)
    return {
        "format": "westack-retro-metrics-1",
        "window": {"since": since.isoformat(), "until": until.isoformat() if until else None},
        "guard": ("empty-window" if not work else "ok"),
        "latest_commit": latest.isoformat() if latest else None,
        "commits": len(work), "merge_commits": sum(1 for c in inwin if c["merge"]),
        "contributors": len(authors),
        "insertions": ins, "deletions": dele, "net": ins - dele,
        "test_insertions": test_ins, "test_ratio": round(test_ins / ins, 3) if ins else None,
        "weighted_commits": sum(min(len(c["files"]), WEIGHT_CAP) for c in work),
        "active_days": len(days),
        "sessions": {"count": len(sess), "deep": sum(1 for m in sess if m >= DEEP_MIN),
                     "medium": sum(1 for m in sess if MEDIUM_MIN <= m < DEEP_MIN),
                     "micro": sum(1 for m in sess if m < MEDIUM_MIN), "active_minutes": sum(sess),
                     "median_minutes": statistics.median(sess) if sess else None},
        "types": dict(types), "fix_ratio": round(types["fix"] / len(work), 3) if work else None,
        "sizes": {k: sizes.get(k, 0) for k in ("small", "medium", "large", "xl")},
        "hours": {f"{h:02d}": n for h, n in sorted(hours.items())},
        "peak_hour": f"{hours.most_common(1)[0][0]:02d}" if hours else None,
        "focus": {"dir": focus_dir, "share": round(focus_n / sum(top_dirs.values()), 3) if top_dirs else None},
        "hotspots": [{"file": f, "changes": n} for f, n in file_changes.most_common(10)],
        "biggest_commit": ({"sha": biggest["sha"][:12], "subject": biggest["subject"],
                            "loc": sum(i + d for _, i, d in biggest["files"])} if biggest else None),
        "authors": sorted(({"email": e, **v} for e, v in authors.items()), key=lambda a: -a["commits"]),
        "ai_assisted_commits": ai, "human_coauthors": dict(human_coauthors),
        "team_streak": {"days": team_streak[0], "anchor": team_streak[1]},
        "you_streak": ({"days": you_streak[0], "anchor": you_streak[1]} if you_streak else None),
    }


def compare(prev: dict, cur: dict) -> dict:
    keys = ("commits", "insertions", "deletions", "net", "test_ratio", "weighted_commits", "active_days", "fix_ratio",
            "contributors", "ai_assisted_commits")
    rows = {}
    for k in keys:
        a, b = prev.get(k), cur.get(k)
        rows[k] = {"previous": a, "current": b,
                   "delta": (round(b - a, 3) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None)}
    rows["sessions"] = {"previous": prev.get("sessions", {}).get("count"), "current": cur.get("sessions", {}).get("count")}
    return {"previous_window": prev.get("window"), "current_window": cur.get("window"), "metrics": rows}


def discover(roots: list, since: date) -> dict:
    repos = defaultdict(lambda: {"sessions": 0, "last": None, "tools": set()})
    read = 0
    for root in roots:
        tool = "codex" if "codex" in str(root).lower() else ("claude" if ".claude" in str(root).lower() else "other")
        # A host's log directory can sit inside another host's cache or temporary folder.
        for part in reversed(Path(root).parts):
            if part.lower() in (".claude", ".codex"):
                tool = part.lower().lstrip(".")
                break
        for f in Path(root).rglob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime.date() < since:
                    continue
                with open(f, encoding="utf-8", errors="replace") as fh:
                    cwd = None
                    for _, line in zip(range(200), fh):
                        m = re.search(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"', line)
                        if m:
                            cwd = json.loads('"' + m.group(1) + '"')
                            break
            except OSError:
                continue
            read += 1
            if cwd:
                r = repos[cwd]
                r["sessions"] += 1
                r["tools"].add(tool)
                r["last"] = max(r["last"] or mtime, mtime)
    out = sorted(({"cwd": k, "sessions": v["sessions"], "last": v["last"].isoformat(timespec="minutes"),
                   "tools": sorted(v["tools"])} for k, v in repos.items()), key=lambda r: -r["sessions"])
    return {"since": since.isoformat(), "session_files": read, "repositories": out}


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = __doc__.split("\n\n")[1]
    try:
        if not argv:
            raise UsageError("no command")
        cmd = argv[0]
        opts, pos, i = {}, [], 1
        while i < len(argv):
            if argv[i].startswith("--"):
                if i + 1 >= len(argv):
                    raise UsageError(f"{argv[i]} needs a value")
                opts[argv[i][2:]] = argv[i + 1]
                i += 2
            else:
                pos.append(argv[i])
                i += 1

        def day(key, required=True):
            if key not in opts:
                if required:
                    raise UsageError(f"--{key} YYYY-MM-DD is required")
                return None
            try:
                return date.fromisoformat(opts[key])
            except ValueError:
                raise UsageError(f"--{key} must be YYYY-MM-DD")

        def load(p):
            try:
                return Path(p).read_text(encoding="utf-8")
            except OSError as exc:
                raise UsageError(f"cannot read {p}: {exc}")
        if cmd == "metrics" and len(pos) == 1:
            result = metrics(parse_log(load(pos[0])), day("since"), day("until", False), opts.get("you"))
            print(json.dumps(result, indent=2))
            return 0 if result["guard"] == "ok" else 1
        if cmd == "compare" and len(pos) == 2:
            print(json.dumps(compare(json.loads(load(pos[0])), json.loads(load(pos[1]))), indent=2))
            return 0
        if cmd == "discover" and pos:
            result = discover(pos, day("since"))
            print(json.dumps(result, indent=2))
            return 0 if result["repositories"] else 1
        raise UsageError(f"unknown command or wrong arguments: {' '.join(argv)}")
    except (UsageError, ValueError) as exc:
        print(f"retro.py: {exc}\n{usage}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    sys.exit(main())
