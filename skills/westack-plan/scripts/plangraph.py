"""westack-plan plan-graph checker: read a plan and report what would make it unsafe to build from.

  python plangraph.py PLAN [--previous OLD_PLAN] [--core CORE_DIR]

PLAN is a markdown plan in this skill's format (references/living.md) or a westack task record (.json), which is
read through the core's record.py and contract (the core is found beside this skill, or at --core). OLD_PLAN is an
earlier version of the same plan, to check that slice and requirement identities survived the re-plan.

  errors    duplicate-id, missing-dependency, cycle, milestone-order, unknown-milestone, no-acceptance,
            acceptance-without-id, acceptance-without-kind, no-rollback, bad-status, unknown-requirement,
            uncovered-requirement, done-without-receipt, receipt-unknown-acceptance, approved-with-open-decision,
            retry-of-unreceipted (a `Retry of: S2` slice, or a unit's retry_of, cites a slice not done with receipts:
            that slice was never done, so it keeps its id and its status is set back),
            fixed-output (an automated criterion's command prints fixed text or masks its own failure, so it cannot
            fail: `echo ok`, `pytest; true`), contract-shape (task records)
  warnings  automated-without-command, weak-expectation (`grep -q ok`), path-as-regex (a path searched as a pattern),
            no-paths, done-before-dependency, overlapping-paths (two unfinished
            slices that no dependency orders claim overlapping paths: fix the plan before dispatch, do not merge
            afterwards; a path may carry its operation, `src/a.py (replace)`), and with --previous: removed-slice,
            retitled-slice, reopened-slice, removed-requirement, previous-unreadable
  graph     order (a dependency order, null on a cycle); done (status done and a receipt reference for every
            criterion, a `human:` one for a human criterion; in a task record, every criterion passed with
            evidence); claimed_done (status done without that); ready (planned, every dependency done); waiting;
            in_progress; blocked; open_decisions

It checks the plan's structure and its receipt references, not their truth: a reference points at evidence for
westack-verify or the core validator to check, and a status line, checkbox or closed ticket is never one. The gate
lint reads only the first backticked span of an automated criterion as text; it is a cheap pre-check for a command
that cannot fail and never replaces a broken-copy run.
Exit 0 clean (warnings allowed), 1 findings, 2 unreadable or no slices, 64 usage. Standard library only; it reads
the files named and prints JSON; it runs no command, writes no file and opens no network connection.
"""
import argparse
import fnmatch
import hashlib
import importlib.util
import json
import pathlib
import re
import shlex
import sys

FORMAT = "westack-plan-graph-1"
NOTE = ("Checks the plan's structure and its receipt references, not their truth. A reference points at evidence "
        "for westack-verify or the core validator to check; a status line, checkbox or closed ticket is never a receipt.")
STATUSES = ("planned", "active", "done", "blocked")  # the core contract's work_unit enum; read from it when present
EMPTY = {"", "none", "n/a", "na", "-", "tbd", "todo", "?", "none yet"}
INACTIVE = re.compile(r"\b(?:withdrawn|parked|deferred|superseded|dropped|out of scope)\b", re.I)
SECTION = re.compile(r"^##\s+(.+?)\s*$")
SLICE = re.compile(r"^###\s+([A-Za-z][\w.-]*)\s*(?::|—|–)\s*(.*?)\s*$")
FIELD = re.compile(r"^[-*]\s+([A-Za-z][A-Za-z ]*?)\s*:\s*(.*?)\s*$")
SUBITEM = re.compile(r"^(?:\s{2,}|\t+)[-*]\s+(.*?)\s*$")
ITEM = re.compile(r"^([A-Za-z][\w.-]*)\s*(?:\(([^)]*)\))?\s*[:=]\s*(.*?)\s*$")
REQUIREMENT = re.compile(r"^[-*]\s+([A-Za-z][\w.-]*)\s*(?:\(([^)]*)\))?\s*:\s*(.*?)\s*$")
DECISION = re.compile(r"^[-*]\s+([A-Za-z][\w.-]*)\s*\[([^\]]*)\]\s*:\s*(.*?)\s*$")
PLAN_STATUS = re.compile(r"^plan status\s*:\s*(.*?)\s*$", re.I)
TOKEN = re.compile(r"[A-Za-z][\w.-]*")
KINDS = {"automated": "automated", "agent": "automated", "auto": "automated",
         "human": "human", "human-only": "human", "manual": "human"}
