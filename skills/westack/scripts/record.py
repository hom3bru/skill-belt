"""westack task-record contract: shape, consistency, append-only history and the record writers.

The record is optional; tiny work uses none. Standard library only; runs no process, opens no network
connection, and writes each record version by exclusive create (an existing file is never replaced).
"""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import sys

__all__ = [
    "BASE", "CONTRACT", "VERSION_NAME", "ADJUDICATION_NEXT", "REQUIREMENT_NEXT", "DECISION_NEXT", "REASON_CODES",
    "shape", "definition", "freshness", "approval_matches", "reconcile", "check_previous", "check_supersession",
    "check_task", "check_delegates", "version_parts", "next_version", "check_chain", "start_task", "task_context",
    "resolve_into_root", "load_version", "add_receipt", "refresh", "waiting_notes",
    "supersedes_ids", "decision_links", "reason_tally", "definition_hash", "definition_drift", "receipt_options",
]


def _sibling(name):
    """Load a sibling helper by path under a key unique to this copy of the core."""
    path = pathlib.Path(__file__).resolve().with_name(name + ".py")
    key = "westack_" + name + "_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return module


_e = _sibling("evidence")
(RUNTIME, DEFAULT_EXCLUDE, digest, read_json, write_new, safe_path, scope_path, portable, within, check_excludes,
 fingerprint, store_manifest, resolve_revision, snapshot, timestamp, supports, same_content, short,
 check_receipt, control_errors, load_manifest, diff_entries) = (
    _e.RUNTIME, _e.DEFAULT_EXCLUDE, _e.digest, _e.read_json, _e.write_new, _e.safe_path, _e.scope_path,
    _e.portable, _e.within, _e.check_excludes, _e.fingerprint, _e.store_manifest, _e.resolve_revision,
    _e.snapshot, _e.timestamp, _e.supports, _e.same_content, _e.short, _e.check_receipt, _e.control_errors,
    _e.load_manifest, _e.diff_entries)

BASE = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = json.loads((BASE / "contracts/contract.json").read_text(encoding="utf-8"))
VERSION_NAME = re.compile(r"(?P<stem>.+)\.(?P<number>\d+)\.json")
# Between snapshots, adjudication, requirement and decision status only move forward.
ADJUDICATION_NEXT = {"open": {"accepted", "rejected", "deferred", "fixed"}, "accepted": {"deferred", "fixed"},
                     "deferred": {"fixed"}, "rejected": set(), "fixed": set()}
REQUIREMENT_NEXT = {"active": {"parked", "superseded"}, "parked": {"active", "superseded"}, "superseded": set()}
DECISION_NEXT = {"proposed": {"active", "rejected"}, "active": {"deprecated", "superseded"},
                 "deprecated": {"superseded"}, "rejected": set(), "superseded": set()}
# A delegate that has not ended cannot be closed; every other end except `finished` names its cause.
DELEGATE_LIVE = {"running", "waiting-on-person"}
DELEGATE_NEEDS_REASON = {"budget-exhausted", "crashed", "lost", "declined", "cancelled", "waiting-on-person"}
# A receipt that did not finish names a fixed reason; the last two codes also record the value seen and the limit.
REASON_CODES = tuple(CONTRACT["$defs"]["evidence"]["properties"]["reason"]["properties"]["code"]["enum"])
UNFINISHED = {"blocked", "not-run", "inconclusive"}
NEEDS_NUMBERS = {"timeout", "cap-reached"}
RELATION_LABEL = {"amends": "amended by", "clarifies": "clarified by", "depends-on": "depended on by"}


def shape(value, spec, where="$", defs=None):
    """Errors for `value` against `spec` in the contract's small vocabulary; `defs` resolves $ref
    (default: contract.json's $defs)."""
    defs = CONTRACT["$defs"] if defs is None else defs
    if "$ref" in spec:
        spec = defs[spec["$ref"].split("/")[-1]]
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
            errors.append(where + ": pattern mismatch" + (" (lowercase hex required)" if "a-f0-9" in spec["pattern"] else ""))
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
                errors.extend(shape(value[key], spec["properties"][key], where + "." + key, defs))
    if actual == "array":
        for i, item in enumerate(value):
            errors.extend(shape(item, spec["items"], where + "[" + str(i) + "]", defs))
    return errors


def definition(task, override_paths=None):
    """The fingerprint definition a record observes: (paths, excludes)."""
    stored = task.get("fingerprint")
    paths = override_paths or (stored["paths"] if stored else None) or task["authority"]["allowed_paths"] or ["."]
    return list(paths), (list(stored["exclude"]) if stored else list(DEFAULT_EXCLUDE))


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
    if observed == "applied" and action["decision"] != "approved":
        return "report-unauthorized-effect"
    if action["decision"] == "denied" or action["outcome"] == "denied":
        return "stop-denied"
    if action["outcome"] == "applied" or observed == "applied":
        return "do-not-replay"
    if action["outcome"] == "uncertain":
        return "refresh-authority-before-retry" if observed == "not-applied" else "inspect-without-replay"
    return "refresh-authority-before-retry"


def supersedes_ids(item):
    """The ids an item supersedes: none, one (requirements, older decisions) or several."""
    value = item["supersedes"]
    return [] if value is None else [value] if isinstance(value, str) else list(value)


def decision_links(task):
    """The reverse view of supersession and relations, derived from the later decision only: {id: [(label, by)]}."""
    links = {}
    for item in task.get("decisions", []):
        for old in supersedes_ids(item):
            links.setdefault(old, []).append(("superseded by", item["id"]))
        for relation in item.get("relations", []):
            links.setdefault(relation["target"], []).append((RELATION_LABEL[relation["type"]], item["id"]))
    return links


def reason_tally(task):
    """{code: [receipt ids]} for receipts that did not finish. A receipt with no code, or free text only, counts as
    no-reason-given and stays outstanding."""
    tally = {}
    for item in task["evidence"]:
        if item["status"] in UNFINISHED:
            tally.setdefault(item.get("reason", {}).get("code", "no-reason-given"), []).append(item["id"])
    return tally


