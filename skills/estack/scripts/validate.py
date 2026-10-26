"""Estack consistency checks. No task execution, permission grant or truth certification."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = json.loads((BASE / "contracts/contract.json").read_text(encoding="utf-8"))
RUNTIME = {"unit", "contract", "integration", "e2e", "host"}
LIMIT = 8 * 1024 * 1024


def digest(path):
    path = pathlib.Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("not a regular file: " + str(path))
    result = hashlib.sha256()
    # Evidence artifacts can be large; bound memory rather than artifact size.
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(128 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_json(path):
    path = pathlib.Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("not a regular file: " + str(path))
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def finite(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number: " + text)
        return value
    with path.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("JSON exceeds 8 MiB record limit")
    return json.loads(raw.decode("utf-8"),
                      object_pairs_hook=unique,
                      parse_float=finite,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + x)))


def shape(value, spec, where="$"):
    if "$ref" in spec:
        spec = CONTRACT["$defs"][spec["$ref"].split("/")[-1]]
    types = spec.get("type", [])
    types = [types] if isinstance(types, str) else types
    actual = ("null" if value is None else "boolean" if isinstance(value, bool)
              else "integer" if isinstance(value, int) else "object" if isinstance(value, dict)
              else "array" if isinstance(value, list) else "string" if isinstance(value, str)
              else "number" if isinstance(value, float) else "unknown")
    if actual not in types:
        return [where + ": expected " + "/".join(types)]
    if value is None:
        return []
    errors = []
    if "enum" in spec and value not in spec["enum"]:
        errors.append(where + ": value outside enum")
    if isinstance(value, str):
        if len(value) < spec.get("minLength", 0):
            errors.append(where + ": empty string")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            errors.append(where + ": pattern mismatch")
    if actual == "integer" and value < spec.get("minimum", value):
        errors.append(where + ": below minimum")
    if actual == "object":
        for key in spec.get("required", []):
            if key not in value:
                errors.append(where + ": missing " + key)
        for key in value:
            if key not in spec.get("properties", {}):
                errors.append(where + ": unknown key " + key)
            else:
                errors.extend(shape(value[key], spec["properties"][key], where + "." + key))
    if actual == "array":
        for i, item in enumerate(value):
            errors.extend(shape(item, spec["items"], where + "[" + str(i) + "]"))
    return errors


def safe_path(root, relative):
    # Diagnostic containment only; host enforcement must cover races and alternate tools.
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or pathlib.PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError("nonportable or escaping path: " + str(relative))
    root = pathlib.Path(root).resolve(strict=True)
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("resolved path escapes root: " + relative)
    return candidate


def scope_path(relative, allowed):
    if "\\" in relative or ":" in relative or relative.startswith("/"):
        return False
    if any(x in {"", ".", ".."} for x in relative.split("/")):
        return False
    return any(prefix == "." or relative == prefix or relative.startswith(prefix.rstrip("/") + "/")
               for prefix in allowed)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed


def freshness(record, revision=None, scope=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        if "target_version" in record:
            if record["target_version"] != record["observed_version"]:
                return "mismatch"
            if timestamp(record["retrieved_at"]) > now or timestamp(record["revalidate_after"]) <= now:
                return "stale"
            return "current"
        return ("stale" if record["revision"] != revision or record["scope_id"] != scope
                or timestamp(record["expires_at"]) <= now else "current")
    except (ValueError, KeyError):
        return "invalid"


def approval_matches(action, response, scope):
    return (action["decision"] == "pending" and action["scope_id"] == scope
            and all(response.get(k) == action[k]
                    for k in ("id", "target_hash", "occurrence", "scope_id", "kind", "target"))
            and response.get("decision") == "approved")


def reconcile(action, observed):
    if action["decision"] == "denied" or action["outcome"] == "denied":
        return "stop-denied"
    if action["outcome"] == "applied" or observed == "applied":
        return "do-not-replay"
    if action["outcome"] == "uncertain":
        return "refresh-authority-before-retry" if observed == "not-applied" else "inspect-without-replay"
    return "refresh-authority-before-retry"


def check_receipt(evidence, root):
    errors = []
    label = evidence["id"]
    if evidence["status"] in {"not-run", "blocked"}:
        if evidence["executed"] or evidence["passed"] or evidence["failed"] or evidence["exit_code"] is not None:
            errors.append(label + ": unrun evidence has execution claims")
        return errors
    if evidence["status"] == "stale":
        return errors
    if evidence["executed"] < 1:
        errors.append(label + ": zero executed checks")
    if evidence["collected"] != evidence["executed"] + evidence["skipped"]:
        errors.append(label + ": collected/executed/skipped mismatch")
    if evidence["executed"] != evidence["passed"] + evidence["failed"]:
        errors.append(label + ": executed/pass/fail mismatch")
    if evidence["status"] == "passed":
        if evidence["failed"] or evidence["exit_code"] != evidence["expected_exit"]:
            errors.append(label + ": passing status contradicts failures/exit")
        if evidence["skipped"]:
            errors.append(label + ": skipped checks cannot certify passing receipt; split receipts")
    elif evidence["status"] == "failed" and not evidence["failed"] and evidence["exit_code"] == evidence["expected_exit"]:
        errors.append(label + ": failure status has no observed failure")
    try:
        if timestamp(evidence["recorded_at"]) > dt.datetime.now(dt.timezone.utc):
            errors.append(label + ": future receipt")
    except ValueError:
        errors.append(label + ": malformed timestamp")
    for path_key, hash_key in (("raw_output", "raw_sha256"), ("artifact", "artifact_sha256")):
        if evidence[path_key] is None or evidence[hash_key] is None:
            errors.append(label + ": missing " + path_key + "/digest")
            continue
        try:
            path = safe_path(root, evidence[path_key])
            if not path.is_file() or digest(path) != evidence[hash_key]:
                errors.append(label + ": missing or changed " + path_key)
        except (OSError, ValueError) as exc:
            errors.append(label + ": " + str(exc))
    return errors


def check_previous(previous, current):
    errors = shape(previous, CONTRACT["root"])
    if errors:
        return ["previous snapshot: " + x for x in errors]
    if previous["id"] != current["id"]:
        return ["previous snapshot belongs to another task"]
    if current["history"][:len(previous["history"])] != previous["history"]:
        errors.append("history was rewritten or removed")
    current_actions = {x["id"]: x for x in current["actions"]}
    evidence = {x["id"]: x for x in current["evidence"]}
    for old in previous["actions"]:
        new = current_actions.get(old["id"])
        if not new:
            errors.append("action removed: " + old["id"])
            continue
        for key in ("kind", "target", "target_hash", "scope_id", "occurrence"):
            if old[key] != new[key]:
                errors.append("action identity changed: " + old["id"])
        if old["decision"] == "denied" and new["decision"] != "denied":
            errors.append("denied action changed decision: " + old["id"])
        if old["outcome"] in {"applied", "denied"} and old["outcome"] != new["outcome"]:
            errors.append("terminal action outcome rewritten: " + old["id"])
        if old["outcome"] == "uncertain" and new["outcome"] != "uncertain":
            observations = [evidence.get(eid) for eid in new["evidence_ids"]]
            if not observations or any(not e or e["status"] != "passed" or e["claim_id"] != old["id"]
                    or (e["revision"], e["patch_id"], e["scope_id"]) !=
                       (current["revision"], current["patch_id"], current["scope_id"]) for e in observations):
                errors.append("uncertain action reconciled without evidence for current action/context: " + old["id"])
    return errors


def check_task(task, root, context=None, previous=None):
    errors = shape(task, CONTRACT["root"])
    if errors:
        return errors
    context = context or {}
    indexes = {}
    for group in ("requirements", "work_units", "acceptance", "actions", "evidence",
                  "findings", "reviews", "lessons", "docs", "history"):
        entries = task[group]
        indexes[group] = {e["id"]: e for e in entries}
        if len(indexes[group]) != len(entries):
            errors.append("duplicate IDs in " + group)
    evidence = indexes["evidence"]
    for receipt in task["evidence"]:
        errors.extend(check_receipt(receipt, root))
    for requirement in task["requirements"]:
        old = requirement["supersedes"]
        if old and (old not in indexes["requirements"] or indexes["requirements"][old]["status"] != "superseded"):
            errors.append(requirement["id"] + ": superseded requirement missing/still active")
        seen, cursor = set(), requirement["id"]
        while cursor in indexes["requirements"]:
            if cursor in seen:
                errors.append(requirement["id"] + ": requirement supersession cycle")
                break
            seen.add(cursor)
            cursor = indexes["requirements"][cursor]["supersedes"]
    graph = indexes["work_units"]
    visited, active = set(), set()

    def visit(key):
        if key in active:
            errors.append("work dependency cycle: " + key)
            return
        if key in visited:
            return
        if key not in graph:
            errors.append("missing work dependency: " + key)
            return
        active.add(key)
        for dependency in graph[key]["depends_on"]:
            visit(dependency)
        active.remove(key)
        visited.add(key)
    for unit in graph:
        visit(unit)
        if not graph[unit]["allowed_paths"]:
            errors.append(unit + ": missing bounded paths")
    identity = lambda action: tuple(action[key] for key in ("kind", "target", "target_hash", "scope_id", "occurrence"))
    denied = {identity(action) for action in task["actions"]
              if action["decision"] == "denied" or action["outcome"] == "denied"}
    for action in task["actions"]:
        if action["outcome"] == "applied" and action["decision"] != "approved":
            errors.append(action["id"] + ": applied action lacks an approved decision")
        if action["kind"] in task["authority"]["forbidden_actions"]:
            if action["decision"] == "approved" or action["outcome"] == "applied":
                errors.append(action["id"] + ": forbidden action approved/applied")
        if action["decision"] == "approved" and action["outcome"] != "applied":
            if action["scope_id"] != task["scope_id"] or action["kind"] not in task["authority"]["allowed_actions"]:
                errors.append(action["id"] + ": approval outside current scope")
        if (action["decision"] == "approved" and action["scope_id"] == task["scope_id"]
                and action["kind"] not in task["authority"]["allowed_actions"]):
            errors.append(action["id"] + ": action kind outside current authority")
        if identity(action) in denied and (action["decision"] == "approved" or action["outcome"] == "applied"):
            errors.append(action["id"] + ": same denied action occurrence cannot be replayed under another ID")
        if action["decision"] == "denied" and action["outcome"] != "denied":
            errors.append(action["id"] + ": denial lost")
        if action["outcome"] == "uncertain" and task["completion"] == "complete":
            errors.append(action["id"] + ": unresolved uncertain mutation")
        if (action["kind"] == "local-write" and action["decision"] == "approved"
                and (action["scope_id"] == task["scope_id"] or action["outcome"] != "applied")):
            if not scope_path(action["target"], task["authority"]["allowed_paths"]):
                errors.append(action["id"] + ": out-of-scope path (diagnostic only)")
        for eid in action["evidence_ids"]:
            if eid not in evidence:
                errors.append(action["id"] + ": unknown action evidence")
    for group in ("acceptance", "findings", "reviews"):
        for item in task[group]:
            for eid in item["evidence_ids"] + item.get("verification_ids", []):
                if eid not in evidence:
                    errors.append(item["id"] + ": unknown evidence " + eid)
    for criterion in task["acceptance"]:
        if criterion["status"] != "passed":
            continue
        refs = [evidence[eid] for eid in criterion["evidence_ids"] if eid in evidence]
        if not refs or not all(e["status"] == "passed" for e in refs):
            errors.append(criterion["id"] + ": passing acceptance lacks passing evidence")
        for e in refs:
            if e["claim_id"] != criterion["id"]:
                errors.append(criterion["id"] + ": evidence belongs to another claim")
            if (e["revision"], e["patch_id"], e["scope_id"]) != (task["revision"], task["patch_id"], task["scope_id"]):
                errors.append(criterion["id"] + ": stale receipt context")
        if criterion["requires_runtime"] and not any(e["type"] in RUNTIME for e in refs):
            errors.append(criterion["id"] + ": source evidence is not runtime evidence")
        if criterion["requires_negative_control"]:
            controls = [evidence.get(e["negative_control"]) for e in refs if e["negative_control"]]
            if not controls or not all(e and e["status"] == "failed" and e["executed"] > 0
                    and e["failed"] > 0 and not e["skipped"] and e["claim_id"] == criterion["id"]
                    and (e["revision"], e["patch_id"], e["scope_id"]) ==
                       (task["revision"], task["patch_id"], task["scope_id"])
                    and (not criterion["requires_runtime"] or e["type"] in RUNTIME) for e in controls):
                errors.append(criterion["id"] + ": missing failed negative control for current claim/context")
    for finding in task["findings"]:
        if finding["adjudication"] == "fixed":
            receipts = [evidence.get(eid) for eid in finding["verification_ids"]]
            if not receipts or any(not e or e["status"] != "passed"
                    or e["claim_id"] != finding["id"]
                    or (e["revision"], e["patch_id"], e["scope_id"]) !=
                       (task["revision"], task["patch_id"], task["scope_id"]) for e in receipts):
                errors.append(finding["id"] + ": fixed finding lacks passing verification")
    independent = []
    for review in task["reviews"]:
        if review["kind"] == "independent" and review["reviewer_id"] == review["author_id"]:
            errors.append(review["id"] + ": self-review labeled independent")
        if review["status"] == "completed":
            receipts = [evidence.get(eid) for eid in review["evidence_ids"]]
            receipt_ok = bool(receipts) and all(e and e["status"] == "passed"
                and e["claim_id"] == review["id"]
                and (e["revision"], e["patch_id"], e["scope_id"]) ==
                    (task["revision"], task["patch_id"], task["scope_id"]) for e in receipts)
            if not receipt_ok:
                errors.append(review["id"] + ": completed review lacks current passing review evidence")
            if review["patch_id"] != task["patch_id"] or review["author_id"] != task["author_id"]:
                errors.append(review["id"] + ": review belongs to another patch/author")
            if not review["evidence_ids"]:
                errors.append(review["id"] + ": completed review without evidence")
            if receipt_ok and review["kind"] == "independent" and review["reviewer_id"] != review["author_id"]:
                independent.append(review)
        for fid in review["finding_ids"]:
            if fid not in indexes["findings"]:
                errors.append(review["id"] + ": unknown finding")
    for lesson in task["lessons"]:
        if lesson["status"] == "revalidated" and freshness(lesson, task["revision"], task["scope_id"]) != "current":
            errors.append(lesson["id"] + ": stale lesson labeled revalidated")
    for doc in task["docs"]:
        if doc["status"] == "current" and freshness(doc) != "current":
            errors.append(doc["id"] + ": stale/mismatched documentation")
    events = task["history"]
    for i, event in enumerate(events):
        if event["to"] not in CONTRACT["transitions"].get(event["from"], []):
            errors.append(event["id"] + ": illegal state transition")
        if i and events[i-1]["to"] != event["from"]:
            errors.append(event["id"] + ": disconnected history")
    if events and events[-1]["to"] != task["state"]:
        errors.append("state does not match history")
    final = task["state"] == "verified" or task["completion"] == "complete"
    if final:
        if any(unit["status"] != "done" for unit in task["work_units"]):
            errors.append("completion contradicts unfinished work units")
        if not any(c["required"] for c in task["acceptance"]) or any(c["required"] and c["status"] != "passed" for c in task["acceptance"]):
            errors.append("required acceptance incomplete or empty")
        if any(f["adjudication"] in {"open", "accepted"} for f in task["findings"]):
            errors.append("unresolved review finding")
        if task["independent_review_required"] and not independent:
            errors.append("required independent review unavailable")
        if task["blockers"] or task["verification"] == "unverified":
            errors.append("completion contradicts blockers/unverified status")
        if task["mode"] in {"build", "repair"} and task["verification"] != "runtime-tested":
            errors.append("build/repair cannot finish with source audit only")
        for key in ("revision", "scope_id", "patch_id"):
            if context.get(key) != task[key]:
                errors.append("current host-observed " + key + " missing/mismatched")
    if task["verification"] == "runtime-tested":
        accepted_ids = {eid for criterion in task["acceptance"] if criterion["status"] == "passed"
                        for eid in criterion["evidence_ids"]}
        if not any(e["id"] in accepted_ids and e["type"] in RUNTIME and e["status"] == "passed"
                   and (e["revision"], e["patch_id"], e["scope_id"]) ==
                       (task["revision"], task["patch_id"], task["scope_id"]) for e in task["evidence"]):
            errors.append("runtime-tested claim lacks runtime evidence")
    delivery_action = {"committed": "commit", "pushed": "push", "pr": "pr", "merged": "merge", "deployed": "deploy"}.get(task["delivery"])
    if delivery_action and not any(a["kind"] == delivery_action and a["outcome"] == "applied" and a["decision"] == "approved" for a in task["actions"]):
        errors.append("delivery state lacks authorized applied action")
    if task["state"] == "delivered" and task["completion"] not in {"partial", "complete"}:
        errors.append("delivered state requires explicit partial/complete outcome")
    if previous is not None:
        errors.extend(check_previous(previous, task))
    return errors


def package_files(root):
    """Reject links before traversal, including Windows directory junctions."""
    files = []
    def unreadable(exc):
        raise ValueError("unreadable package directory: " + str(exc))
    for directory, folders, names in os.walk(root, followlinks=False, onerror=unreadable):
        for name in folders + names:
            path = pathlib.Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("package contains symlink/reparse point: " + str(path))
            if name in names and not stat.S_ISREG(info.st_mode):
                raise ValueError("nonregular package file: " + str(path))
        folders[:] = sorted(name for name in folders if name != "__pycache__")
        files.extend(pathlib.Path(directory) / name for name in sorted(names) if not name.endswith(".pyc"))
    return sorted(files)


def check_package(root):
    root = pathlib.Path(root).resolve()
    errors = []
    try:
        files = package_files(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    entries = [path for path in files if path.name == "SKILL.md"]
    if entries != [root / "SKILL.md"]:
        errors.append("package must have exactly one root SKILL.md")
    if not (root / "SKILL.md").is_file():
        return errors
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"^---\nname: ([a-z0-9-]{1,64})\ndescription: ([^\n]+)\n---\n", text)
    if not front or front[1] != "estack" or len(front[2]) > 1024:
        errors.append("invalid skill trigger metadata")
    for file in (path for path in files if path.suffix == ".md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            relative = target.split("#")[0]
            path = (file.parent / relative).resolve()
            if not path.is_relative_to(root) or not path.exists():
                errors.append(str(file.relative_to(root)) + ": broken/escaping reference " + target)
    return errors


def start_task(args):
    """Create an incomplete canonical record; flags record scope, never grant it."""
    root = pathlib.Path(args.root).resolve(strict=True)
    target = pathlib.Path(args.path).resolve()
    if not root.is_dir() or not target.is_relative_to(root):
        raise ValueError("task output must be inside the caller-selected evidence root")
    if any(not value.strip() for value in (args.goal, args.revision, args.scope, args.author, args.task_id)):
        raise ValueError("goal, identity and observed context must be nonempty")
    if not re.fullmatch(r"[a-f0-9]{64}", args.patch):
        raise ValueError("patch must be the host-observed SHA-256")
    if any(prefix != "." and not scope_path(prefix, [prefix]) for prefix in args.allow_path):
        raise ValueError("allowed paths must be portable paths relative to the selected root")
    record = dict(schema_version=1, id=args.task_id, mode=args.task_mode, size=args.size,
        goal=args.goal, non_goals=[], scope_id=args.scope, revision=args.revision, patch_id=args.patch,
        author_id=args.author,
        authority=dict(allowed_actions=list(dict.fromkeys(args.allow_action)), forbidden_actions=[],
                       allowed_paths=list(dict.fromkeys(args.allow_path))),
        host=dict(name="unprobed", version="unprobed", capabilities=[]),
        requirements=[dict(id="goal", text=args.goal, origin="user", status="active", supersedes=None)],
        work_units=[], acceptance=[], actions=[], evidence=[], findings=[], reviews=[], lessons=[], docs=[], history=[],
        state="framed", completion="open", verification="unverified", independent_review_required=False,
        delivery="none", next_safe_action="Inspect relevant source and host permissions; define acceptance before building",
        blockers=[])
    errors = check_task(record, root)
    if errors:
        raise ValueError("invalid initial record: " + "; ".join(errors))
    # Check directory links as well as output containment before any write.
    relative = target.relative_to(root).as_posix()
    safe_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
    return {"status": "created-incomplete", "path": str(target), "verification": "unverified",
            "claim": "canonical task scaffold only; no host permission granted or work executed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    package = sub.add_parser("package")
    package.add_argument("path")
    init = sub.add_parser("init", help="create an incomplete canonical task without executing anything")
    init.add_argument("path")
    init.add_argument("--root", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--revision", required=True)
    init.add_argument("--scope", required=True)
    init.add_argument("--patch", required=True)
    init.add_argument("--author", required=True)
    init.add_argument("--task-id", default="new-task")
    init.add_argument("--task-mode", choices=CONTRACT["$defs"]["task"]["properties"]["mode"]["enum"], default="build")
    init.add_argument("--size", choices=["tiny", "bounded", "cross-cutting"], default="bounded")
    init.add_argument("--allow-path", action="append", required=True)
    init.add_argument("--allow-action", action="append", default=[],
                      choices=CONTRACT["$defs"]["action"]["properties"]["kind"]["enum"])
    task = sub.add_parser("task")
    task.add_argument("path")
    task.add_argument("--root", required=True)
    task.add_argument("--revision")
    task.add_argument("--scope")
    task.add_argument("--patch")
    task.add_argument("--previous")
    args = parser.parse_args()
    try:
        if args.mode == "init":
            print(json.dumps(start_task(args), indent=2))
            return 0
        elif args.mode == "package":
            errors = check_package(args.path)
        else:
            errors = check_task(read_json(args.path), args.root,
                                {"revision": args.revision, "scope_id": args.scope, "patch_id": args.patch},
                                read_json(args.previous) if args.previous else None)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        errors = ["malformed/unreadable input: " + str(exc)]
    print(json.dumps({"status": "failed" if errors else "passed",
                      "claim": "consistency-only; not truth, host enforcement or model qualification",
                      "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