LIST_FIELDS = {"depends on": "depends", "delivers": "delivers", "paths": "paths", "consumers": "consumers"}
SPAN = re.compile(r"`([^`]+)`")
FIXED = {"echo", "printf", "true", ":"}  # print fixed text or always succeed
FIXED_PROGRAM = re.compile(r"^\s*(?:print|console\.log)\s*\(\s*(?:'[^']*'|\"[^\"]*\")?\s*\)\s*;?\s*$")
INLINE = {"python": "-c", "python3": "-c", "py": "-c", "node": "-e", "nodejs": "-e"}
SEARCH = {"grep", "egrep", "fgrep", "rg", "ag", "ack"}
WEAK = {"ok", "okay", "pass", "passed", "success", "done", "true", "yes", "works", "fine"}
RETRY = re.compile(r"\bretry of\s*:?\s*([A-Za-z][\w.-]*)", re.I)
PATHLIKE = re.compile(r"^[\w.-]+(?:/[\w.-]+)+\.\w{1,5}$|^[\w-]+\.(?:py|js|ts|md|json|toml|ya?ml|txt|cfg)$")


def load_core(core=None):
    """The core's record.py module, or None when no core is found."""
    base = pathlib.Path(core) if core else pathlib.Path(__file__).resolve().parents[2] / "westack"
    path = base / "scripts" / "record.py"
    if not path.is_file():
        return None
    key = "westack_plan_record_" + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
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


def statuses(record):
    if record is None:
        return STATUSES
    return tuple(record.CONTRACT["$defs"]["work_unit"]["properties"]["status"]["enum"])


def empty(value):
    return value.strip().strip(".").lower() in EMPTY


def ids(values):
    found = []
    for value in values:
        match = TOKEN.match(value.strip())
        if match and not empty(value):
            found.append(match.group(0))
    return found


def split_list(value):
    return [] if empty(value) else [part.strip() for part in value.split(",") if part.strip()]


def new_slice(sid, title, line):
    return {"id": sid, "title": title, "line": line, "milestone": None, "depends": [], "delivers": [], "paths": [],
            "consumers": [], "acceptance": [], "rollback": None, "status": "planned", "receipts": {},
            "retry_of": RETRY.search(title).group(1) if RETRY.search(title) else None}


def receipt_pairs(value):
    pairs = []
    for part in value.split(";"):
        match = ITEM.match(part.strip())
        if match:
            pairs.append((match.group(1), match.group(3).strip()))
    return pairs


def parse_markdown(text):
    plan = {"kind": "markdown", "slices": [], "requirements": None, "milestones": None, "decisions": [],
            "plan_status": None, "problems": []}
    section, current, field = None, None, None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        status = PLAN_STATUS.match(line)
        if status and plan["plan_status"] is None and section is None:
            plan["plan_status"] = status.group(1)
            continue
        heading = SECTION.match(line)
        if heading and not line.startswith("###"):
            section, current, field = heading.group(1).strip().lower(), None, None
            if section == "requirements":
                plan["requirements"] = plan["requirements"] or []
            elif section == "milestones":
                plan["milestones"] = plan["milestones"] or []
            continue
        if section == "requirements":
            match = REQUIREMENT.match(line)
            if match:
                plan["requirements"].append({"id": match.group(1), "active": not INACTIVE.search(match.group(2) or ""),
                                             "line": number})
        elif section == "milestones":
            match = REQUIREMENT.match(line)
            if match:
                plan["milestones"].append({"id": match.group(1), "title": match.group(3), "line": number})
        elif section == "decisions":
            match = DECISION.match(line)
            if match:
                tags = [t.strip().lower() for t in match.group(2).split(",")]
                plan["decisions"].append({"id": match.group(1), "tags": tags, "open": "open" in tags, "line": number})
        elif section == "slices":
            heading = SLICE.match(line)
            if heading:
                current, field = new_slice(heading.group(1), heading.group(2), number), None
                plan["slices"].append(current)
                continue
            if current is None:
                continue
            sub = SUBITEM.match(raw)
            if sub and field:
                add_subitem(current, field, sub.group(1), number, plan)
                continue
            match = FIELD.match(line)
            if match:
                field = add_field(current, match.group(1).strip().lower(), match.group(2), number, plan)
    return plan


