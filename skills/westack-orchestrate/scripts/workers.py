"""westack-orchestrate worker checker: a dispatch plan and its briefs before any worker starts, the workers' returns
after, and the delegation ledger before the run closes.

  python workers.py plan DISPATCH [--repo DIR] [--core DIR]
  python workers.py collect DISPATCH [--record TASK] [--repo DIR] [--core DIR]
  python workers.py ledger TASK [--dispatch DISPATCH] [--core DIR]

DISPATCH is a dispatch plan (format westack-dispatch-1, references/brief.md). Its briefs, inputs, plan and runs folder
are read relative to its own folder, or to --repo. TASK is a westack task record (task.NNNN.json), read through the
core's record.py and contract, found beside this skill or at --core.

  plan     each brief names its tools (a subset of the coordinator's), a cap, a tier (from the contract), a wait mode,
           its write paths and the history it gets; no unfilled placeholder; an itemised done-when list and its end
           marker; declared inputs exist with their stated SHA-256; writers' paths (and each worker's own folder) are
           disjoint; clocks are absolute and in order; every brief echoes the plan's hash and the plan has not moved;
           the mode has its reasons, the worker cap holds, a budget reserves its checks; DS-8: each Done-when item ends
           with its source, `(source: user <their words>)`, `(source: plan <step>)` or `(source: rule <file>)`, or it is
           `unsourced-requirement`
  collect  every started worker has a start handle, or the whole set is refused; each return is missing, partial,
           rejected, stale or complete, and a complete one is model-reported until the task record (--record) holds a
           passing, current receipt whose claim names the worker; the batch takes its worst state, and an empty batch
           is inconclusive; every call reads every worker (a wake-up is a signal, not the state)
  ledger   the record's shape, then its delegates through the core's own checker (record.check_delegates, as for a
           finished record), plus a worker whose parent is not the task, a dispatched worker with no entry, and a run
           still waiting; DS-7: a user's pause or stop is the record's waiting_on, `hold: pause by user: <why>` (or stop)
           with a person-confirms check, and is `held` until the user lifts it (the next record drops waiting_on); a CI
           result, a clue or a bot comment never lifts it; a hold an event could satisfy is `hold-event-check`, one with
           no user or reason `hold-incomplete`

It checks structure and hashes, not whether a brief is wise or a worker honest: a complete return is a claim until a
receipt settles it. Exit 0 clean, 1 findings (collect: also refused, or any return not complete), 2 unreadable or,
for ledger, not-run without the core, 64 usage. Standard library only; it reads the files named and prints JSON; it
runs no command, starts no worker, writes no file and opens no network connection.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

FORMAT = "westack-workers-1"
DISPATCH_FORMAT = "westack-dispatch-1"
NOTE = ("Checks structure and hashes, not truth: a complete return is model-reported until a passing receipt in the "
        "task record settles it.")
REQUIRED = ("worker", "tier", "wait", "tools", "cap", "writes", "history")
WAITS = ("report", "handle")
MODES = ("workers", "inline")
DEFAULT_CAP = 7  # workers reporting to one coordinator; a plan raises it only with a reason
CAP = re.compile(r"\b\d+\s*(?:turns?|minutes?|mins?|hours?|hrs?|h|calls?|tool calls?)\b", re.I)
PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}|<<[^<>]*>>|(?<![\w<])<[A-Za-z0-9][\w .-]{0,40}>|\b(?:TODO|TBD|FIXME)\b|"
                         r"\[(?:fill|insert|todo|tbd)\b[^\]]*\]", re.M)
ITEM = re.compile(r"^\s*[-*]\s+([A-Za-z]+\d+)\s*:")
SOURCED = re.compile(r"\(source:\s*(?:user|plan|rule)\s+[^)\s][^)]*\)", re.I)  # DS-8: where a Done-when item comes from
HOLD_WORD = re.compile(r"\s*hold\b", re.I)  # DS-7: a waiting_on that records a user's pause or stop
HOLD = re.compile(r"\s*hold\s*:\s*(?:pause|stop)\s+by\s+user\s*:\s*\S", re.I)
ANSWER = re.compile(r"^\s*[-*]\s+([A-Za-z]+\d+)\s*:\s*(done|not done|could not)\b\s*[:,.;-]?\s*(.*)$", re.I)
FILE_LINE = re.compile(r"^\s*[-*]\s+(\S+)(?:\s+([0-9a-f]{64}))?\s*$")
COMMIT = re.compile(r"^commit:\s*(?:[0-9a-f]{40}|[0-9a-f]{64})\s*$", re.M)
ECHO = re.compile(r"^plan:\s*(\S+)\s+([0-9a-f]{64})\s*$", re.M)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
SEARCH_LISTS = (r"found", r"searched,?\s+nothing\s+found", r"not\s+searched")
CREDENTIAL_NAMES = {"credentials", "credentials.json", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "netrc", "_netrc"}
CREDENTIAL_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore")
# A batch takes its worst state; the order runs worst first.
ORDER = ("refused", "missing", "rejected", "stale", "partial", "model-reported", "settled")


def load_core(core=None):
    """The core's record.py module, or None when no core is found or it cannot load."""
    base = pathlib.Path(core) if core else pathlib.Path(__file__).resolve().parents[2] / "westack"
    path = base / "scripts" / "record.py"
    if not path.is_file():
        return None
    key = "westack_orchestrate_record_" + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except Exception:  # an unloadable core is reported as absent
            del sys.modules[key]
            return None
    return module