def definition_hash(operation, expected_exit, files):
    """SHA-256 of a check's definition: the command text, its expected exit and the bytes of the files that define it."""
    lines = ["westack-definition-v1", operation, str(expected_exit)] + [path + "\0" + sha for path, sha in sorted(files)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def definition_drift(receipt, repo):
    """None while a receipt's recorded check definition still holds in `repo`, else why it no longer does."""
    stored = receipt.get("definition")
    if not stored:
        return None
    try:
        files = [(path, digest(safe_path(repo, path))) for path in stored["paths"]]
    except (OSError, ValueError) as exc:
        return "a definition file is unreadable (" + str(exc) + ")"
    now = definition_hash(receipt["operation"], receipt["expected_exit"], files)
    return None if now == stored["sha256"] else "stored " + short(stored["sha256"]) + ", now " + short(now)


def covers(excludes, entry):
    """True when an exclude entry (a name at any depth, or a repository-relative path) already hides `entry`."""
    parts = entry.split("/")
    return any(entry == old or ("/" not in old and old in parts) or entry.startswith(old.rstrip("/") + "/")
               for old in excludes)


def link_state(record, before, before_path):
    """`linked`, `unlinked` or `broken` for a version's previous_sha256 against the file it should hash. A link a
    hand-copied version repeats from its predecessor proves nothing and reads as unlinked."""
    link = record.get("previous_sha256")
    if link is None or link == before.get("previous_sha256"):
        return "unlinked"
    return "linked" if link == digest(before_path) else "broken"


def changed_since(old_patch, new_patch, root):
    if old_patch == new_patch:
        return "no files changed since"
    try:
        old, new = load_manifest(root, old_patch), load_manifest(root, new_patch)
    except (OSError, ValueError):
        old = new = None
    if old is None or new is None:
        return "files changed since: unknown (no stored manifest for one of the patches)"
    diff = diff_entries(old, new)
    return "files changed since: " + (", ".join(sorted(set(diff["added"] + diff["modified"] + diff["removed"]))) or "none")


def regression_note(was, criterion, current, earlier_patch, root, where):
    """A criterion that passed earlier and now fails: name the last passing receipts and the files changed since."""
    failing = [e["id"] for e in current["evidence"] if e["id"] in criterion["evidence_ids"] and e["status"] == "failed"]
    return (criterion["id"] + " regressed: last passed with " + ", ".join(was["evidence_ids"]) + " in " + where
            + "; now failed" + (" (" + ", ".join(failing) + ")" if failing else "") + "; "
            + changed_since(earlier_patch, current["patch_id"], root))


def decision_rewritten(old, new):
    """The optional parts of a decision are fixed once recorded: they may be added, and lists only grow."""
    for key in ("because", "alternative_reasons", "confirmation", "relations", "cites_memory"):
        if key in old:
            if isinstance(old[key], list):
                if any(item not in new.get(key, []) for item in old[key]):
                    return True
            elif new.get(key) != old[key]:
                return True
    return False


def check_previous(previous, current, notes=None, root=None):
    notes = [] if notes is None else notes
    errors = shape(previous, CONTRACT["root"])
    if errors:
        return ["previous snapshot: " + x for x in errors]
    if previous["id"] != current["id"]:
        return ["previous snapshot belongs to another task"]
    prefix_kept = current["history"][:len(previous["history"])] == previous["history"]
    if not prefix_kept:
        errors.append("history was rewritten or removed")
    new_events = current["history"][len(previous["history"]):] if prefix_kept else []
    scope_changed = previous["scope_id"] != current["scope_id"]
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
            if not observations or any(not e or e["status"] != "passed" or not supports(e, old["id"])
                                       or not same_content(e, current) for e in observations):
                errors.append("uncertain action reconciled without evidence for current action/context: " + old["id"])
    # Receipts are immutable except for becoming stale; a failure is never replaced.
    for old in previous["evidence"]:
        new = evidence.get(old["id"])
        if new is None:
            errors.append("receipt removed: " + old["id"])
        elif new != old and not (new["status"] == "stale" and
                                 {k: x for k, x in new.items() if k != "status"} ==
                                 {k: x for k, x in old.items() if k != "status"}):
            errors.append("receipt rewritten: " + old["id"] + " (only a change to stale is allowed)")
    findings = {x["id"]: x for x in current["findings"]}
    for old in previous["findings"]:
        new = findings.get(old["id"])
        if new is None:
            errors.append("finding removed: " + old["id"])
        elif old["adjudication"] != new["adjudication"] and new["adjudication"] not in ADJUDICATION_NEXT[old["adjudication"]]:
            errors.append("finding " + old["id"] + " adjudication cannot move from " + old["adjudication"]
                          + " to " + new["adjudication"])
    requirements = {x["id"]: x for x in current["requirements"]}
    for old in previous["requirements"]:
        new = requirements.get(old["id"])
        if new is None:
            errors.append("requirement removed: " + old["id"])
        elif any(old[key] != new[key] for key in ("text", "origin", "supersedes")):
            errors.append("requirement rewritten: " + old["id"] + " (supersede it with a new requirement)")
        elif old["status"] != new["status"] and new["status"] not in REQUIREMENT_NEXT[old["status"]]:
            errors.append("requirement " + old["id"] + " status cannot move from " + old["status"]
                          + " to " + new["status"])
    decisions = {x["id"]: x for x in current.get("decisions", [])}
    resolved = {name for e in new_events if e.get("reason") for name in e.get("resolves", [])}
    for old in previous.get("decisions", []):
        new = decisions.get(old["id"])
        if new is None:
            errors.append("decision " + old["id"] + " removed")
        elif old["status"] == "proposed" == new["status"]:
            continue  # a draft the user has not answered may still be edited
        elif (any(old[key] != new[key] for key in ("question", "choice", "alternatives", "origin"))
              or supersedes_ids(old) != supersedes_ids(new) or decision_rewritten(old, new)):
            errors.append("decision " + old["id"] + " rewritten (supersede it with a new decision)")
        elif old["status"] != new["status"] and new["status"] not in DECISION_NEXT[old["status"]]:
            errors.append("decision " + old["id"] + " status cannot move from " + old["status"] + " to " + new["status"])
        elif old["status"] == "proposed" and old["id"] not in resolved:
            errors.append("decision " + old["id"] + " moved from proposed to " + new["status"]
                          + " without a history event that resolves it (the user's answer: a reason and resolves)")
    notes.extend("decision " + item["id"] + ": an assumption written as active; a decision the agent makes starts "
                 "proposed until the user accepts it (a later contract version may refuse this)"
                 for item in current.get("decisions", [])
                 if item["origin"] == "assumption" and item["status"] == "active"
                 and item["id"] not in {x["id"] for x in previous.get("decisions", [])})
    # Observations (eliminations, confirmations, surprises) are append-only.
    observations = {x["id"]: x for x in current.get("observations", [])}
    for old in previous.get("observations", []):
        new = observations.get(old["id"])
        if new is None:
            errors.append("observation removed: " + old["id"])
        elif new != old:
            errors.append("observation rewritten: " + old["id"] + " (add a new observation that cites it instead)")
    # Delegation ledger entries stay visible; a closed entry stays closed.
    delegates = {x["id"]: x for x in current.get("delegates", [])}
    for old in previous.get("delegates", []):
        new = delegates.get(old["id"])
        if new is None:
            errors.append("delegate removed: " + old["id"])
        elif any(old[key] != new[key] for key in ("parent", "executor", "tier", "scope")):
            key = next(k for k in ("parent", "executor", "tier", "scope") if old[k] != new[k])
            errors.append("delegate identity changed: " + old["id"] + " (" + key + " was '" + old[key] + "', now '"
                          + new[key] + "')")
        elif old.get("outcome") is not None and new.get("outcome") != old["outcome"]:
            errors.append("delegate outcome rewritten: " + old["id"] + " (a closed entry stays closed)")
        elif "deadline_at" in old:
            # The deadline is fixed when the work starts; a resume cannot extend or drop it.
            if "deadline_at" not in new:
                errors.append("delegate " + old["id"] + ": deadline_at removed (it is fixed when the work starts)")
            else:
                try:
                    if timestamp(new["deadline_at"]) > timestamp(old["deadline_at"]):
                        errors.append("delegate " + old["id"] + ": deadline_at moved later (it is fixed when the work"
                                      " starts; a resume cannot extend it)")
                except ValueError:
                    pass  # check_task reports the malformed timestamp
    # A finished unit is never reopened (the retry is a new unit naming it); a claimed unit is not queued unseen.
    now_units = {x["id"]: x for x in current["work_units"]}
    for old in previous["work_units"]:
        new = now_units.get(old["id"])
        if new is None:
            continue
        if old["status"] == "done" and new["status"] != "done":
            errors.append("work unit " + old["id"] + " was done and cannot be reopened; start a new unit that names it"
                          " in retry_of")
        if (old.get("claim", {}).get("state") in {"claimed", "lapsed"} and new["status"] == "planned"
                and new.get("claim", {}).get("state") != "inspected"):
            errors.append(old["id"] + ": returned to planned without inspecting the claimant's target")
    # A step that newly ends without a confirmed result says why.
    before = {x["id"]: x for x in previous["actions"]}
    errors.extend(item["id"] + ": a step that ended without a confirmed result records why it ended (cause)"
                  for item in current["actions"] if item["outcome"] == "uncertain" and "cause" not in item
                  and before.get(item["id"], {}).get("outcome") != "uncertain")
    if "base_revision" in previous and current.get("base_revision") != previous["base_revision"]:
        errors.append("base_revision " + ("removed" if "base_revision" not in current else "changed")
                      + " (it records the revision the task started from)")
    for criterion in current["acceptance"]:
        was = next((c for c in previous["acceptance"] if c["id"] == criterion["id"] and c["status"] == "passed"), None)
        if was and criterion["status"] == "failed":
            notes.append(regression_note(was, criterion, current, previous["patch_id"], root, "the previous version"))
    # Finish conditions only get stricter within a scope.
    relaxed = []
    acceptance = {x["id"]: x for x in current["acceptance"]}
    for old in previous["acceptance"]:
        new = acceptance.get(old["id"])
        if new is None:
            relaxed.append("acceptance " + old["id"] + " removed")
        elif old["claim"] != new["claim"] or any(old[flag] and not new[flag] for flag in
                                                 ("required", "requires_runtime", "requires_negative_control")):
            relaxed.append("acceptance " + old["id"] + " cannot be weakened (claim and requirement flags are fixed)")
        elif old.get("verifier") == "human" and new.get("verifier") != "human":
            relaxed.append("acceptance " + old["id"] + " verifier cannot move from human to agent")
    if previous["independent_review_required"] and not current["independent_review_required"]:
        relaxed.append("independent_review_required cannot be dropped")
    units = {x["id"] for x in current["work_units"]}
    relaxed.extend("unfinished work unit " + old["id"] + " removed" for old in previous["work_units"]
                   if old["id"] not in units and old["status"] != "done")
    reviews = {x["id"] for x in current["reviews"]}
    relaxed.extend("review " + old["id"] + " removed" for old in previous["reviews"] if old["id"] not in reviews)
    relaxed.extend("forbidden action " + kind + " removed" for kind in previous["authority"]["forbidden_actions"]
                   if kind not in current["authority"]["forbidden_actions"])
    relaxed.extend("non-goal removed: " + goal for goal in previous["non_goals"] if goal not in current["non_goals"])
    # What the fingerprint ignores or observes is part of scope; a stop-on-purpose marker is the user's word.
    old_paths, old_excludes = definition(previous)
    new_paths, new_excludes = definition(current)
    relaxed.extend("fingerprint exclusion widened: " + item for item in new_excludes if not covers(old_excludes, item))
    # Observed paths that merely follow the allowed paths (no stored fingerprint on either side) narrow with them.
    explicit = "fingerprint" in previous or "fingerprint" in current
    relaxed.extend("fingerprint path narrowed: " + item for item in old_paths
                   if explicit and portable(item) and not within(item, new_paths))
    if previous.get("stop", {}).get("kind") == "on-purpose" and current.get("stop") != previous["stop"]:
        relaxed.append("stop marker (on purpose) changed or removed")
    if relaxed:
        if not scope_changed:
            errors.extend(x + " within an unchanged scope (relaxing needs a new scope_id and a history event giving the reason)"
                          for x in relaxed)
        elif not any(e.get("reason") and e["scope_id"] == current["scope_id"] for e in new_events):
            errors.extend(x + " (relaxed under a scope change without a history event recording why)" for x in relaxed)
    if not scope_changed:
        old_allowed, new_allowed = previous["authority"]["allowed_actions"], current["authority"]["allowed_actions"]
        for kind in old_allowed:
            if kind not in new_allowed:
                errors.append("removing allowed action " + kind + " is a scope change: set a new scope_id")
        granted = {kind for e in new_events if e.get("reason") for kind in e.get("grants", [])}
        for kind in new_allowed:
            if kind not in old_allowed and kind not in granted:
                errors.append("allowed action " + kind + " added without a history event recording the user's grant"
                              " (reason and grants)")
    return errors


def check_supersession(items, index, noun):
    errors = []
    for item in items:
        # A proposal or a rejected proposal replaces nothing yet.
        if item["status"] not in {"proposed", "rejected"}:
            for old in supersedes_ids(item):
                if old not in index or index[old]["status"] != "superseded":
                    errors.append(item["id"] + ": superseded " + noun + " missing/still active")
        pending, seen = supersedes_ids(item), set()
        while pending:
            cursor = pending.pop()
            if cursor == item["id"]:
                errors.append(item["id"] + ": " + noun + " supersession cycle")
                break
            if cursor in index and cursor not in seen:
                seen.add(cursor)
                pending.extend(supersedes_ids(index[cursor]))
    return errors


def check_task(task, root, context=None, previous=None, notes=None):
    errors = shape(task, CONTRACT["root"])
    if errors:
        return errors
    notes = [] if notes is None else notes
    context = context or {}
    authority = task["authority"]
    current = lambda item: same_content(item, task)
    indexes = {}
    for group in ("requirements", "work_units", "acceptance", "actions", "evidence",
                  "findings", "reviews", "lessons", "docs", "history", "decisions", "observations", "delegates"):
        entries = task.get(group, [])
        indexes[group] = {e["id"]: e for e in entries}
        if len(indexes[group]) != len(entries):
            errors.append("duplicate IDs in " + group)
    evidence = indexes["evidence"]
    for path in authority["allowed_paths"]:
        if not portable(path):
            errors.append("nonportable authority path: " + path)
    for kind in sorted(set(authority["allowed_actions"]) & set(authority["forbidden_actions"])):
        errors.append("authority: " + kind + " is both allowed and forbidden")
    if "fingerprint" in task:
        observed_paths = task["fingerprint"]["paths"]
        for path in observed_paths:
            if not portable(path):
                errors.append("nonportable fingerprint path: " + path)
        try:
            check_excludes(task["fingerprint"]["exclude"])
        except ValueError as exc:
            errors.append(str(exc))
        if not observed_paths:
            errors.append("fingerprint.paths is empty")
        for path in authority["allowed_paths"]:
            if portable(path) and observed_paths and not within(path, observed_paths):
                errors.append("allowed path " + path + " is not inside fingerprint.paths; edits there would go unobserved")
    for receipt in task["evidence"]:
        errors.extend(check_receipt(receipt, root))
        # A receipt also goes stale when the definition of its check changed; only a receipt that stores one can.
        if receipt["status"] == "stale" and current(receipt) and "definition" not in receipt:
            errors.append(receipt["id"] + ": marked stale but matches the current patch and scope")
    errors.extend(check_supersession(task["requirements"], indexes["requirements"], "requirement"))
    errors.extend(check_supersession(task.get("decisions", []), indexes["decisions"], "decision"))
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
        for path in graph[unit]["allowed_paths"]:
            if not portable(path):
                errors.append(unit + ": nonportable work-unit path " + path)
            elif not within(path, authority["allowed_paths"]):
                errors.append(unit + ": work-unit path outside authority " + path)
        for aid in graph[unit].get("acceptance_ids", []):
            if aid not in indexes["acceptance"]:
                errors.append(unit + ": unknown acceptance " + aid)
    identity = lambda action: tuple(action[key] for key in ("kind", "target", "target_hash", "scope_id", "occurrence"))
    denied = {identity(action) for action in task["actions"]
              if action["decision"] == "denied" or action["outcome"] == "denied"}
    for action in task["actions"]:
        if action["outcome"] == "applied" and action["decision"] != "approved":
            errors.append(action["id"] + ": applied action lacks an approved decision")
        if action["kind"] in authority["forbidden_actions"]:
            if action["decision"] == "approved" or action["outcome"] == "applied":
                errors.append(action["id"] + ": forbidden action approved/applied")
        if action["decision"] == "approved" and action["outcome"] != "applied":
            if action["scope_id"] != task["scope_id"] or action["kind"] not in authority["allowed_actions"]:
                errors.append(action["id"] + ": approval outside current scope")
        if (action["decision"] == "approved" and action["scope_id"] == task["scope_id"]
                and action["kind"] not in authority["allowed_actions"]):
            errors.append(action["id"] + ": action kind outside current authority")
        if identity(action) in denied and (action["decision"] == "approved" or action["outcome"] == "applied"):
            errors.append(action["id"] + ": same denied action occurrence cannot be replayed under another ID")
        if action["decision"] == "denied" and action["outcome"] != "denied":
            errors.append(action["id"] + ": denial lost")
        if action["outcome"] == "uncertain" and task["completion"] == "complete":
            errors.append(action["id"] + ": unresolved uncertain mutation")
        if (action["kind"] == "local-write" and action["decision"] == "approved"
                and (action["scope_id"] == task["scope_id"] or action["outcome"] != "applied")):
            if not scope_path(action["target"], authority["allowed_paths"]):
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
        cid = criterion["id"]
        refs = [evidence[eid] for eid in criterion["evidence_ids"] if eid in evidence]
        if not refs or not all(e["status"] == "passed" for e in refs):
            errors.append(cid + ": passing acceptance lacks passing evidence")
        for e in refs:
            if not supports(e, cid):
                errors.append(cid + ": evidence belongs to another claim")
            if not current(e):
                errors.append(cid + ": stale receipt context")
        if criterion["requires_runtime"] and not any(e["type"] in RUNTIME for e in refs):
            errors.append(cid + ": source evidence is not runtime evidence")
        if criterion["requires_negative_control"]:
            if not refs:
                errors.append(cid + ": missing failed negative control for current claim/context")
            # Every receipt needs its own failed run of the same check on a different (broken) artifact.
            # The control may predate the fix (a red run), but must belong to this claim and scope.
            for e in refs:
                control = evidence.get(e["negative_control"]) if e["negative_control"] else None
                errors.extend(control_errors(cid, e, control, task["scope_id"]))
        if criterion.get("verifier") == "human":
            # Only a person can pass it: a passing review receipt cited by a completed human-level review.
            human = [r for r in task["reviews"] if r["status"] == "completed" and r.get("level") == "human"
                     and r["reviewer_id"] != r["author_id"]]
            if not any(e["type"] == "review" and e["status"] == "passed" and supports(e, cid) and current(e)
                       and any(e["id"] in r["evidence_ids"] for r in human) for e in refs):
                errors.append(cid + ": a human-verified criterion needs a passing review receipt from a completed"
                              " human review; agent receipts cannot pass it")
    for observation in task.get("observations", []):
        for eid in observation["evidence_ids"]:
            if eid not in evidence:
                errors.append(observation["id"] + ": unknown evidence " + eid)
        if observation["kind"] in {"ruled-out", "confirmed"} and not observation["evidence_ids"]:
            errors.append(observation["id"] + ": a " + observation["kind"]
                          + " observation cites the evidence behind it")
    if "resume_check" in task:
        target = indexes["acceptance"].get(task["resume_check"])
        if not target or not target["required"]:
            errors.append("resume_check must name a required acceptance criterion: " + task["resume_check"])
    for finding in task["findings"]:
        if finding["adjudication"] == "fixed":
            receipts = [evidence.get(eid) for eid in finding["verification_ids"]]
            if not receipts or any(not e or e["status"] != "passed" or not supports(e, finding["id"])
                                   or not current(e) for e in receipts):
                errors.append(finding["id"] + ": fixed finding lacks passing verification")
    independent = []
    for review in task["reviews"]:
        level = review.get("level")
        if review["kind"] == "independent" and review["reviewer_id"] == review["author_id"]:
            errors.append(review["id"] + ": self-review labeled independent")
        if review["kind"] == "independent" and level == "self":
            errors.append(review["id"] + ": independent review recorded at level self")
        if review["kind"] == "self" and level not in (None, "self"):
            errors.append(review["id"] + ": self review cannot record level " + level)
        if review["status"] == "completed":
            receipts = [evidence.get(eid) for eid in review["evidence_ids"]]
            receipt_ok = bool(receipts) and all(e and e["status"] == "passed"
                and supports(e, review["id"]) and current(e) for e in receipts)
            if not receipt_ok:
                errors.append(review["id"] + ": completed review lacks current passing review evidence"
                              " (passed records that the review ran; put defects in findings)")
            if review["patch_id"] != task["patch_id"] or review["author_id"] != task["author_id"]:
                errors.append(review["id"] + ": review belongs to another patch/author")
            if not review["evidence_ids"]:
                errors.append(review["id"] + ": completed review without evidence")
            if receipt_ok and review["kind"] == "independent" and review["reviewer_id"] != review["author_id"]:
                independent.append(review)
            # A producer stamp is self-declared; a receipt counts for this review only if the stamp matches it.
            for eid in review["evidence_ids"]:
                stamp = (evidence.get(eid) or {}).get("producer")
                if stamp and stamp["context_id"] != review["context_id"]:
                    errors.append(review["id"] + ": receipt " + eid + " was stamped by context " + stamp["context_id"]
                                  + ", not the review's context " + review["context_id"])
                if stamp and review["kind"] == "independent" and stamp["context_id"] == review["author_id"]:
                    errors.append(review["id"] + ": independent review backed by receipt " + eid
                                  + " stamped by the author")
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
    if not events and task["state"] != "framed":
        errors.append("empty history requires state framed; record each transition from framed")
    if events and events[0]["from"] != "framed":
        errors.append("history must start at framed")
    for i, event in enumerate(events):
        if event["from"] == event["to"]:
            # A note event keeps the state; it must say why (scope change, grant, refresh).
            if event["from"] not in CONTRACT["transitions"] or not event.get("reason"):
                errors.append(event["id"] + ": illegal state transition (a same-state event needs a reason)")
        elif event["to"] not in CONTRACT["transitions"].get(event["from"], []):
            errors.append(event["id"] + ": illegal state transition")
        if event.get("grants") and not event.get("reason"):
            errors.append(event["id"] + ": a grant needs a reason")
        if i and events[i-1]["to"] != event["from"]:
            errors.append(event["id"] + ": disconnected history")
    if events and events[-1]["to"] != task["state"]:
        errors.append("state does not match history")
    final = task["state"] == "verified" or task["completion"] == "complete"
    if final:
        if not events:
            errors.append("final record needs a nonempty connected history")
        if any(unit["status"] != "done" for unit in task["work_units"]):
            errors.append("completion contradicts unfinished work units")
        if not any(c["required"] for c in task["acceptance"]) or any(c["required"] and c["status"] != "passed" for c in task["acceptance"]):
            errors.append("required acceptance incomplete or empty")
        if any(f["adjudication"] in {"open", "accepted"} for f in task["findings"]):
            errors.append("unresolved review finding")
        if task["independent_review_required"]:
            if not independent:
                errors.append("required independent review unavailable")
            elif not any(r.get("level") not in (None, "self") for r in independent):
                errors.append("required independent review needs a recorded independence level other than self"
                              " (fresh-context-same-model, different-model or human)")
        if task["blockers"] or task["verification"] == "unverified":
            errors.append("completion contradicts blockers/unverified status")
        if task["mode"] in {"build", "repair"}:
            if task["verification"] != "runtime-tested":
                errors.append("build/repair cannot finish with source audit only")
            reached = [e["to"] for e in events]
            last = max((i for i, state in enumerate(reached) if state == "implemented"), default=None)
            if last is None or "verified" not in reached[last + 1:]:
                errors.append("build/repair needs a verified event after implemented in history")
    errors.extend(check_delegates(task, final))
    waiting = task.get("waiting_on")
    if waiting:
        check = waiting["check"]
        if check["kind"] == "hash-matches" and "sha256" not in check:
            errors.append("waiting_on.check: hash-matches needs sha256")
        if check["kind"] != "hash-matches" and "sha256" in check:
            errors.append("waiting_on.check: sha256 applies only to hash-matches")
        if check["kind"] in {"file-exists", "hash-matches"} and (not portable(check["target"]) or check["target"] == "."):
            errors.append("waiting_on.check.target: a file check needs a portable repository-relative path")
        try:
            timestamp(waiting["expires_at"])
        except ValueError:
            errors.append("waiting_on.expires_at: not an ISO timestamp with a timezone")
        if final:
            errors.append("completion contradicts waiting_on: still waiting on " + waiting["what"])
    errors.extend(check_optional(task, indexes, final, notes))
    # Supplied host context binds every record; final records must supply it. Patch and scope decide
    # staleness; a moved revision with the same content is reported, not rejected.
    for key in ("scope_id", "patch_id"):
        observed = context.get(key)
        if (final or observed is not None) and observed != task[key]:
            errors.append("current host-observed " + key + " missing/mismatched: record " + short(task[key])
                          + ", observed " + short(observed))
    observed_revision = context.get("revision")
    if final and observed_revision is None:
        errors.append("current host-observed revision missing: a final record needs the observed revision")
    elif observed_revision is not None and observed_revision != task["revision"]:
        notes.append("revision moved: record " + task["revision"] + ", observed " + observed_revision
                     + "; staleness follows patch and scope, so receipts for this content stay current")
    if task["verification"] == "runtime-tested":
        accepted_ids = {eid for criterion in task["acceptance"] if criterion["status"] == "passed"
                        for eid in criterion["evidence_ids"]}
        if not any(e["id"] in accepted_ids and e["type"] in RUNTIME and e["status"] == "passed" and current(e)
                   for e in task["evidence"]):
            errors.append("runtime-tested claim lacks runtime evidence")
    delivery_action = {"committed": "commit", "pushed": "push", "pr": "pr", "merged": "merge", "deployed": "deploy"}.get(task["delivery"])
    if delivery_action and not any(a["kind"] == delivery_action and a["outcome"] == "applied" and a["decision"] == "approved" for a in task["actions"]):
        errors.append("delivery state lacks authorized applied action")
    if task["state"] == "delivered" and task["completion"] not in {"partial", "complete"}:
        errors.append("delivered state requires explicit partial/complete outcome")
    if previous is not None:
        errors.extend(check_previous(previous, task, notes, root))
    return errors


def check_delegates(task, final):
    """The delegation ledger's rules over a shape-valid record: every parent chain ends at the task, every end except
    `finished` gives a reason, a closed entry has ended and its outcome carries a ref (landed) or a reason
    (discarded), and with `final` a run is not closed with an open entry. check_task applies it; westack-orchestrate's
    workers.py calls it with final=True to ask whether a run's ledger can close."""
    errors = []
    delegates = {e["id"]: e for e in task.get("delegates", [])}
    for entry in task.get("delegates", []):
        name, outcome, cursor, seen = entry["id"], entry.get("outcome"), entry["parent"], {entry["id"]}
        while cursor != task["id"] and cursor in delegates and cursor not in seen:
            seen.add(cursor)
            cursor = delegates[cursor]["parent"]
        if cursor != task["id"]:
            errors.append(name + ": parent chain does not reach the task (" + entry["parent"] + ")")
        if entry["status"] in DELEGATE_NEEDS_REASON and "reason" not in entry:
            errors.append(name + ": status " + entry["status"] + " needs a reason")
        if outcome is None:
            if final:
                errors.append(name + ": delegate ledger entry still open (land it with a ref or discard it with a reason)")
            continue
        if entry["status"] in DELEGATE_LIVE:
            errors.append(name + ": status " + entry["status"] + " has not ended, so it cannot be closed")
        if outcome["disposition"] == "landed" and "ref" not in outcome:
            errors.append(name + ": a landed outcome needs a ref")
        if outcome["disposition"] == "discarded" and "reason" not in outcome:
            errors.append(name + ": a discarded outcome needs a reason")
    return errors


def evidence_option_errors(receipt):
    """Errors in a receipt's optional reason and check definition."""
    label, errors, reason = receipt["id"], [], receipt.get("reason")
    if reason and receipt["status"] not in UNFINISHED:
        errors.append(label + ": a reason code applies only to blocked, not-run or inconclusive receipts")
    elif reason and reason["code"] in NEEDS_NUMBERS and not (reason.get("observed") and reason.get("limit")):
        errors.append(label + ": a " + reason["code"] + " reason records the observed value and the limit")
    errors.extend(label + ": nonportable definition path: " + path for path in receipt.get("definition", {}).get("paths", [])
                  if not portable(path) or path == ".")
    return errors


def check_optional(task, indexes, final, notes):
    """Checks for the optional fields and objects. A field that is absent never fails a record; where an older
    record could trip a check, it is a note."""
    errors, now = [], dt.datetime.now(dt.timezone.utc)
    evidence, criteria = indexes["evidence"], indexes["acceptance"]
    # Receipts: reason codes, check definitions, producer stamps.
    for receipt in task["evidence"]:
        errors.extend(evidence_option_errors(receipt))
    tally = reason_tally(task)
    if tally:
        notes.append("reason codes: " + ", ".join(code + " " + str(len(ids)) + " (" + ", ".join(ids) + ")"
                                                  for code, ids in sorted(tally.items())))
    stamped = [(e["id"], e["producer"]) for e in task["evidence"] if "producer" in e]
    unknown = [eid for eid, stamp in stamped if stamp.get("observed_model", "unknown") == "unknown"]
    if unknown:
        notes.append("producer stamps are self-declared, not signatures; observed model unknown: " + ", ".join(unknown))
    notes.extend(eid + ": requested " + stamp["requested_model"] + ", observed " + stamp["observed_model"]
                 for eid, stamp in stamped if stamp.get("requested_model") and stamp.get("observed_model") not in
                 (None, "unknown", stamp["requested_model"]))
    # Work units: done needs passing evidence; a retry is a new unit; one claimant with a lease.
    for unit in task["work_units"]:
        label, claim = unit["id"], unit.get("claim")
        if unit["status"] == "done":
            errors.extend(label + ": marked done but acceptance " + aid + " is " + criteria[aid]["status"]
                          for aid in unit.get("acceptance_ids", []) if aid in criteria and criteria[aid]["status"] != "passed")
        if unit["status"] == "blocked" and "reason" not in unit:
            notes.append(label + ": blocked without a reason")
        if unit.get("retry_of") == label:
            errors.append(label + ": retry_of names itself")
        elif "retry_of" in unit and unit["retry_of"] not in indexes["work_units"]:
            errors.append(label + ": retry_of names no work unit: " + unit["retry_of"])
        if claim:
            try:
                expired = timestamp(claim["expires_at"]) <= now
            except ValueError:
                errors.append(label + ": claim.expires_at: not an ISO timestamp with a timezone")
                expired = False
            if unit["status"] == "planned" and claim["state"] in {"claimed", "lapsed"}:
                errors.append(label + ": a claimed unit is not queued (status planned); release it after inspecting the"
                              " worker's target")
            if claim["state"] == "inspected" and "inspection" not in claim:
                errors.append(label + ": claim inspected without saying what was inspected")
            if claim["state"] == "claimed" and expired:
                notes.append(label + ": lease held by " + claim["owner"] + " expired at " + claim["expires_at"]
                             + "; the expiry does not show the worker stopped. Inspect its target, record claim.state"
                             " inspected, then queue the unit again")
    # Actions: the text shown must contain the pinned target; open approvals and unmatched steps are listed.
    for action in task["actions"]:
        if "shown" in action and action["target"] not in action["shown"]:
            errors.append(action["id"] + ": the text shown to the person does not contain the pinned target")
        if action["decision"] == "pending":
            notes.append("open approval " + action["id"] + " (" + action["kind"] + " " + action["target"]
                         + (", request " + action["request_id"] if "request_id" in action else "") + ")")
    unmatched = [a for a in task["actions"] if a["outcome"] == "uncertain"]
    if unmatched:
        notes.append("unmatched steps (inspect each without replaying it): " + ", ".join(
            a["id"] + " (" + (", ".join(k + " " + a[k] for k in ("cause", "phase") if k in a) or "no cause recorded") + ")"
            for a in unmatched))
        bare = [a["id"] for a in unmatched if "cause" not in a]
        if bare:
            notes.append("uncertain steps without a cause: " + ", ".join(bare) + " (the cause picks the retry)")
    # Findings: a waiver holds only while the patch it was accepted at is the patch now.
    bare = []
    for finding in task["findings"]:
        snapshot_patch = finding.get("waived_patch_id")
        if snapshot_patch is not None and finding["adjudication"] != "deferred":
            errors.append(finding["id"] + ": a waiver snapshot applies only to a deferred finding")
        elif snapshot_patch is not None and snapshot_patch != task["patch_id"]:
            (errors if final else notes).append(
                finding["id"] + ": waiver lapsed (accepted at " + short(snapshot_patch) + ", patch is now "
                + short(task["patch_id"]) + "); the finding is open again, re-adjudicate it")
        elif snapshot_patch is None and finding["adjudication"] == "deferred":
            bare.append(finding["id"])
    if bare:
        notes.append("deferred findings without a waiver snapshot: " + ", ".join(bare)
                     + " (they will not lapse when the patch changes)")
    stop = task.get("stop")
    if stop and final:
        errors.append("completion contradicts stop: the task was stopped (" + stop["kind"] + "): " + stop["reason"])
    if stop:
        notes.append("stopped on purpose: do not resume without the user's say-so (" + stop["reason"] + ")"
                     if stop["kind"] == "on-purpose" else "interrupted: " + stop["reason"] + "; resume from next_safe_action")
    # Delegates: the clocks are absolute timestamps; a running delegate past its deadline reads budget-exhausted.
    for entry in task.get("delegates", []):
        times = {}
        for key in ("start_by", "deadline_at"):
            if key in entry:
                try:
                    times[key] = timestamp(entry[key])
                except ValueError:
                    errors.append(entry["id"] + ": " + key + ": not an ISO timestamp with a timezone")
        if len(times) == 2 and times["start_by"] > times["deadline_at"]:
            errors.append(entry["id"] + ": start_by is after deadline_at")
        if entry["status"] == "running" and "deadline_at" in times and times["deadline_at"] <= now:
            notes.append(entry["id"] + ": deadline_at passed (" + entry["deadline_at"] + ") while still running: read it"
                         " as budget-exhausted and record why")
    for event in task["history"]:
        errors.extend(event["id"] + ": resolves names no decision: " + name for name in event.get("resolves", [])
                      if name not in indexes["decisions"])
        if event.get("resolves") and not event.get("reason"):
            errors.append(event["id"] + ": resolves needs a reason")
    errors.extend(check_observations(task))
    errors.extend(check_decisions(task, notes))
    return errors


def check_observations(task):
    errors = []
    for observation in task.get("observations", []):
        label = observation["id"]
        if observation["kind"] != "memory-read":
            if "entries" in observation:
                errors.append(label + ": entries apply only to a memory-read observation")
            continue
        if "entries" not in observation:
            errors.append(label + ": a memory-read observation lists the entries it read (an empty list says it found none)")
        names = [entry["name"] for entry in observation.get("entries", [])]
        errors.extend(label + ": memory entry " + name + " is listed twice" for name in dict.fromkeys(names)
                      if names.count(name) > 1)
    return errors


def check_decisions(task, notes):
    """Decisions: driver and reasons (WB-15), lifecycle (WB-17), links (WB-18), confirmation (WB-14), memory (CM-56)."""
    errors, items = [], task.get("decisions", [])
    ids, criteria = {item["id"] for item in items}, {c["id"]: c for c in task["acceptance"]}
    snapshots = [o for o in task.get("observations", []) if o["kind"] == "memory-read"]
    known = {entry["name"] for o in snapshots for entry in o.get("entries", [])}
    named, undriven, unreasoned = {name for item in items for name in supersedes_ids(item)}, [], []
    for item in items:
        label, status = item["id"], item["status"]
        reasons = [r["alternative"] for r in item.get("alternative_reasons", [])]
        errors.extend(label + ": alternative_reasons names an alternative that is not listed: " + name
                      for name in dict.fromkeys(reasons) if name not in item["alternatives"])
        errors.extend(label + ": alternative_reasons repeats " + name for name in dict.fromkeys(reasons)
                      if reasons.count(name) > 1)
        missing = [name for name in item["alternatives"] if name not in reasons]
        if status == "proposed":
            notes.append("decision " + label + " is proposed: it binds nothing until the user accepts it")
            if "because" not in item:
                errors.append(label + ": a proposed decision states its driver (because)")
            if missing:
                errors.append(label + ": a proposed decision gives a reason for each alternative (missing: "
                              + ", ".join(missing) + ")")
        elif status != "rejected":
            if "because" not in item:
                undriven.append(label)
            if missing:
                unreasoned.append(label + " (" + ", ".join(missing) + ")")
        if status == "superseded" and label not in named:
            notes.append("decision " + label + " is superseded but no decision names it in supersedes (use deprecated"
                         " when nothing replaces it)")
        for relation in item.get("relations", []):
            if relation["target"] == label:
                errors.append(label + ": relations targets itself")
            elif relation["target"] not in ids:
                errors.append(label + ": relations targets unknown decision " + relation["target"])
        for name in item.get("cites_memory", []):
            if not snapshots:
                errors.append(label + ": cites memory entry " + name + " but the record holds no memory-read observation"
                              " (the citation cannot be audited)")
            elif name not in known:
                errors.append(label + ": cites memory entry " + name + " that is not in the recorded memory snapshot"
                              " (a fact saved after the read is not assumed to be in it)")
        confirmation = item.get("confirmation")
        if confirmation:
            wanted = confirmation.get("acceptance_id")
            if wanted is not None and wanted not in criteria:
                errors.append(label + ": confirmation.acceptance_id names no acceptance criterion: " + wanted)
            if status == "active":
                by = [e["id"] for e in task["evidence"]
                      if e["status"] == "passed" and supports(e, label) and same_content(e, task)]
                if by or (wanted in criteria and criteria[wanted]["status"] == "passed"):
                    notes.append("decision " + label + ": confirmed by " + (", ".join(by) if by else "acceptance " + wanted))
                else:
                    notes.append("decision " + label + ": decided but unconfirmed (check: " + confirmation["check"]
                                 + "); not implemented until a passing receipt names " + label
                                 + (" or acceptance " + wanted + " passes" if wanted else ""))
    if undriven:
        notes.append("decisions without a stated driver: " + ", ".join(undriven))
    if unreasoned:
        notes.append("alternatives without a reason: " + ", ".join(unreasoned))
    links = decision_links(task)
    if links:
        notes.append("decision links (derived): " + "; ".join(
            target + " " + ", ".join(label + " " + by for label, by in found) for target, found in links.items()))
    return errors


def version_parts(path):
    match = VERSION_NAME.fullmatch(pathlib.Path(path).name)
    if not match:
        raise ValueError("numbered records are named like task.0001.json: " + pathlib.Path(path).name)
    return match["stem"], int(match["number"]), len(match["number"])


def next_version(path):
    stem, number, width = version_parts(path)
    return pathlib.Path(path).with_name(stem + "." + str(number + 1).zfill(width) + ".json")


def check_chain(directory, last, notes=None, root=None):
    """Check every numbered version up to `last` against its predecessor; versions must be contiguous. Each
    version the helper writes carries the SHA-256 of the one before it (`previous_sha256`); a mismatch names the
    version whose link breaks. `notes` receives what the links cannot prove and any regression."""
    notes = [] if notes is None else notes
    directory = pathlib.Path(directory)
    root = directory if root is None else root
    stem, final_number, width = version_parts(last)
    found = {}
    for path in directory.iterdir():
        match = VERSION_NAME.fullmatch(path.name)
        if match and match["stem"] == stem:
            number = int(match["number"])
            if number in found:
                return ["two files number version " + str(number) + ": " + found[number].name + ", " + path.name]
            found[number] = path
    errors = ["missing version " + stem + "." + str(n).zfill(width) + ".json" for n in range(1, final_number + 1)
              if n not in found]
    if errors:
        return errors
    if found[final_number].resolve() != pathlib.Path(last).resolve():
        return ["--chain folder does not contain the checked record " + pathlib.Path(last).name]
    previous, linked, unlinked, last_pass = None, 0, [], {}
    for number in range(1, final_number + 1):
        path = found[number]
        record = read_json(path)
        problems = shape(record, CONTRACT["root"])
        if problems:
            errors.extend(path.name + ": " + x for x in problems)
            break
        if previous is not None:
            errors.extend(path.name + ": " + x for x in check_previous(previous, record))
            state = link_state(record, previous, found[number - 1])
            if state == "broken":
                errors.append(path.name + ": previous_sha256 does not match " + found[number - 1].name
                              + " (that version changed after this one was written)")
            linked += state == "linked"
            if state == "unlinked":
                unlinked.append(path.name)
        if number == final_number:
            notes.extend(regression_note(last_pass[c["id"]][0], c, record, last_pass[c["id"]][1], root,
                                         last_pass[c["id"]][2])
                         for c in record["acceptance"] if c["status"] == "failed" and c["id"] in last_pass)
        last_pass.update({c["id"]: (c, record["patch_id"], path.name) for c in record["acceptance"]
                          if c["status"] == "passed"})
        previous = record
    if final_number > 1 and not errors:
        if not linked:
            notes.append("no version carries previous_sha256, so an edit to an earlier version cannot be detected")
        else:
            notes.append("chain links hold for " + str(linked) + " of " + str(final_number - 1) + " versions"
                         + ("; unlinked (hand-written or copied): " + ", ".join(unlinked) if unlinked else "")
                         + ". A link shows continuity only: the newest version could be deleted undetected and it does"
                         " not show who wrote any version")
    return errors


def open_records(target, task_id):
    """The newest version of each numbered record beside `target` that carries `task_id`, as (path, record)."""
    newest, folder = {}, pathlib.Path(target).parent
    for path in (folder.iterdir() if folder.is_dir() else ()):
        match = VERSION_NAME.fullmatch(path.name)
        if not match:
            continue
        try:
            record = read_json(path)
        except (OSError, ValueError):
            continue
        number = int(match["number"])
        if isinstance(record, dict) and record.get("id") == task_id and number > newest.get(match["stem"], (0,))[0]:
            newest[match["stem"]] = (number, path, record)
    return [(path, record) for _, path, record in sorted(newest.values(), key=lambda item: str(item[1]))]


def start_task(args):
    """Create an incomplete canonical record; flags record scope, never grant it. The task id is the key: a repeated
    start returns the open record, the same id with another goal is an error naming both, and a record that ended
    (delivered or complete) frees its id."""
    root = pathlib.Path(args.root).resolve(strict=True)
    target = pathlib.Path(args.path).resolve()
    if not root.is_dir() or not target.is_relative_to(root):
        raise ValueError("task output must be inside the caller-selected evidence root")
    for path, held in open_records(target, args.task_id):
        if held.get("state") == "delivered" or held.get("completion") == "complete":
            continue
        if str(held.get("goal")).strip() != args.goal.strip():
            raise ValueError("task id " + args.task_id + " is already open in " + path.name + " with goal '"
                             + str(held.get("goal")) + "'; this start gives goal '" + args.goal + "'. Use another"
                             " --task-id, or ask the user whether to supersede it")
        return {"status": "existing-open", "path": str(path), "sha256": digest(path), "state": held.get("state"),
                "claim": "an open record already holds this task id and goal; nothing was written"}
    allowed = list(dict.fromkeys(args.allow_action))
    forbidden = list(dict.fromkeys(args.forbid_action))
    overlap = sorted(set(allowed) & set(forbidden))
    if overlap:
        raise ValueError("action kinds both allowed and forbidden: " + ", ".join(overlap))
    if any(not portable(prefix) for prefix in args.allow_path + args.observe_path):
        raise ValueError("allowed and observed paths must be portable paths relative to the repository")
    paths = list(dict.fromkeys(args.allow_path))
    observed_paths = list(dict.fromkeys(paths + args.observe_path))
    ignore = check_excludes(([] if args.no_default_excludes else DEFAULT_EXCLUDE) + args.exclude)
    revision, patch, notes, observed = args.revision, args.patch, [], None
    if args.repo:
        observed = fingerprint(args.repo, observed_paths, exclude=[root], ignore=ignore)
        if patch and patch != observed["patch"]:
            raise ValueError("--patch differs from the repository fingerprint")
        patch = observed["patch"]
        revision, problems, notes = resolve_revision(args.repo, args.revision)
        if problems:
            raise ValueError("; ".join(problems))
    if not revision or not patch:
        raise ValueError("pass --repo (with --revision when the folder has no readable .git), "
                         "or both --revision and --patch")
    if any(not value.strip() for value in (args.goal, revision, args.scope, args.author, args.task_id, *args.non_goal)):
        raise ValueError("goal, identity, non-goals and observed context must be nonempty")
    if not re.fullmatch(r"[a-f0-9]{64}", patch):
        raise ValueError("patch must be the host-observed lowercase SHA-256 (see fingerprint)")
    record = dict(schema_version=1, id=args.task_id, mode=args.task_mode, size=args.size,
        goal=args.goal, non_goals=list(dict.fromkeys(args.non_goal)), scope_id=args.scope, revision=revision,
        patch_id=patch, author_id=args.author, base_revision=revision,
        authority=dict(allowed_actions=allowed, forbidden_actions=forbidden, allowed_paths=paths),
        fingerprint=dict(paths=observed_paths, exclude=ignore, baseline=patch),
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
    write_new(target, record)
    result = {"status": "created-incomplete", "path": str(target), "verification": "unverified",
              "patch_id": patch, "revision": revision,
              "claim": "canonical task scaffold only; no host permission granted or work executed"}
    if observed:
        result.update(files=observed["files"], missing=observed["missing"], manifest=store_manifest(root, observed))
    if notes:
        result["notes"] = notes
    return result


def task_context(args, task):
    """Observed context: --repo recomputes patch (and HEAD when readable) from disk."""
    context = {"revision": args.revision, "scope_id": args.scope, "patch_id": args.patch}
    errors, notes, observed = [], [], None
    if args.repo and not shape(task, CONTRACT["root"]):
        paths, ignore = definition(task, args.paths)
        observed = fingerprint(args.repo, paths, exclude=[args.root], ignore=ignore)
        if args.patch and args.patch != observed["patch"]:
            errors.append("--patch differs from the repository fingerprint")
        context["patch_id"] = observed["patch"]
        if observed["missing"]:
            notes.append("observed paths missing on disk: " + ", ".join(observed["missing"]))
        revision, problems, more = resolve_revision(args.repo, args.revision)
        errors += problems
        notes += more
        context["revision"] = revision
    if "waiting_on" in task and not shape(task, CONTRACT["root"]):
        notes += waiting_notes(task, args.repo)
    if not shape(task, CONTRACT["root"]):
        # A passed receipt whose check definition changed is stale though the patch is identical (refresh marks it).
        defined = [e for e in task["evidence"] if "definition" in e and e["status"] == "passed"]
        for receipt in (defined if args.repo else []):
            drift = definition_drift(receipt, args.repo)
            if drift:
                errors.append(receipt["id"] + ": check definition changed since the receipt ran (" + drift
                              + "); refresh marks it stale")
        if defined and not args.repo:
            notes.append("definition: the check definition of " + ", ".join(e["id"] for e in defined)
                         + " is not evaluated without --repo")
        if getattr(args, "previous", None) and "previous_sha256" in task:
            before = read_json(args.previous)
            if isinstance(before, dict) and link_state(task, before, args.previous) == "broken":
                errors.append("previous_sha256 does not match " + pathlib.Path(args.previous).name
                              + " (that version changed after this one was written)")
    return context, errors, notes, observed


def waiting_notes(task, repo=None):
    """What resume reports for a waiting record: what it waits for, whether the wait expired and, for the two
    local check kinds, whether the check holds. Reads at most one file under `repo`; runs nothing and never
    decides to dispatch."""
    waiting = task.get("waiting_on")
    if not waiting:
        return []
    check = waiting["check"]
    kind, target = check["kind"], check["target"]
    notes = ["waiting: " + waiting["what"] + "; check " + kind + " " + target + "; next step: " + waiting["next_step"]
             + "; expires " + waiting["expires_at"] + ". Resume re-checks this and never re-dispatches the job."]
    try:
        if timestamp(waiting["expires_at"]) <= dt.datetime.now(dt.timezone.utc):
            notes.append("waiting: expired at " + waiting["expires_at"]
                         + "; ask the user whether to keep waiting. Do not re-dispatch.")
    except ValueError:
        pass
    if kind not in {"file-exists", "hash-matches"}:
        notes.append("waiting: the helper does not evaluate " + kind + " checks; run it yourself before acting")
        return notes
    if repo is None:
        notes.append("waiting: the " + kind + " check is not evaluated without --repo; run it yourself")
        return notes
    try:
        path = safe_path(repo, target)
    except ValueError:
        notes.append("waiting: " + target + " is not a safe repository path; the check was not evaluated")
        return notes
    except OSError as exc:
        notes.append("waiting: the check could not be evaluated (" + str(exc) + ")")
        return notes
    try:
        if not path.is_file():
            holds, detail = False, target + " is not there"
        elif kind == "hash-matches" and digest(path) != check.get("sha256"):
            holds, detail = False, target + " differs from the recorded SHA-256"
        else:
            holds, detail = True, target + (" matches the recorded SHA-256" if kind == "hash-matches" else " exists")
    except (OSError, ValueError) as exc:
        notes.append("waiting: the check could not be evaluated (" + str(exc) + ")")
        return notes
    notes.append("waiting: check is true (" + detail + "); the wait is over, continue from the next step" if holds
                 else "waiting: check is false (" + detail + "); still waiting, dispatch nothing")
    return notes


def resolve_into_root(path, root):
    """(relative path, sha256) for a file inside the evidence root; files elsewhere are snapshotted in."""
    path = pathlib.Path(path).resolve(strict=True)
    if path.is_relative_to(root):
        relative = path.relative_to(root).as_posix()
        safe_path(root, relative)
        return relative, digest(path)
    copied = snapshot(path, root)
    return copied["path"], copied["sha256"]


def load_version(args):
    root = pathlib.Path(args.root).resolve(strict=True)
    source = pathlib.Path(args.path).resolve(strict=True)
    record = read_json(source)
    problems = shape(record, CONTRACT["root"])
    if problems:
        raise ValueError("record is malformed: " + "; ".join(problems))
    target = next_version(source)
    if not target.is_relative_to(root):
        raise ValueError("numbered records must live inside the evidence root")
    if os.path.lexists(target):
        raise ValueError("next version already exists; never replaced: " + target.name)
    return root, source, record, target


def add_receipt(args):
    """Append one receipt to the next numbered version. Computes hashes; runs nothing."""
    root, source, record, target = load_version(args)
    previous = copy.deepcopy(record)
    paths, ignore = definition(record)
    observed = fingerprint(args.repo, paths, exclude=[root], ignore=ignore)
    before = getattr(args, "patch_before", None)
    if before is not None and not re.fullmatch(r"[a-f0-9]{64}", before):
        raise ValueError("--patch-before must be the lowercase SHA-256 that `validate.py fingerprint` printed")
    if before is not None and before != observed["patch"]:
        raise ValueError("receipt void: the observed paths changed while the check ran (before " + short(before)
                         + ", after " + short(observed["patch"]) + "); nothing written. Rerun the check on unchanged paths")
    if observed["patch"] != record["patch_id"]:
        raise ValueError("the repository no longer matches the record's patch (record " + short(record["patch_id"])
                         + ", observed " + short(observed["patch"]) + "); run validate.py refresh first")
    revision, problems, notes = resolve_revision(args.repo, args.revision)
    if problems:
        raise ValueError("; ".join(problems))
    if args.id in {e["id"] for e in record["evidence"]}:
        raise ValueError("receipt id already used: " + args.id)
    unrun = args.status in {"not-run", "blocked"}
    if not unrun and (args.raw is None or args.artifact is None):
        raise ValueError("--raw and --artifact are required for a receipt that ran")
    limits = list(args.limitation)
    option = lambda name: getattr(args, name, None)  # callers built before the optional flags omit them
    reason_code = option("reason_code")
    if args.status in UNFINISHED and not reason_code and not limits:
        raise ValueError("a blocked, not-run or inconclusive receipt names why: pass --reason-code (or at least one "
                         "--limitation); with neither it would count as no-reason-given")
    if before is not None and not unrun:
        limits.append("observed paths fingerprinted before and after the run, both " + before + "; two endpoint "
                      "samples cannot see a change made and then restored")
    elif not unrun:
        notes.append("no --patch-before: the observed paths were not fingerprinted before the check, so an edit "
                     "made while it ran would not be seen")
    raw, raw_sha = resolve_into_root(args.raw, root) if args.raw else (None, None)
    artifact, artifact_sha = resolve_into_root(args.artifact, root) if args.artifact else (None, None)
    executed = args.passed + args.failed
    status = args.status or ("failed" if args.failed or (args.exit is not None and args.exit != args.expected_exit)
                             else "passed")
    claims = list(dict.fromkeys(args.claim))
    receipt = dict(id=args.id, claim_id=claims[0], type=args.type, revision=revision or record["revision"],
                   patch_id=record["patch_id"], scope_id=record["scope_id"], artifact=artifact,
                   artifact_sha256=artifact_sha, operation=args.operation, environment=args.environment,
                   raw_output=raw, raw_sha256=raw_sha,
                   recorded_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                   status=status, collected=executed + args.skipped, executed=executed, passed=args.passed,
                   failed=args.failed, skipped=args.skipped, exit_code=args.exit, expected_exit=args.expected_exit,
                   negative_control=args.control, coverage=args.coverage or "as recorded in the raw output",
                   limitations=limits)
    if len(claims) > 1:
        receipt["claim_ids"] = claims
    if reason_code:
        receipt["reason"] = {key: value for key, value in (("code", reason_code), ("observed", option("reason_observed")),
                                                           ("limit", option("reason_limit"))) if value}
    files = list(dict.fromkeys(option("definition_path") or []))
    if files or option("tool_version"):
        # The definition covers the command text, the expected exit and the bytes of the files that define the check.
        hashed = [(path, digest(safe_path(args.repo, path))) for path in files]
        receipt["definition"] = dict(sha256=definition_hash(args.operation, args.expected_exit, hashed),
                                     tool_version=option("tool_version") or "unknown", paths=files)
    if any(option(name) for name in ("producer_tool", "producer_context", "requested_model", "observed_model")):
        if not option("producer_tool"):
            raise ValueError("a producer stamp needs --producer-tool (and --producer-context); it is a claim, not a signature")
        receipt["producer"] = dict(tool=option("producer_tool"), context_id=option("producer_context") or "unknown",
                                   **({"requested_model": option("requested_model")} if option("requested_model") else {}),
                                   observed_model=option("observed_model") or "unknown")
    problems = shape(receipt, CONTRACT["$defs"]["evidence"]) or check_receipt(receipt, root) \
        or evidence_option_errors(receipt)
    if args.control and args.control not in {e["id"] for e in record["evidence"]}:
        problems.append("unknown negative control receipt: " + args.control)
    if problems:
        raise ValueError("receipt not written: " + "; ".join(problems))
    record["evidence"].append(receipt)
    record["previous_sha256"] = digest(source)
    if args.link:
        criteria = {c["id"]: c for c in record["acceptance"]}
        for claim in claims:
            criterion = criteria.get(claim)
            if criterion is None:
                notes.append("--link: " + claim + (" is a decision; a receipt that names it confirms it, so there is "
                                                   "nothing to link" if claim in {d["id"] for d in record.get("decisions", [])}
                                                   else " is not an acceptance criterion; left unlinked"))
            elif status == "passed":
                criterion["evidence_ids"] = [e["id"] for e in record["evidence"] if e["status"] == "passed"
                                             and supports(e, claim) and same_content(e, record)]
                criterion["status"] = "passed"
            elif status in {"failed", "inconclusive"}:
                criterion["evidence_ids"] = list(dict.fromkeys(criterion["evidence_ids"] + [args.id]))
                criterion["status"] = status
    store_manifest(root, observed)
    context = {"revision": revision, "scope_id": record["scope_id"], "patch_id": observed["patch"]}
    errors = check_task(record, root, context, previous, notes)
    write_new(target, record)
    return {"status": "failed" if errors else "passed", "path": str(target), "receipt": args.id,
            "receipt_status": status, "errors": errors, "notes": notes}


def refresh(args):
    """Write the next version bound to the observed context; stale receipts and reset verification as needed."""
    root, source, record, target = load_version(args)
    previous = copy.deepcopy(record)
    scope = args.scope or record["scope_id"]
    scope_changed = scope != record["scope_id"]
    grants = list(dict.fromkeys(args.grant))
    if (scope_changed or grants or args.relax) and not args.reason:
        raise ValueError("--reason is required for a scope change, a grant or a relaxation")
    if args.relax and not scope_changed:
        raise ValueError("--relax needs --scope: finish conditions only relax under a new scope")
    for kind in grants:
        if kind in record["authority"]["forbidden_actions"]:
            raise ValueError("cannot grant a forbidden action: " + kind)
        if kind not in record["authority"]["allowed_actions"]:
            record["authority"]["allowed_actions"].append(kind)
    paths, ignore = definition(record)
    paths = list(dict.fromkeys(paths + args.observe_path))
    widened = [item for item in args.exclude if not covers(ignore, item)]
    if widened and not scope_changed:
        raise ValueError("--exclude widens what the fingerprint ignores (" + ", ".join(widened) + "), which is a "
                         "relaxation: pass --scope and --reason")
    ignore = check_excludes(ignore + args.exclude)
    observed = fingerprint(args.repo, paths, exclude=[root], ignore=ignore)
    revision, problems, notes = resolve_revision(args.repo, args.revision)
    if problems:
        raise ValueError("; ".join(problems))
    stored = record.get("fingerprint", {})
    record["fingerprint"] = dict(paths=paths, exclude=ignore, baseline=stored.get("baseline", record["patch_id"]))
    old_patch = record["patch_id"]
    record.update(revision=revision or record["revision"], patch_id=observed["patch"], scope_id=scope,
                  previous_sha256=digest(source))
    staled = []
    for receipt in record["evidence"]:
        # A receipt goes stale when the patch or scope moved, or when its recorded check definition changed.
        if receipt["status"] == "passed" and (not same_content(receipt, record) or definition_drift(receipt, args.repo)):
            receipt["status"] = "stale"
            staled.append(receipt["id"])
    evidence = {e["id"]: e for e in record["evidence"]}
    reset = []
    for criterion in record["acceptance"]:
        if criterion["status"] == "passed" and any(evidence[x]["status"] != "passed" or not same_content(evidence[x], record)
                                                   for x in criterion["evidence_ids"] if x in evidence):
            criterion["status"] = "not-run"
            reset.append(criterion["id"])
    for item in args.relax:
        criteria = {c["id"]: c for c in record["acceptance"]}
        if item in criteria:
            criteria[item]["required"] = False
        elif item in {w["id"] for w in record["work_units"]}:
            record["work_units"] = [w for w in record["work_units"] if w["id"] != item]
        elif item in {r["id"] for r in record["reviews"]}:
            record["reviews"] = [r for r in record["reviews"] if r["id"] != item]
        elif item == "independent-review":
            record["independent_review_required"] = False
        else:
            raise ValueError("--relax names no acceptance criterion, work unit or review: " + item)
    for action in record["actions"]:
        if action["scope_id"] != scope and action["outcome"] == "not-applied" and action["decision"] in {"pending", "approved"}:
            action["decision"] = "stale"
    state = record["state"]
    moved = bool(reset or staled or scope_changed)
    if moved and record["verification"] != "unverified":
        record["verification"] = "unverified"
    to = {"verified": "implemented", "delivered": "inspected"}.get(state, state) if moved else state
    if moved and record["completion"] == "complete":
        record["completion"] = "open"
    reason = args.reason or ("refresh: patch " + short(old_patch) + " -> " + short(observed["patch"])
                             + ", revision " + str(previous["revision"]) + " -> " + str(record["revision"])
                             + "; " + str(len(staled)) + " receipts stale")
    used = {e["id"] for e in record["history"]}
    eid = "refresh-" + str(version_parts(target)[1])
    while eid in used:
        eid += "x"
    event = {"id": eid, "from": state, "to": to, "scope_id": scope, "patch_id": observed["patch"], "reason": reason}
    if grants:
        event["grants"] = grants
    record["history"].append(event)
    record["state"] = to
    if reset:
        record["next_safe_action"] = "Re-run acceptance checks on the current patch: " + ", ".join(reset)
    store_manifest(root, observed)
    context = {"revision": record["revision"], "scope_id": scope, "patch_id": observed["patch"]}
    errors = check_task(record, root, context, previous, notes)
    write_new(target, record)
    return {"status": "failed" if errors else "passed", "path": str(target), "stale_receipts": staled,
            "reset_acceptance": reset, "state": to, "errors": errors, "notes": notes}


def receipt_options(parser):
    """The receipt flags for the optional evidence objects: reason code, check definition and producer stamp."""
    parser.add_argument("--reason-code", choices=REASON_CODES, help="why a blocked, not-run or inconclusive receipt did not finish")
    parser.add_argument("--reason-observed", help="the value seen, such as '130 s' (timeout and cap-reached record it and the limit)")
    parser.add_argument("--reason-limit", help="the limit it hit, such as '120 s'")
    parser.add_argument("--tool-version", help="version of the tool that ran the check; stored with the check definition")
    parser.add_argument("--definition-path", action="append", default=[],
                        help="repository file that defines the check (rules, expected output); editing it stales the receipt")
    parser.add_argument("--producer-tool", help="self-declared producer of the receipt (a claim, not a signature)")
    parser.add_argument("--producer-context", help="self-declared context id of the producer")
    parser.add_argument("--requested-model")
    parser.add_argument("--observed-model", help="model seen at run time; recorded as unknown when not given")