def add_field(current, key, value, number, plan):
    if key in LIST_FIELDS:
        current[LIST_FIELDS[key]].extend(split_list(value))
        return key
    if key == "milestone":
        current["milestone"] = None if empty(value) else ids([value])[0] if ids([value]) else None
    elif key == "rollback":
        current["rollback"] = None if empty(value) else value
    elif key == "status":
        current["status"] = value.strip().lower() or "planned"
    elif key == "retry of" and ids([value]):
        current["retry_of"] = ids([value])[0]
    elif key == "receipts":
        for aid, ref in ([] if empty(value) else receipt_pairs(value)):
            current["receipts"][aid] = ref
    elif key == "acceptance" and not empty(value):
        add_subitem(current, key, value, number, plan)
    return key


def add_subitem(current, field, text, number, plan):
    if field in LIST_FIELDS:
        current[LIST_FIELDS[field]].extend(split_list(text))
    elif field == "acceptance":
        match = ITEM.match(text)
        if not match:
            current["acceptance"].append({"id": None, "kind": None, "text": text, "line": number})
            return
        kind = KINDS.get((match.group(2) or "").strip().lower())
        current["acceptance"].append({"id": match.group(1), "kind": kind, "text": match.group(3), "line": number,
                                      "command": "`" in match.group(3)})
    elif field == "receipts":
        for aid, ref in receipt_pairs(text):
            current["receipts"][aid] = ref


def parse_record(text, record):
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("work_units"), list):
        raise ValueError("not a westack task record: no work_units list")
    plan = {"kind": "task-record", "slices": [], "requirements": None, "milestones": None, "decisions": [],
            "plan_status": None, "problems": []}
    for problem in record.shape(data, record.CONTRACT["root"])[:10]:
        plan["problems"].append({"code": "contract-shape", "detail": problem + " (run the core validate.py task for the full check)"})
    criteria = {c.get("id"): c for c in data.get("acceptance", []) if isinstance(c, dict)}
    for unit in data["work_units"]:
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str):
            continue
        item = new_slice(unit["id"], str(unit.get("goal", "")), None)
        item.update(depends=[d for d in unit.get("depends_on") or [] if isinstance(d, str)],
                    paths=list(unit.get("allowed_paths") or []), status=str(unit.get("status", "planned")),
                    rollback=unit.get("rollback") if isinstance(unit.get("rollback"), str) and not empty(unit["rollback"]) else None,
                    retry_of=unit.get("retry_of") if isinstance(unit.get("retry_of"), str) else None)
        for aid in unit.get("acceptance_ids") or []:
            criterion = criteria.get(aid, {})
            kind = "human" if criterion.get("verifier") == "human" else "automated"
            item["acceptance"].append({"id": aid, "kind": kind, "text": criterion.get("claim", ""), "command": True})
            if criterion.get("status") == "passed" and criterion.get("evidence_ids"):
                item["receipts"][aid] = ("human: " if kind == "human" else "") + ", ".join(criterion["evidence_ids"])
        plan["slices"].append(item)
    return plan


def read_plan(path, record):
    raw = pathlib.Path(path).read_bytes()
    text = raw.decode("utf-8-sig")
    if pathlib.Path(path).suffix.lower() == ".json":
        if record is None:
            raise ValueError("a task record is read through the westack core (record.py); none was found")
        return parse_record(text, record), raw
    return parse_markdown(text), raw