def tiers(record):
    """The delegate tiers the contract allows."""
    return tuple(record.CONTRACT["$defs"]["delegate"]["properties"]["tier"]["enum"])


def text(value):
    return isinstance(value, str) and bool(value.strip())


def finding(code, worker, detail):
    return {"code": code, "worker": worker, "detail": detail}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(block)
    return hasher.hexdigest()


def norm(path):
    """A repository-relative slash path without ./ or a trailing slash ('' is the whole tree), or None when it is not
    portable (absolute, a drive, or a .. segment)."""
    path = path.strip().replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return None
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if ".." in parts:
        return None
    return "/".join(parts)


def inside(root, relative):
    """root/relative for a portable, non-empty relative path, else None."""
    clean = norm(str(relative or ""))
    return root / clean if clean else None


def scope(path):
    """What a write path can touch, for the overlap check: a glob widens to the folder holding its first wildcard."""
    for index, char in enumerate(path):
        if char in "*?[":
            return path[:index].rsplit("/", 1)[0] if "/" in path[:index] else ""
    return path


def overlaps(a, b):
    return a == b or a == "" or b == "" or a.startswith(b + "/") or b.startswith(a + "/")


def parse_brief(raw):
    """(header dict, body text, body's first line number) from a brief; header is None without a header block."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, raw, 1
    header = {}
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return header, "\n".join(lines[number:]), number + 1
        if ":" in line:
            key, value = line.split(":", 1)
            header[key.strip().lower()] = value.strip()
    return None, raw, 1


def sections(body):
    """{heading in lower case: [lines]} for a markdown text."""
    found, current = {}, None
    for line in body.splitlines():
        match = HEADING.match(line)
        if match:
            current = match.group(1).strip().lower()
            found.setdefault(current, [])
        elif current is not None:
            found[current].append(line)
    return found


def done_items(body):
    return [m.group(1) for m in (ITEM.match(line) for line in sections(body).get("done when", [])) if m]


def split_list(value):
    return [item.strip() for item in re.split(r"[,;]", value or "") if item.strip()]


def read_dispatch(path):
    """The dispatch plan as a dict; raises ValueError when unreadable or not this format."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("unreadable dispatch plan: %s" % exc)
    if not isinstance(data, dict) or data.get("format") != DISPATCH_FORMAT:
        raise ValueError("not a dispatch plan: format must be " + DISPATCH_FORMAT)
    if not isinstance(data.get("workers"), list) or not all(isinstance(w, dict) for w in data["workers"]):
        raise ValueError("workers must be a list of objects")
    return data


def report_of(command, findings, notes, **extra):
    status = extra.pop("status", None) or ("findings" if findings else "clean")
    out = {"format": FORMAT, "command": command, "status": status, "findings": findings, "notes": notes, "note": NOTE}
    out.update(extra)
    return out


def unreadable(command, error):
    return report_of(command, [], [], status="unreadable", error=str(error))


# ---- plan ---------------------------------------------------------------------------------------------------------
def check_header(wid, header, held, tiers, findings, root):
    """Findings for one brief's header; `tiers` is the contract's list, or None without the core."""
    for key in REQUIRED:
        if key not in header or (not header[key] and key != "writes"):
            findings.append(finding("field-missing", wid, "the brief header has no " + key))
    if header.get("worker") and header["worker"] != wid:
        findings.append(finding("id-mismatch", wid, "the brief names worker " + header["worker"]))
    if tiers is not None:
        if header.get("tier") and header["tier"] not in tiers:
            findings.append(finding("bad-tier", wid, header["tier"] + " is not one of " + ", ".join(tiers)))
    if header.get("wait") and header["wait"] not in WAITS:
        findings.append(finding("bad-wait", wid, header["wait"] + " is not report or handle"))
    if header.get("cap") and not CAP.search(header["cap"]):
        findings.append(finding("bad-cap", wid, "the cap needs a number and a unit (turns, minutes, hours, calls)"))
    tools, removed = split_list(header.get("tools")), {t.lower() for t in split_list(header.get("removed"))}
    for tool in tools:
        if tool.lower() not in held:
            findings.append(finding("tool-not-held", wid, tool + " is not among the coordinator's tools"))
        if tool.lower() in removed:
            findings.append(finding("tool-conflict", wid, tool + " is both listed and removed"))
    times = {}
    for key in ("start_by", "deadline_at"):
        if header.get(key):
            try:
                parsed = dt.datetime.fromisoformat(header[key].replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is None or parsed.tzinfo is None:
                findings.append(finding("clock-format", wid, key + " needs an absolute time with a timezone"))
            else:
                times[key] = parsed
    if len(times) == 2 and times["deadline_at"] <= times["start_by"]:
        findings.append(finding("clock-order", wid, "deadline_at is not after start_by"))
    for entry in (e.strip() for e in (header.get("inputs") or "").split(";") if e.strip()):
        parts = entry.split()
        path = norm(parts[0])
        if len(parts) < 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[1]):
            findings.append(finding("input-unhashed", wid, entry + ": give the input's SHA-256"))
            continue
        source, expected = inside(root, path), parts[1]
        if source is None or not source.is_file():
            findings.append(finding("input-missing", wid, parts[0] + " is not there"))
        elif digest(source) != expected:
            findings.append(finding("input-changed", wid, parts[0] + " no longer has the stated SHA-256"))


def check_text(wid, raw, body, findings):
    for number, line in enumerate(raw.splitlines(), start=1):
        for match in PLACEHOLDER.finditer(line):
            findings.append(finding("placeholder", wid, "line %d: %s" % (number, match.group(0))))
    for line in sections(body).get("done when", []):
        match = ITEM.match(line)
        if match and not SOURCED.search(line):
            findings.append(finding("unsourced-requirement", wid, "%s names no source: end the item with (source: user "
                                    "<their words>), (source: plan <step>) or (source: rule <file>), on its own line"
                                    % match.group(1)))
    items = done_items(body)
    if not items:
        findings.append(finding("no-done-when", wid,
                                "the brief has no '## Done when' list with item ids (- D1: ...)"))
    for item in sorted({i for i in items if items.count(i) > 1}):
        findings.append(finding("duplicate-item", wid, item + " appears more than once"))
    if "END-OF-REPORT " + wid not in body:
        findings.append(finding("no-end-marker", wid, "the brief does not tell the worker to end with END-OF-REPORT " + wid))