def components(nodes, edges):
    """Strongly connected components (Tarjan) of the dependency graph, in node order."""
    index, low, stack, on, found, counter = {}, {}, [], set(), [], [0]

    def visit(node):
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on.add(node)
        for nxt in edges[node]:
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            group = []
            while True:
                member = stack.pop()
                on.discard(member)
                group.append(member)
                if member == node:
                    break
            found.append(group)
    for node in nodes:
        if node not in index:
            visit(node)
    return found


def topological(nodes, edges):
    """A dependency order (dependencies first, ties in plan order), or None when the graph has a cycle."""
    remaining = {n: {d for d in edges[n]} for n in nodes}
    order = []
    while remaining:
        free = [n for n in nodes if n in remaining and not remaining[n]]
        if not free:
            return None
        node = free[0]
        order.append(node)
        del remaining[node]
        for deps in remaining.values():
            deps.discard(node)
    return order


def command_parts(command):
    """[(argv, connector before it)] for one shell line, or None when it cannot be split."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    parts, argv, joiner = [], [], ""
    for token in tokens:
        if set(token) <= set("&|;()"):
            if argv:
                parts.append((argv, joiner))
            argv, joiner = [], token
        else:
            argv.append(token)
    if argv:
        parts.append((argv, joiner))
    return parts


def prints_fixed(argv):
    """True for a command whose result does not depend on the code under test: echo, printf, true, `exit 0`, or an
    inline program that only prints a literal."""
    head = argv[0]
    if head in FIXED:
        return True
    if head == "exit":
        return argv[1:] == ["0"]
    flag = INLINE.get(head)
    return bool(flag and flag in argv[1:-1] and FIXED_PROGRAM.match(argv[argv.index(flag) + 1]))


def cannot_fail(parts):
    """The exit status is fixed: every part prints fixed text, a fixed command feeds a pipeline, or the last part
    (after `;`, `||` or `|`) is fixed and so masks whatever came before. `a && echo ok` can still fail."""
    if all(prints_fixed(argv) for argv, _ in parts):
        return True
    if prints_fixed(parts[0][0]) and all(joiner == "|" for _, joiner in parts[1:]):
        return True
    last, joiner = parts[-1]
    return prints_fixed(last) and joiner in (";", "||", "|")


def gate_problems(text):
    """[(code, level, detail)] for the command of an automated criterion (its first backticked span): fixed-output
    (an error: the gate cannot fail), weak-expectation and path-as-regex (warnings). A heuristic read of text."""
    span = SPAN.search(text or "")
    parts = command_parts(span.group(1).strip()) if span else None
    if not parts or sum(len(argv) for argv, _ in parts) < 2:  # a lone word such as `printf` is prose, not a command
        return []
    command = span.group(1).strip()
    if cannot_fail(parts):
        return [("fixed-output", "error", "`" + command + "` cannot fail: it prints fixed text or masks its own "
                 "failure; name a command whose result depends on the code under test")]
    found = []
    for argv, _ in parts:
        if argv[0] not in SEARCH:
            continue
        pattern = next((a for a in argv[1:] if not a.startswith("-")), "")
        if pattern.lower() in WEAK:
            found.append(("weak-expectation", "warning", "`" + command + "` looks for a word any output may contain; "
                          "name the specific line, name or count it must show"))
        elif PATHLIKE.match(pattern) and not any(a == "--fixed-strings" or (a[:1] == "-" and a[1:2] != "-" and "F" in a)
                                                 for a in argv[1:]):
            found.append(("path-as-regex", "warning", "`" + command + "` searches a path as a pattern, so its dots "
                          "match any character; use a fixed-string search or test the file directly"))
    return found


def receipt_problem(item):
    """Why a slice whose status is done is only claimed done, or None when every criterion has its reference."""
    missing = []
    for criterion in item["acceptance"]:
        ref = item["receipts"].get(criterion["id"])
        if not ref or empty(ref):
            missing.append(criterion["id"] + " has no receipt")
        elif criterion["kind"] == "human" and not ref.strip().lower().startswith("human"):
            missing.append(criterion["id"] + " is human-only and needs a person's confirmation (human: who, when)")
    if not item["acceptance"]:
        missing.append("no acceptance criteria to receipt")
    return "; ".join(str(m) for m in missing) or None


OPERATION = re.compile(r"\s*\(([^()]*)\)\s*$")
GLOB = re.compile(r"[*?\[]")


def claim(text):
    """(normalised path, declared operation or None) for one Paths entry such as 'src/a.py (replace)'."""
    match = OPERATION.search(text)
    path = (text[:match.start()] if match else text).strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/"), (match.group(1).strip() or None) if match else None


def paths_overlap(a, b):
    """True when two normalised paths can name the same file: equal, one inside the other, or a glob reaching the other."""
    if a == b or not a or not b or "." in (a, b):  # an empty path or '.' is the whole repository
        return True
    if b.startswith(a + "/") or a.startswith(b + "/"):
        return True
    if any(GLOB.search(p) and fnmatch.fnmatchcase(o, p) for p, o in ((a, b), (b, a))):
        return True
    if GLOB.search(a) and GLOB.search(b):  # two patterns: overlap when their literal folders are nested
        folders = [GLOB.split(p, 1)[0].rsplit("/", 1)[0] if "/" in GLOB.split(p, 1)[0] else "" for p in (a, b)]
        return not all(folders) or folders[0] == folders[1] or any(
            x.startswith(y + "/") for x, y in (folders, folders[::-1]))
    return False


def first_overlap(left, right):
    """The first pair of Paths entries (one from each list) that overlap, as ((entry, path, operation), ...), or None."""
    for mine in left:
        for theirs in right:
            (pa, oa), (pb, ob) = claim(mine), claim(theirs)
            if paths_overlap(pa, pb):
                return (mine, pa, oa), (theirs, pb, ob)
    return None


def overlapping(first, nodes, edges):
    """overlapping-paths warnings: unfinished slices that no dependency orders, directly or through others, and that
    claim overlapping paths. Slices that are done, or that name no paths, are left out."""
    reach = {}

    def below(node):
        if node not in reach:
            reach[node] = set()  # a cycle is reported elsewhere; here it only has to terminate
            for dep in edges[node]:
                reach[node] = reach[node] | {dep} | below(dep)
        return reach[node]
    warnings = []
    live = [n for n in nodes if first[n]["status"] != "done" and first[n]["paths"]]
    for index, left in enumerate(live):
        for right in live[index + 1:]:
            if right in below(left) or left in below(right):
                continue
            found = first_overlap(first[left]["paths"], first[right]["paths"])
            if found:
                (mine, pa, oa), (theirs, pb, ob) = found
                ops = [who + " " + op for who, op in ((left, oa), (right, ob)) if op]
                warnings.append({"code": "overlapping-paths", "slice": left, "with": right, "paths": [mine, theirs],
                                 "detail": left + " and " + right + " are not ordered by a dependency and both claim "
                                 + (pa if pa == pb else pa + " and " + pb) + (" (" + "; ".join(ops) + ")" if ops else "")
                                 + ": narrow one, order them or merge them before dispatch"})
    return warnings


def analyse(plan, allowed):
    errors = list(plan["problems"])
    warnings = []
    slices = plan["slices"]
    first = {}
    for item in slices:
        if item["id"] in first:
            errors.append({"code": "duplicate-id", "slice": item["id"], "detail": "defined twice; ids must be unique"})
        else:
            first[item["id"]] = item
    nodes = list(first)
    edges = {n: [d for d in first[n]["depends"] if d in first] for n in nodes}
    for node in nodes:
        for dep in first[node]["depends"]:
            if dep not in first:
                errors.append({"code": "missing-dependency", "slice": node, "detail": "depends on " + dep + ", which no slice defines"})
    for group in components(nodes, edges):
        if len(group) > 1 or group[0] in edges[group[0]]:
            members = [n for n in nodes if n in group]
            errors.append({"code": "cycle", "members": members, "detail": " -> ".join(members + members[:1])})
    order = topological(nodes, edges)
    milestones = [m["id"] for m in plan["milestones"]] if plan["milestones"] is not None else []
    for node in nodes:
        item = first[node]
        if item["milestone"] and item["milestone"] not in milestones:
            errors.append({"code": "unknown-milestone", "slice": node, "detail": item["milestone"] + " is not under ## Milestones"})
        for dep in edges[node]:
            mine, theirs = item["milestone"], first[dep]["milestone"]
            if mine in milestones and theirs in milestones and milestones.index(theirs) > milestones.index(mine):
                errors.append({"code": "milestone-order", "slice": node,
                               "detail": "depends on " + dep + " in the later milestone " + theirs})
        if item["status"] not in allowed:
            errors.append({"code": "bad-status", "slice": node, "detail": item["status"] + " is not one of " + ", ".join(allowed)})
        if not item["acceptance"]:
            errors.append({"code": "no-acceptance", "slice": node, "detail": "no acceptance criterion a check or a person could fail"})
        known = set()
        for criterion in item["acceptance"]:
            if not criterion["id"]:
                errors.append({"code": "acceptance-without-id", "slice": node, "detail": criterion["text"]})
                continue
            known.add(criterion["id"])
            if criterion["kind"] is None:
                errors.append({"code": "acceptance-without-kind", "slice": node, "acceptance": criterion["id"],
                               "detail": "say (automated) or (human)"})
            elif criterion["kind"] == "automated" and not criterion.get("command"):
                warnings.append({"code": "automated-without-command", "slice": node, "acceptance": criterion["id"],
                                 "detail": "name the exact command in backticks and what it must show"})
            elif criterion["kind"] == "automated":
                for code, level, detail in gate_problems(criterion["text"]):
                    (errors if level == "error" else warnings).append(
                        {"code": code, "slice": node, "acceptance": criterion["id"], "detail": detail})
        if item["rollback"] is None:
            errors.append({"code": "no-rollback", "slice": node, "detail": "say how to undo this slice, in proportion to it"})
        if not item["paths"] and plan["kind"] == "markdown":
            warnings.append({"code": "no-paths", "slice": node, "detail": "name the paths the slice may touch"})
        for aid in item["receipts"]:
            if aid not in known:
                errors.append({"code": "receipt-unknown-acceptance", "slice": node, "acceptance": aid,
                               "detail": "a receipt for a criterion the slice does not define"})
    done, claimed = [], []
    for node in nodes:
        item = first[node]
        if item["status"] != "done":
            continue
        problem = receipt_problem(item)
        if problem:
            claimed.append(node)
            errors.append({"code": "done-without-receipt", "slice": node, "detail": problem})
        else:
            done.append(node)
    finished = set(done)
    for node in nodes:
        target = first[node]["retry_of"]
        if target and target in first and target not in finished:
            errors.append({"code": "retry-of-unreceipted", "slice": node, "retries": target,
                           "detail": target + " was never done with receipts, so it is not retried: set its status back "
                           "and keep its id. A retry slice is for one done with receipts whose check later failed"})
    for node in nodes:
        if first[node]["status"] == "done":
            late = [d for d in edges[node] if d not in finished]
            if late:
                warnings.append({"code": "done-before-dependency", "slice": node,
                                 "detail": "marked done while " + ", ".join(late) + " is not done"})
    warnings.extend(overlapping(first, nodes, edges))
    ready, waiting = [], {}
    for node in nodes:
        if first[node]["status"] != "planned":
            continue
        pending = [d for d in first[node]["depends"] if d not in finished]
        if pending:
            waiting[node] = pending
        else:
            ready.append(node)
    coverage = "not checked: the plan lists no requirements"
    if plan["requirements"] is not None:
        defined = {r["id"]: r for r in plan["requirements"]}
        delivered = {}
        for node in nodes:
            for rid in ids(first[node]["delivers"]):
                delivered.setdefault(rid, []).append(node)
                if rid not in defined:
                    errors.append({"code": "unknown-requirement", "slice": node, "requirement": rid,
                                   "detail": rid + " is not under ## Requirements"})
        for rid, requirement in defined.items():
            if requirement["active"] and rid not in delivered:
                errors.append({"code": "uncovered-requirement", "requirement": rid, "detail": "no slice delivers " + rid})
        coverage = "checked: every active requirement against the slices' Delivers lines"
    elif plan["kind"] == "task-record":
        coverage = "not checked: a task record does not link work units to requirements"
    open_decisions = [d["id"] for d in plan["decisions"] if d["open"]]
    approved = bool(plan["plan_status"]) and plan["plan_status"].strip().lower().startswith("approved")
    if approved:
        for decision in open_decisions:
            errors.append({"code": "approved-with-open-decision", "decision": decision,
                           "detail": "an approved plan leaves no decision open; settle it or record the accepted assumption"})
    return {"errors": errors, "warnings": warnings, "order": order, "done": done, "claimed_done": claimed,
            "ready": ready, "waiting": waiting, "in_progress": [n for n in nodes if first[n]["status"] == "active"],
            "blocked": [n for n in nodes if first[n]["status"] == "blocked"], "open_decisions": open_decisions,
            "coverage": coverage, "plan_status": plan["plan_status"], "approved": approved, "slices": len(slices),
            "requirements": len(plan["requirements"] or [])}


def compare(old, new, allowed):
    """Identity warnings between an earlier plan and this one."""
    warnings = []
    before = {s["id"]: s for s in old["slices"]}
    after = {s["id"]: s for s in new["slices"]}
    old_done = set(analyse(old, allowed)["done"])
    norm = lambda text: " ".join((text or "").lower().split())
    for sid, item in before.items():
        if sid not in after:
            if item["status"] != "done":
                warnings.append({"code": "removed-slice", "slice": sid,
                                 "detail": "an unfinished slice is gone; record why in the decision log"})
            continue
        if norm(item["title"]) != norm(after[sid]["title"]):
            warnings.append({"code": "retitled-slice", "slice": sid, "detail": repr(item["title"]) + " -> "
                             + repr(after[sid]["title"]) + "; an id keeps its meaning, so check nothing downstream "
                             "still points at the old one"})
        if sid in old_done and after[sid]["status"] != "done":
            warnings.append({"code": "reopened-slice", "slice": sid, "detail": "was done with receipts, now " + after[sid]["status"]})
    previous_requirements = {r["id"] for r in old["requirements"] or []}
    current_requirements = {r["id"] for r in new["requirements"] or []}
    for rid in sorted(previous_requirements - current_requirements):
        warnings.append({"code": "removed-requirement", "requirement": rid,
                         "detail": "mark a dropped requirement (withdrawn) instead of deleting it, so its history stays"})
    return warnings


def check_file(path, previous=None, core=None):
    record = load_core(core)
    allowed = statuses(record)
    report = {"format": FORMAT, "plan": str(path), "sha256": None, "kind": None,
              "contract": "core contract statuses" if record else "built-in statuses (core not found)", "note": NOTE}
    try:
        plan, raw = read_plan(path, record)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        report.update(status="unreadable", errors=[{"code": "unreadable", "detail": str(exc)}], warnings=[])
        return report
    report.update(sha256=hashlib.sha256(raw).hexdigest(), kind=plan["kind"])
    if not plan["slices"]:
        where = "no work_units" if plan["kind"] == "task-record" else "no '### <id>: <title>' slices under '## Slices'"
        report.update(status="unreadable", errors=[{"code": "no-slices", "detail": where}], warnings=[])
        return report
    report.update(analyse(plan, allowed))
    if previous:
        try:
            old, _ = read_plan(previous, record)
            report["warnings"].extend(compare(old, plan, allowed))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            report["warnings"].append({"code": "previous-unreadable", "detail": str(exc)})
    report["status"] = "findings" if report["errors"] else "clean"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("plan", help="a markdown plan or a westack task record (.json)")
    parser.add_argument("--previous", help="an earlier version of the same plan")
    parser.add_argument("--core", help="the westack core folder (default: ../westack beside this skill)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    report = check_file(args.plan, previous=args.previous, core=args.core)
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return {"clean": 0, "findings": 1}.get(report["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