def write_sets(workers, briefs, runs, findings):
    """{worker id: [scopes]} for the overlap check; each worker always writes its own folder."""
    sets = {}
    for worker in workers:
        wid = worker["id"]
        header = briefs.get(wid)
        mine = [runs + "/" + wid if runs else wid]
        if header is not None and "writes" in header:
            value = header["writes"]
            if not value.strip():
                findings.append(finding("writes-undeclared", wid, "writes is empty: say none or name the paths"))
            elif value.strip().lower() != "none":
                for raw in split_list(value):
                    path = norm(raw)
                    if path is None:
                        findings.append(finding("writes-not-portable", wid, raw + " is not a relative path inside the tree"))
                    else:
                        mine.append(scope(path))
        sets[wid] = mine
    return sets


def check_plan(path, repo=None, core=None):
    try:
        data = read_dispatch(path)
    except ValueError as exc:
        return unreadable("plan", exc)
    root = pathlib.Path(repo) if repo else pathlib.Path(path).resolve().parent
    record = load_core(core)
    findings, notes = [], []
    if record is None:
        notes.append("core not found: tier and worker ids were not checked against the contract")
    mode = data.get("mode")
    if mode not in MODES:
        findings.append(finding("field-missing", None, "mode must be workers or inline"))
    if not text(data.get("why")):
        findings.append(finding("no-reason", None, "why is empty: say what the user asked, or why it runs inline"))
    if mode == "workers" and not text(data.get("fan_out")):
        findings.append(finding("no-reason", None, "fan_out is empty: say which fan-out condition holds"))
    held = {t.lower() for t in (data.get("coordinator") or {}).get("tools", []) if isinstance(t, str)}
    if mode == "workers" and not held:
        findings.append(finding("field-missing", None, "coordinator.tools is empty"))
    workers = data["workers"]
    started = sum(1 for w in workers if w.get("ran") != "inline")
    if mode == "inline" and started:
        findings.append(finding("mode-mismatch", None, "mode is inline but %d worker(s) are not marked ran: inline" % started))
    if mode == "workers" and not workers:
        findings.append(finding("no-workers", None, "mode is workers but no worker is listed"))
    limit = data.get("max_workers", DEFAULT_CAP)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        findings.append(finding("field-missing", None, "max_workers must be a positive whole number"))
        limit = DEFAULT_CAP
    if limit > DEFAULT_CAP and not text(data.get("cap_reason")):
        findings.append(finding("cap-without-reason", None, "max_workers above %d needs cap_reason" % DEFAULT_CAP))
    if started > limit:
        findings.append(finding("too-many-workers", None, "%d workers for a cap of %d: queue or batch the rest" % (started, limit)))
    if "budget" in data:
        budget = data["budget"]
        if not isinstance(budget, dict) or not text(budget.get("checks")):
            findings.append(finding("budget-checks", None, "a budget names the checking it reserves first (budget.checks)"))
    plan = data.get("plan")
    expected = None
    if plan is not None:
        if not isinstance(plan, dict) or not text(plan.get("path")) or not re.fullmatch(r"[0-9a-f]{64}", str(plan.get("sha256"))):
            findings.append(finding("plan-stamp", None, "plan needs a path and a SHA-256"))
        else:
            expected = plan["path"] + " " + plan["sha256"]
            target = inside(root, plan["path"])
            if target is None or not target.is_file() or digest(target) != plan["sha256"]:
                findings.append(finding("plan-moved", None, plan["path"] + " is missing or no longer has the stated SHA-256"))
    ids = [w.get("id") for w in workers]
    pattern = record.CONTRACT["$defs"]["delegate"]["properties"]["id"] if record else None
    tier_values = tiers(record) if record else None
    briefs = {}
    for worker in workers:
        wid = worker.get("id")
        if not text(wid):
            findings.append(finding("bad-id", None, "a worker has no id"))
            continue
        if ids.count(wid) > 1:
            findings.append(finding("duplicate-id", wid, wid + " is listed more than once"))
        if re.search(r"[\\/]", wid) or wid in (".", "..") or (pattern is not None and record.shape(wid, pattern)):
            findings.append(finding("bad-id", wid, "a worker id is a plain name (it names the ledger entry and the folder)"))
        if worker.get("ran") == "inline":
            continue
        brief = inside(root, worker.get("brief"))
        try:
            raw = brief.read_text(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            findings.append(finding("brief-unreadable", wid, str(worker.get("brief")) + " cannot be read"))
            continue
        header, body, _ = parse_brief(raw)
        if header is None:
            findings.append(finding("field-missing", wid, "the brief has no header block (--- ... ---)"))
            header = {}
        briefs[wid] = header
        check_header(wid, header, held, tier_values, findings, root)
        check_text(wid, raw, body, findings)
        if expected is not None:
            stamp = " ".join(header.get("plan", "").split())
            if stamp != expected:
                findings.append(finding("plan-stamp", wid, "the brief's plan stamp differs from the dispatch plan's"))
    runs = norm(str(data.get("runs", "runs"))) or ""
    sets = write_sets([w for w in workers if text(w.get("id")) and w.get("ran") != "inline"], briefs, runs, findings)
    names = sorted(sets)
    for index, wid in enumerate(names):
        for other in names[index + 1:]:
            for mine in sets[wid]:
                for theirs in sets[other]:
                    if overlaps(mine, theirs):
                        findings.append(finding("writes-overlap", other, "%s (%s) overlaps %s (%s)" % (
                            other, theirs or ".", wid, mine or ".")))
    return report_of("plan", findings, notes, workers=len(workers))


# ---- collect ------------------------------------------------------------------------------------------------------
def allowed_file(path, folder):
    """A returned file is named, inside the worker's folder, not hidden and not credential-like."""
    clean = norm(path)
    if clean is None or any(c in path for c in "*?[") or not clean.startswith(folder + "/"):
        return False
    parts = clean.split("/")
    name = parts[-1].lower()
    if any(p.startswith(".") for p in parts) or name in CREDENTIAL_NAMES or name.endswith(CREDENTIAL_SUFFIXES):
        return False
    return "secret" not in name


def judge(worker, header, raw, root, folder):
    """(state, problems, items) for one return, read against its brief's header, done-when ids and the plan hash."""
    wid = worker["id"]
    problems, rejected, stale = [], False, False
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    marker = "END-OF-REPORT " + wid
    if not lines or lines[-1] != marker:
        problems.append(finding("no-end-marker", wid, "the last line is not " + marker))
    parts = sections(raw)
    answers = {}
    for line in parts.get("done when", []):
        match = ANSWER.match(line)
        if match:
            answers[match.group(1)] = (match.group(2).lower(), match.group(3).strip())
    missing_items = [i for i in header.get("_items", []) if i not in answers]
    for item in missing_items:
        problems.append(finding("unanswered-item", wid, item + " is not answered done, not done or could not"))
    for item, (answer, reason) in sorted(answers.items()):
        if answer == "could not" and not reason:
            problems.append(finding("no-reason", wid, item + ": a could not needs its reason"))
    listed = []
    for line in parts.get("files", []):
        match = FILE_LINE.match(line)
        if not match:
            continue
        path, expected_hash = match.group(1), match.group(2)
        listed.append(path)
        if not allowed_file(path, folder):
            problems.append(finding("file-not-allowed", wid, path + " is outside the worker's folder, hidden, globbed or credential-like"))
            rejected = True
            continue
        target = inside(root, path)
        if expected_hash is None:
            problems.append(finding("file-unhashed", wid, path + " has no SHA-256"))
        elif target is None or not target.is_file():
            problems.append(finding("file-missing", wid, path + " is not there"))
        else:
            expected = expected_hash
            if digest(target) != expected:
                problems.append(finding("file-hash", wid, path + " does not have the stated SHA-256"))
                rejected = True
    writes = (header.get("writes") or "").strip().lower()
    if writes and writes != "none" and not listed and not COMMIT.search(raw):
        problems.append(finding("no-artifact", wid, "a writer names no artifact (a file with its hash, or a commit)"))
    kind = (header.get("kind") or "").strip().lower()
    headings = list(parts)
    if kind == "search" and not all(
            any(re.fullmatch(name, h) for h in headings) for name in SEARCH_LISTS):
        problems.append(finding("search-lists", wid, "a search return lists found, searched with nothing found, and not searched"))
    plan_hash = header.get("_plan")
    if plan_hash:
        match = ECHO.search(raw)
        if not match:
            problems.append(finding("no-plan-echo", wid, "the report does not echo the plan's path and SHA-256"))
        else:
            echoed = match.group(2)
            expected = plan_hash
            if echoed != expected:
                problems.append(finding("stale", wid, "built on plan hash " + echoed[:12] + "..., not the current one"))
                stale = True
    state = "rejected" if rejected else "stale" if stale else "partial" if problems else "complete"
    return state, problems, {item: answer for item, (answer, _) in sorted(answers.items())}


def receipts_for(record, task, wid):
    return sorted(e["id"] for e in task.get("evidence", []) if e.get("status") == "passed"
                  and record.supports(e, wid) and record.same_content(e, task))


def collect(path, record=None, repo=None, core=None):
    try:
        data = read_dispatch(path)
    except ValueError as exc:
        return unreadable("collect", exc)
    root = pathlib.Path(repo) if repo else pathlib.Path(path).resolve().parent
    runs = norm(str(data.get("runs", "runs"))) or ""
    workers = [w for w in data["workers"] if text(w.get("id"))]
    findings, notes = [], []
    missing = [w["id"] for w in workers if w.get("ran") != "inline" and not text(w.get("handle"))]
    if missing:
        findings = [finding("missing-handle", wid, "no start handle recorded: build only on the full set") for wid in missing]
        return report_of("collect", findings, notes, status="refused", workers={}, batch="refused",
                         returned=[], in_flight=[])
    core_module, task = None, None
    if record is not None:
        core_module = load_core(core)
        try:
            task = json.loads(pathlib.Path(record).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return unreadable("collect", "unreadable task record: %s" % exc)
        if core_module is None:
            notes.append("core not found: no return can be settled from the record")
    expected_plan = (data.get("plan") or {}).get("sha256") if isinstance(data.get("plan"), dict) else None
    returned, in_flight = [], []
    for worker in workers:
        wid = worker["id"]
        if worker.get("ran") == "inline":
            continue
        if (root / runs / wid / "report.md").is_file():
            returned.append(wid)
        else:
            in_flight.append(wid)
    states, results = [], {}
    for worker in workers:
        wid = worker["id"]
        if worker.get("ran") == "inline":
            results[wid] = {"state": "inline", "claim": "coordinator did it itself"}
            continue
        folder = (runs + "/" + wid) if runs else wid
        if wid not in returned:
            results[wid] = {"state": "missing", "claim": None}
            findings.append(finding("missing", wid, folder + "/report.md is not there"))
            states.append("missing")
            continue
        try:
            raw = (root / folder / "report.md").read_text(encoding="utf-8")
        except (OSError, ValueError):
            raw = ""
        header, unknown = {}, False
        try:
            brief_raw = inside(root, worker.get("brief")).read_text(encoding="utf-8")
            header, body, _ = parse_brief(brief_raw)
            header = dict(header or {})
            header["_items"] = done_items(body)
        except (AttributeError, OSError, ValueError):
            findings.append(finding("brief-unreadable", wid, "its brief cannot be read, so its checklist is unknown"))
            unknown = True
        if expected_plan:
            header["_plan"] = expected_plan
        state, problems, items = judge(worker, header, raw, root, folder)
        if unknown and state == "complete":
            state = "partial"  # a return checked against no checklist is not whole
        findings.extend(problems)
        entry = {"state": state, "claim": None, "items": items, "report_sha256": digest(root / folder / "report.md")}
        if state == "complete":
            receipts = receipts_for(core_module, task, wid) if core_module is not None and task is not None else []
            claim = "settled" if receipts else "model-reported"
            entry.update(claim=claim, receipts=receipts)
            states.append(claim)
        else:
            states.append(state)
        results[wid] = entry
    batch = "inconclusive" if not states else min(states, key=ORDER.index)
    if batch == "inconclusive":
        findings.append(finding("empty-batch", None, "no worker returns to judge: inconclusive, never complete"))
    status = "clean" if batch in ("model-reported", "settled") else "findings"
    return report_of("collect", findings, notes, status=status, workers=results, batch=batch,
                     returned=returned, in_flight=in_flight)


# ---- ledger -------------------------------------------------------------------------------------------------------
def check_ledger(path, dispatch=None, core=None):
    record = load_core(core)
    if record is None or not hasattr(record, "check_delegates"):
        return report_of("ledger", [], ["the westack core (record.py with check_delegates) was not found: the ledger "
                                        "was not checked"], status="not-run")
    try:
        task = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return unreadable("ledger", "unreadable task record: %s" % exc)
    findings, notes = [], []
    shape = record.shape(task, record.CONTRACT["root"])
    if shape:
        findings = [finding("contract-shape", None, problem) for problem in shape[:10]]
        return report_of("ledger", findings, notes)
    for message in record.check_delegates(task, True):
        findings.append(finding("ledger", message.split(":", 1)[0], message))
    for entry in task.get("delegates", []):
        if entry["parent"] != task["id"]:
            findings.append(finding("nested-worker", entry["id"], "its parent is " + entry["parent"]
                                    + ", not the task: workers start no workers (depth one)"))
    waiting = task.get("waiting_on")
    if waiting and HOLD_WORD.match(waiting["what"]):
        findings.append(finding("held", None, "a user's hold stands (%s): resume starts nothing; a CI result, a new clue "
                                "or a bot comment never lifts it, only the user's own word does, and the next record "
                                "then drops waiting_on" % waiting["what"]))
        if waiting["check"]["kind"] != "person-confirms":
            findings.append(finding("hold-event-check", None, "the hold's check is %s, which an event could satisfy: a "
                                    "hold uses person-confirms" % waiting["check"]["kind"]))
        if not HOLD.match(waiting["what"]):
            findings.append(finding("hold-incomplete", None, "write the hold as 'hold: pause by user: <why>' (or stop): "
                                    "who held the run and why"))
    elif waiting:
        findings.append(finding("still-waiting", None, "the run still waits on " + waiting["what"]))
    if dispatch is not None:
        try:
            data = read_dispatch(dispatch)
        except ValueError as exc:
            return unreadable("ledger", exc)
        recorded = {entry["id"] for entry in task.get("delegates", [])}
        for worker in data["workers"]:
            if worker.get("ran") != "inline" and text(worker.get("id")) and worker["id"] not in recorded:
                findings.append(finding("no-ledger-entry", worker["id"], "dispatched but has no delegates entry"))
    if not task.get("delegates"):
        notes.append("the record has no delegates: nothing was delegated, or nothing was recorded")
    return report_of("ledger", findings, notes)


# ---- command line -------------------------------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="check a dispatch plan and its briefs before any worker starts")
    plan.add_argument("dispatch")
    gather = sub.add_parser("collect", help="check the workers' returns")
    gather.add_argument("dispatch")
    gather.add_argument("--record", help="the task record whose receipts can settle a return")
    ledger = sub.add_parser("ledger", help="check the delegation ledger in a task record")
    ledger.add_argument("task")
    ledger.add_argument("--dispatch", help="the dispatch plan whose workers must each have an entry")
    for command in (plan, gather):
        command.add_argument("--repo", help="the folder paths are relative to (default: the dispatch plan's folder)")
    for command in (plan, gather, ledger):
        command.add_argument("--core", help="the westack core folder (default: ../westack beside this skill)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    if args.command == "plan":
        report = check_plan(args.dispatch, repo=args.repo, core=args.core)
    elif args.command == "collect":
        report = collect(args.dispatch, record=args.record, repo=args.repo, core=args.core)
    else:
        report = check_ledger(args.task, dispatch=args.dispatch, core=args.core)
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return {"clean": 0, "findings": 1, "refused": 1}.get(report["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
