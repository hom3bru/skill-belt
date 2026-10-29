"""westack consistency checks. No task execution, permission grant or truth certification."""
import argparse
import copy
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
NON_EXECUTION = {"source", "review"}
LIMIT = 8 * 1024 * 1024
REPARSE_POINT = 0x400
# Only name-surrogate reparse points are links; cloud placeholders and other tags are hashed.
LINK_TAGS = {getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C), getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)}
# Wire-format identifiers predate the rename to westack and stay fixed: changing them would change
# every recorded patch_id and stored manifest.
FINGERPRINT_HEADER = b"estack-fingerprint-v1\n"
ALWAYS_SKIP = {".git"}
# Caches and dependencies that runs rewrite. A record's fingerprint.exclude overrides this list;
# .git and the evidence root are always skipped.
DEFAULT_EXCLUDE = [".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", ".mypy_cache",
                   ".tox", "dist", "build", ".next"]
MANIFEST_FORMAT = "estack-manifest-v1"
VERSION_NAME = re.compile(r"(?P<stem>.+)\.(?P<number>\d+)\.json")
GIT_OBJECT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
GIT_REF = re.compile(r"refs/[A-Za-z0-9._+/-]+")
FRONT_MATTER_KEYS = {"name", "description", "metadata", "disable-model-invocation", "license", "allowed-tools",
                     "compatibility"}
FRONT_MATTER_NESTED = {"metadata", "allowed-tools"}
# Between snapshots, adjudication, requirement and decision status only move forward.
ADJUDICATION_NEXT = {"open": {"accepted", "rejected", "deferred", "fixed"}, "accepted": {"deferred", "fixed"},
                     "deferred": {"fixed"}, "rejected": set(), "fixed": set()}
REQUIREMENT_NEXT = {"active": {"parked", "superseded"}, "parked": {"active", "superseded"}, "superseded": set()}
DECISION_NEXT = {"active": {"superseded"}, "superseded": set()}


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


def read_small_text(path):
    path = pathlib.Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("not a regular file: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("metadata file exceeds 8 MiB: " + path.name)
    return raw.decode("utf-8")


def write_new(path, data):
    """Exclusive create; an existing file is never replaced."""
    path = pathlib.Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")


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


def portable(relative):
    """A repository-relative slash path, or "." for the whole repository."""
    return isinstance(relative, str) and (relative == "." or scope_path(relative, [relative]))


def within(relative, allowed):
    return "." in allowed or (relative != "." and scope_path(relative, allowed))


def is_link(info):
    # Symlinks, and on Windows symlink or junction reparse points only.
    if stat.S_ISLNK(info.st_mode):
        return True
    if getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
        return getattr(info, "st_reparse_tag", None) in LINK_TAGS
    return False


def check_excludes(ignore):
    """Exclude entries are names (matched at any depth) or portable repository-relative paths."""
    for item in ignore:
        if not isinstance(item, str) or item in {"", ".", ".."} or not portable(item):
            raise ValueError("invalid fingerprint exclude: " + str(item))
    return list(dict.fromkeys(ignore))


def fingerprint_hash(entries):
    result = hashlib.sha256(FINGERPRINT_HEADER)
    for relative in sorted(entries):
        result.update((relative + "\0" + entries[relative] + "\n").encode("utf-8"))
    return result.hexdigest()


def fingerprint(repo, paths=None, exclude=(), ignore=None):
    """Observed state of the files under `paths` (relative to `repo`).

    SHA-256 over the header line followed by sorted lines of
    "<posix path>\\0<file sha256>\\n". Names in `ignore` (default
    DEFAULT_EXCLUDE) are skipped at any depth and entries containing "/" as
    repository-relative paths; `.git` and any `exclude` evidence root are
    always skipped. A link is recorded by its target text and never followed;
    a requested path that does not exist is recorded as missing. Zero hashed
    files is an error, as is an evidence root that equals or contains a
    requested path. Reads files only.
    """
    repo = pathlib.Path(repo).resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("repository must be a directory: " + str(repo))
    paths = list(dict.fromkeys(paths or ["."]))
    for relative in paths:
        if not portable(relative):
            raise ValueError("nonportable fingerprint path: " + str(relative))
    ignore = check_excludes(DEFAULT_EXCLUDE if ignore is None else ignore)
    skip_names = {x for x in ignore if "/" not in x} | ALWAYS_SKIP
    skip_paths = [repo.joinpath(*x.split("/")) for x in ignore if "/" in x]
    excluded = []
    for item in exclude:
        if item is None:
            continue
        resolved = pathlib.Path(item).resolve()
        if resolved == repo:
            raise ValueError("evidence root must not be the repository root; use a subdirectory or an outside folder")
        if resolved.is_relative_to(repo):
            for relative in paths:
                target = repo if relative == "." else repo.joinpath(*relative.split("/"))
                if target == resolved or target.is_relative_to(resolved):
                    raise ValueError("evidence root " + str(resolved) + " equals or contains fingerprint path "
                                     + relative + "; keep evidence outside the observed paths")
            excluded.append(resolved)
    entries, missing = {}, []

    def skipped(path):
        return (path.name in skip_names or any(path == x or path.is_relative_to(x) for x in skip_paths)
                or any(path == x or path.is_relative_to(x) for x in excluded))

    def record(path, info):
        relative = path.relative_to(repo).as_posix()
        if stat.S_ISLNK(info.st_mode) or (stat.S_ISDIR(info.st_mode) and is_link(info)):
            try:
                target = str(os.readlink(path)).replace("\\", "/")
            except OSError:
                target = "?"
            entries[relative] = "link:" + target
            return False
        if stat.S_ISREG(info.st_mode):
            entries[relative] = digest(path)
            return False
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("non-regular file in fingerprint: " + relative)
        return True

    for relative in paths:
        parts = [] if relative == "." else relative.split("/")
        cursor, info = repo, repo.lstat()
        for index, part in enumerate(parts):
            cursor = cursor / part
            try:
                info = cursor.lstat()
            except FileNotFoundError:
                info = None
                break
            if index < len(parts) - 1 and is_link(info):
                raise ValueError("fingerprint path passes through a link: " + relative)
        if info is None:
            missing.append(relative)
            entries.setdefault(relative, "missing")
            continue
        if skipped(cursor) or not record(cursor, info):
            continue
        for directory, folders, names in os.walk(cursor, followlinks=False):
            here = pathlib.Path(directory)
            keep = []
            for name in sorted(folders):
                child = here / name
                if not skipped(child) and record(child, child.lstat()):
                    keep.append(name)
            folders[:] = keep
            for name in sorted(names):
                child = here / name
                if not skipped(child):
                    record(child, child.lstat())
    files = sum(1 for x in entries.values() if GIT_OBJECT.fullmatch(x))
    if not files:
        raise ValueError("zero files fingerprinted under " + ", ".join(paths)
                         + (" (missing: " + ", ".join(missing) + ")" if missing else "")
                         + "; the record would be blind to edits. Check the paths, excludes and evidence root")
    return {"patch": fingerprint_hash(entries), "files": files, "paths": paths, "missing": missing,
            "exclude": ignore, "entries": entries}


def definition(task, override_paths=None):
    """The fingerprint definition a record observes: (paths, excludes)."""
    stored = task.get("fingerprint")
    paths = override_paths or (stored["paths"] if stored else None) or task["authority"]["allowed_paths"] or ["."]
    return list(paths), (list(stored["exclude"]) if stored else list(DEFAULT_EXCLUDE))


def plain_folder(root, name):
    folder = root / name
    if os.path.lexists(folder):
        info = folder.lstat()
        if is_link(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(name + " must be a plain directory inside the evidence root")
    else:
        folder.mkdir()
    return folder


def store_manifest(root, observed):
    """Keep per-file hashes as manifests/<patch>.json (exclusive create; self-verifying)."""
    root = pathlib.Path(root).resolve(strict=True)
    plain_folder(root, "manifests")
    relative = "manifests/" + observed["patch"] + ".json"
    target = safe_path(root, relative)
    if os.path.lexists(target):
        if load_manifest(root, observed["patch"]) != observed["entries"]:
            raise ValueError("existing manifest does not match its patch; refusing to replace: " + relative)
        return relative
    write_new(target, {"format": MANIFEST_FORMAT, "patch": observed["patch"], "entries": observed["entries"]})
    return relative


def load_manifest(root, patch):
    """Entries of a stored manifest, None when absent; a manifest whose entries do not hash to its name is an error."""
    if not isinstance(patch, str) or not re.fullmatch(r"[a-f0-9]{64}", patch):
        return None
    path = pathlib.Path(root) / "manifests" / (patch + ".json")
    if not path.is_file():
        return None
    data = read_json(path)
    if (not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT or data.get("patch") != patch
            or not isinstance(data.get("entries"), dict) or fingerprint_hash(data["entries"]) != patch):
        raise ValueError("manifest does not hash to its patch: manifests/" + patch + ".json")
    return data["entries"]


def diff_entries(old, new):
    return {"added": sorted(set(new) - set(old)), "modified": sorted(k for k in set(old) & set(new) if old[k] != new[k]),
            "removed": sorted(set(old) - set(new))}


def git_location(repo):
    """The folder holding .git at or above `repo`, or None."""
    repo = pathlib.Path(repo).resolve(strict=True)
    for folder in (repo, *repo.parents):
        if (folder / ".git").exists():
            return folder
    return None


def git_revision(repo):
    """Read HEAD from disk without running Git, searching upward for .git. None means no Git work tree.

    Handles a .git directory or a worktree/submodule `.git` file pointer,
    `commondir`, loose refs, packed-refs and a detached HEAD. Raises ValueError
    for anything else (for example reftable storage or an unborn branch); use
    `git rev-parse HEAD` then.
    """
    location = git_location(repo)
    if location is None:
        return None
    marker = location / ".git"
    if marker.is_dir():
        gitdir = marker
    elif marker.is_file():
        text = read_small_text(marker).strip()
        if not text.startswith("gitdir:"):
            raise ValueError("unrecognized .git file")
        pointer = pathlib.Path(text[len("gitdir:"):].strip())
        gitdir = (pointer if pointer.is_absolute() else location / pointer).resolve(strict=True)
    else:
        raise ValueError("unrecognized .git entry")
    common = gitdir
    if (gitdir / "commondir").is_file():
        pointer = pathlib.Path(read_small_text(gitdir / "commondir").strip())
        common = (pointer if pointer.is_absolute() else gitdir / pointer).resolve(strict=True)
    value = read_small_text(gitdir / "HEAD").strip()
    for _ in range(5):
        if GIT_OBJECT.fullmatch(value):
            return value
        if not value.startswith("ref:"):
            raise ValueError("unrecognized HEAD content")
        ref = value[len("ref:"):].strip()
        if not GIT_REF.fullmatch(ref) or any(part in {"", ".", ".."} for part in ref.split("/")):
            raise ValueError("unsupported ref name: " + ref)
        value = None
        for base in dict.fromkeys((gitdir, common)):
            loose = base.joinpath(*ref.split("/"))
            if loose.is_file():
                value = read_small_text(loose).strip()
                break
        packed = common / "packed-refs"
        if value is None and packed.is_file():
            for line in read_small_text(packed).splitlines():
                if line and not line.startswith(("#", "^")):
                    object_id, _, name = line.partition(" ")
                    if name.strip() == ref:
                        value = object_id.strip()
                        break
        if value is None:
            raise ValueError("ref not found (unborn branch or unsupported ref storage): " + ref)
    raise ValueError("symbolic ref chain too deep")


def resolve_revision(repo, supplied):
    """(revision, errors, notes) from Git on disk and an optional caller label; never silent."""
    errors, notes = [], []
    repo = pathlib.Path(repo).resolve(strict=True)
    location = git_location(repo)
    try:
        head = git_revision(repo)
    except (OSError, ValueError) as exc:
        if supplied:
            notes.append("cannot read .git (" + str(exc) + "); using the supplied --revision")
            return supplied, errors, notes
        errors.append("cannot read revision from .git (" + str(exc) + "); pass --revision from git rev-parse HEAD")
        return None, errors, notes
    if head is None:
        if not supplied:
            notes.append("no .git found at or above " + str(repo) + "; pass --revision (no-vcs outside Git)")
        return supplied, errors, notes
    if location != repo:
        if supplied and supplied != head:
            notes.append("--repo has no .git of its own; using the supplied --revision label " + supplied
                         + " (enclosing work tree " + str(location) + " is at " + head + ")")
            return supplied, errors, notes
        notes.append("Git root found at " + str(location))
    elif supplied and supplied != head:
        errors.append("--revision differs from the repository HEAD")
    return head, errors, notes


def observe(repo, paths, root=None, ignore=None):
    result = fingerprint(repo, paths, exclude=[root] if root else [], ignore=ignore)
    location = git_location(repo)
    result["git_root"] = str(location) if location else None
    try:
        result["revision"] = git_revision(repo)
        if result["revision"] is None:
            result["revision_error"] = "no .git found at or above " + str(pathlib.Path(repo).resolve()) \
                                       + "; pass --revision (no-vcs outside Git)"
    except (OSError, ValueError) as exc:
        result["revision"] = None
        result["revision_error"] = str(exc) + "; use git rev-parse HEAD"
    return result


def snapshot(source, root):
    """Copy a file to <root>/snapshots/<sha256><suffix> by exclusive create; never replace."""
    root = pathlib.Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("evidence root must be a directory")
    source = pathlib.Path(source)
    value = digest(source)
    suffix = source.suffix if re.fullmatch(r"\.[A-Za-z0-9_-]{1,16}", source.suffix) else ""
    relative = "snapshots/" + value + suffix
    plain_folder(root, "snapshots")
    target = safe_path(root, relative)
    if os.path.lexists(target):
        if digest(target) != value:
            raise ValueError("existing snapshot does not match its digest; refusing to replace: " + relative)
        return {"status": "reused", "path": relative, "sha256": value}
    copied = hashlib.sha256()
    with source.open("rb") as reader, target.open("xb") as writer:
        for chunk in iter(lambda: reader.read(128 * 1024), b""):
            copied.update(chunk)
            writer.write(chunk)
    if copied.hexdigest() != value:
        target.unlink()  # only the file this call just created
        raise ValueError("source changed while copying; snapshot discarded")
    return {"status": "created", "path": relative, "sha256": value}


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
    if observed == "applied" and action["decision"] != "approved":
        return "report-unauthorized-effect"
    if action["decision"] == "denied" or action["outcome"] == "denied":
        return "stop-denied"
    if action["outcome"] == "applied" or observed == "applied":
        return "do-not-replay"
    if action["outcome"] == "uncertain":
        return "refresh-authority-before-retry" if observed == "not-applied" else "inspect-without-replay"
    return "refresh-authority-before-retry"


def supports(evidence, claim):
    """A receipt backs its claim_id and any listed claim_ids."""
    return evidence["claim_id"] == claim or claim in evidence.get("claim_ids", [])


def same_content(item, task):
    """Staleness follows content and authority: patch fingerprint and scope, not the commit."""
    return (item["patch_id"], item["scope_id"]) == (task["patch_id"], task["scope_id"])


def check_receipt(evidence, root):
    errors = []
    label = evidence["id"]
    status = evidence["status"]
    if status in {"not-run", "blocked"}:
        if evidence["executed"] or evidence["passed"] or evidence["failed"] or evidence["exit_code"] is not None:
            errors.append(label + ": unrun evidence has execution claims")
        return errors
    # A stale receipt keeps its structure and files; only its status changed.
    ran = status != "stale" or evidence["executed"] > 0
    if evidence["type"] in NON_EXECUTION:
        # A read or review runs no process: both exit fields null, or both integers.
        if (evidence["exit_code"] is None) != (evidence["expected_exit"] is None):
            errors.append(label + ": exit_code and expected_exit must both be null or both integers")
    elif ran and (evidence["expected_exit"] is None or (evidence["exit_code"] is None and status == "passed")):
        errors.append(label + ": runtime receipt needs exit_code and expected_exit")
    if status != "stale" and evidence["executed"] < 1:
        errors.append(label + ": zero executed checks")
    if evidence["collected"] != evidence["executed"] + evidence["skipped"]:
        errors.append(label + ": collected/executed/skipped mismatch")
    if evidence["executed"] != evidence["passed"] + evidence["failed"]:
        errors.append(label + ": executed/pass/fail mismatch")
    if status == "passed":
        if evidence["failed"] or evidence["exit_code"] != evidence["expected_exit"]:
            errors.append(label + ": passing status contradicts failures/exit")
        if evidence["skipped"]:
            errors.append(label + ": skipped checks cannot certify passing receipt; split receipts")
    elif status == "failed" and not evidence["failed"] and evidence["exit_code"] == evidence["expected_exit"]:
        errors.append(label + ": failure status has no observed failure")
    elif status == "inconclusive" and not evidence["limitations"]:
        # It ran but cannot settle the claim; it never counts as passed.
        errors.append(label + ": an inconclusive receipt records why and what would settle it (limitations)")
    try:
        if timestamp(evidence["recorded_at"]) > dt.datetime.now(dt.timezone.utc):
            errors.append(label + ": future receipt")
    except ValueError:
        errors.append(label + ": malformed timestamp")
    for path_key, hash_key in (("raw_output", "raw_sha256"), ("artifact", "artifact_sha256")):
        if evidence[path_key] is None or evidence[hash_key] is None:
            if ran:
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
    for old in previous.get("decisions", []):
        new = decisions.get(old["id"])
        if new is None:
            errors.append("decision " + old["id"] + " removed")
        elif any(old[key] != new[key] for key in ("question", "choice", "alternatives", "origin", "supersedes")):
            errors.append("decision " + old["id"] + " rewritten (supersede it with a new decision)")
        elif old["status"] != new["status"] and new["status"] not in DECISION_NEXT[old["status"]]:
            errors.append("decision " + old["id"] + " status cannot move from " + old["status"] + " to " + new["status"])
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
        old = item["supersedes"]
        if old and (old not in index or index[old]["status"] != "superseded"):
            errors.append(item["id"] + ": superseded " + noun + " missing/still active")
        seen, cursor = set(), item["id"]
        while cursor in index:
            if cursor in seen:
                errors.append(item["id"] + ": " + noun + " supersession cycle")
                break
            seen.add(cursor)
            cursor = index[cursor]["supersedes"]
    return errors


def short(value):
    return (value[:12] + "...") if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) else str(value)


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
                  "findings", "reviews", "lessons", "docs", "history", "decisions"):
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
        if receipt["status"] == "stale" and current(receipt):
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
                if not (control and control["status"] == "failed" and control["executed"] > 0
                        and control["failed"] > 0 and not control["skipped"] and supports(control, cid)
                        and control["scope_id"] == task["scope_id"]):
                    errors.append(cid + ": missing failed negative control for current claim/context (" + e["id"] + ")")
                    continue
                for key, noun in (("type", "type"), ("operation", "operation"), ("collected", "collected count")):
                    if control[key] != e[key]:
                        errors.append(cid + ": negative control " + control["id"] + " " + noun + " differs from "
                                      + e["id"] + " (a control reruns the same check)")
                if control["artifact_sha256"] == e["artifact_sha256"]:
                    errors.append(cid + ": negative control " + control["id"] + " uses the same artifact as " + e["id"])
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
        errors.extend(check_previous(previous, task))
    return errors


def version_parts(path):
    match = VERSION_NAME.fullmatch(pathlib.Path(path).name)
    if not match:
        raise ValueError("numbered records are named like task.0001.json: " + pathlib.Path(path).name)
    return match["stem"], int(match["number"]), len(match["number"])


def next_version(path):
    stem, number, width = version_parts(path)
    return pathlib.Path(path).with_name(stem + "." + str(number + 1).zfill(width) + ".json")


def check_chain(directory, last):
    """Check every numbered version up to `last` against its predecessor; versions must be contiguous."""
    directory = pathlib.Path(directory)
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
    previous = None
    for number in range(1, final_number + 1):
        path = found[number]
        record = read_json(path)
        problems = shape(record, CONTRACT["root"])
        if problems:
            errors.extend(path.name + ": " + x for x in problems)
            break
        if previous is not None:
            errors.extend(path.name + ": " + x for x in check_previous(previous, record))
        previous = record
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
            if is_link(info):
                raise ValueError("package contains symlink/reparse point: " + str(path))
            if name in names and not stat.S_ISREG(info.st_mode):
                raise ValueError("nonregular package file: " + str(path))
        folders[:] = sorted(name for name in folders if name != "__pycache__")
        files.extend(pathlib.Path(directory) / name for name in sorted(names) if not name.endswith(".pyc"))
    return sorted(files)


def front_matter(text):
    """Parse the small front-matter subset hosts share; return (keys, errors)."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}, ["missing --- block"]
    keys, errors, current = {}, [], None
    for line in match[1].split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t":
            if current not in FRONT_MATTER_NESTED or keys.get(current):
                errors.append("indented line outside metadata/allowed-tools")
            continue
        parsed = re.fullmatch(r"([a-z][a-z0-9-]*):(?: (.*))?", line)
        if not parsed:
            errors.append("unparseable line")
            current = None
            continue
        key, value = parsed[1], (parsed[2] or "").strip()
        if key in keys:
            errors.append("duplicate key " + key)
        if key not in FRONT_MATTER_KEYS:
            errors.append("unknown key " + key)
        keys[key], current = value, key
    return keys, errors


def plain_scalar(value):
    """The unquoted or simply quoted YAML scalar text, or None when a parser could misread it."""
    if value[:1] in {'"', "'"}:
        inner = value[1:-1]
        if len(value) < 2 or value[-1] != value[0] or value[0] in inner or "\\" in inner:
            return None
        return inner
    if re.search(r": | #", value) or value.endswith(":") or value[:1] in set("[]{}&*!|>%@`,?:-#"):
        return None
    return value


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
    text = text[1:] if text.startswith("﻿") else text
    keys, problems = front_matter(text)
    if keys.get("name") != "westack":
        problems.append("name must be westack")
    description = plain_scalar(keys["description"]) if keys.get("description") else None
    if not description:
        problems.append("description missing or not a safe plain/quoted YAML scalar")
    elif len(description) > 1024:
        problems.append("description exceeds 1024 characters")
    if "compatibility" in keys:
        compatibility = plain_scalar(keys["compatibility"]) if keys["compatibility"] else None
        if not compatibility or len(compatibility) > 500:
            problems.append("compatibility must be a safe scalar of 1-500 characters")
    errors.extend("invalid skill trigger metadata (front matter): " + x for x in problems)
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
        patch_id=patch, author_id=args.author,
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
    return context, errors, notes, observed


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
                   limitations=list(args.limitation))
    if len(claims) > 1:
        receipt["claim_ids"] = claims
    problems = shape(receipt, CONTRACT["$defs"]["evidence"]) or check_receipt(receipt, root)
    if args.control and args.control not in {e["id"] for e in record["evidence"]}:
        problems.append("unknown negative control receipt: " + args.control)
    if problems:
        raise ValueError("receipt not written: " + "; ".join(problems))
    record["evidence"].append(receipt)
    if args.link:
        criteria = {c["id"]: c for c in record["acceptance"]}
        for claim in claims:
            criterion = criteria.get(claim)
            if criterion is None:
                notes.append("--link: " + claim + " is not an acceptance criterion; left unlinked")
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
    ignore = check_excludes(ignore + args.exclude)
    observed = fingerprint(args.repo, paths, exclude=[root], ignore=ignore)
    revision, problems, notes = resolve_revision(args.repo, args.revision)
    if problems:
        raise ValueError("; ".join(problems))
    stored = record.get("fingerprint", {})
    record["fingerprint"] = dict(paths=paths, exclude=ignore, baseline=stored.get("baseline", record["patch_id"]))
    old_patch = record["patch_id"]
    record.update(revision=revision or record["revision"], patch_id=observed["patch"], scope_id=scope)
    staled = []
    for receipt in record["evidence"]:
        if receipt["status"] == "passed" and not same_content(receipt, record):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    package = sub.add_parser("package")
    package.add_argument("path")
    actions = CONTRACT["$defs"]["action"]["properties"]["kind"]["enum"]
    init = sub.add_parser("init", help="create an incomplete canonical task without executing anything")
    init.add_argument("path")
    init.add_argument("--root", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--repo", help="repository to fingerprint for --patch and read HEAD from")
    init.add_argument("--revision")
    init.add_argument("--scope", required=True)
    init.add_argument("--patch")
    init.add_argument("--author", required=True)
    init.add_argument("--task-id", default="new-task")
    init.add_argument("--task-mode", choices=CONTRACT["$defs"]["task"]["properties"]["mode"]["enum"], default="build")
    init.add_argument("--size", choices=["tiny", "bounded", "cross-cutting"], default="bounded")
    init.add_argument("--allow-path", action="append", required=True)
    init.add_argument("--observe-path", action="append", default=[],
                      help="also fingerprint this path (tests, config) without granting writes")
    init.add_argument("--exclude", action="append", default=[], help="extra name or path to leave out of the fingerprint")
    init.add_argument("--no-default-excludes", action="store_true")
    init.add_argument("--allow-action", action="append", default=[], choices=actions)
    init.add_argument("--forbid-action", action="append", default=[], choices=actions)
    init.add_argument("--non-goal", action="append", default=[])
    task = sub.add_parser("task")
    task.add_argument("path")
    task.add_argument("--root", required=True)
    task.add_argument("--repo", help="recompute patch (and HEAD) from this repository")
    task.add_argument("--path", dest="paths", action="append", default=[],
                      help="fingerprint these paths instead of the record's definition")
    task.add_argument("--revision")
    task.add_argument("--scope")
    task.add_argument("--patch")
    task.add_argument("--previous")
    task.add_argument("--chain", help="folder of numbered versions; check each against its predecessor")
    observed = sub.add_parser("fingerprint", help="print the observed patch fingerprint and Git HEAD")
    observed.add_argument("--repo", required=True)
    observed.add_argument("--path", dest="paths", action="append", default=[])
    observed.add_argument("--root", help="evidence root to exclude when it is inside the repository")
    observed.add_argument("--exclude", action="append", default=None,
                          help="replace the default excludes (repeat for each name or path)")
    copy_file = sub.add_parser("snapshot", help="copy a tested file into <root>/snapshots/<sha256><suffix>")
    copy_file.add_argument("path")
    copy_file.add_argument("--root", required=True)
    advice = sub.add_parser("reconcile", help="diagnostic recommendation for one recorded action")
    advice.add_argument("path")
    advice.add_argument("--root", required=True)
    advice.add_argument("--action", required=True)
    advice.add_argument("--observed", required=True, choices=["applied", "not-applied", "unknown"])
    receipt = sub.add_parser("receipt", help="write the next version with one receipt; computes hashes, runs nothing")
    receipt.add_argument("path")
    receipt.add_argument("--root", required=True)
    receipt.add_argument("--repo", required=True)
    receipt.add_argument("--revision")
    receipt.add_argument("--id", required=True)
    receipt.add_argument("--claim", action="append", required=True,
                         help="acceptance, action, finding or review ID; repeat when one run backs several")
    receipt.add_argument("--type", required=True, choices=CONTRACT["$defs"]["evidence"]["properties"]["type"]["enum"])
    receipt.add_argument("--operation", required=True, help="the exact command or read, as run")
    receipt.add_argument("--environment", required=True)
    receipt.add_argument("--raw", help="raw output file (copied into snapshots/ when outside the evidence root)")
    receipt.add_argument("--artifact", help="tested file (snapshotted when outside the evidence root)")
    receipt.add_argument("--passed", type=int, default=0)
    receipt.add_argument("--failed", type=int, default=0)
    receipt.add_argument("--skipped", type=int, default=0)
    receipt.add_argument("--exit", type=int)
    receipt.add_argument("--expected-exit", type=int)
    receipt.add_argument("--status", choices=["passed", "failed", "inconclusive", "blocked", "not-run"],
                         help="default: failed when a case failed or the exit differs, else passed")
    receipt.add_argument("--control", help="ID of the failed broken-copy receipt for the same check")
    receipt.add_argument("--coverage")
    receipt.add_argument("--limitation", action="append", default=[])
    receipt.add_argument("--link", action="store_true",
                         help="point named acceptance criteria at this receipt (passed, failed or inconclusive)")
    renew = sub.add_parser("refresh", help="write the next version bound to the observed repository and scope")
    renew.add_argument("path")
    renew.add_argument("--root", required=True)
    renew.add_argument("--repo", required=True)
    renew.add_argument("--revision")
    renew.add_argument("--scope", help="new scope label when the user's authority changed")
    renew.add_argument("--reason")
    renew.add_argument("--grant", action="append", default=[], choices=actions,
                       help="record an action kind the user granted within the current scope")
    renew.add_argument("--relax", action="append", default=[],
                       help="with --scope: make a criterion optional, drop a work unit or review, or 'independent-review'")
    renew.add_argument("--observe-path", action="append", default=[])
    renew.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()
    extra, notes = {}, []
    try:
        if args.mode == "init":
            print(json.dumps(start_task(args), indent=2))
            return 0
        if args.mode == "fingerprint":
            result = observe(args.repo, args.paths, args.root, args.exclude)
            result.pop("entries")
            print(json.dumps(dict(status="passed", **result,
                  claim="observed file-content fingerprint; not a review, test or permission"), indent=2))
            return 0
        if args.mode == "snapshot":
            print(json.dumps(dict(snapshot(args.path, args.root),
                  claim="byte copy for evidence; proves nothing about the file's behaviour"), indent=2))
            return 0
        if args.mode in {"receipt", "refresh"}:
            result = add_receipt(args) if args.mode == "receipt" else refresh(args)
            result["claim"] = "record write only; nothing executed, no permission granted"
            print(json.dumps(result, indent=2))
            return 1 if result["errors"] else 0
        if args.mode == "package":
            errors = check_package(args.path)
        elif args.mode == "reconcile":
            record = read_json(args.path)
            malformed = shape(record, CONTRACT["root"])
            # Consistency of the record itself; context binding is the task command's job.
            errors = malformed or check_task(record, args.root,
                                             {k: record[k] for k in ("revision", "scope_id", "patch_id")})
            action = None if malformed else next((a for a in record["actions"] if a["id"] == args.action), None)
            if action is None and not malformed:
                errors.append("unknown action: " + args.action)
            elif action is not None:
                extra = {"action": args.action, "observed": args.observed,
                         "recommendation": reconcile(action, args.observed)}
            extra["claim"] = ("diagnostic only: uses the caller's observation; does not observe the target "
                              "or make a retry safe")
        else:
            if args.chain and args.previous:
                raise ValueError("use --chain or --previous, not both")
            record = read_json(args.path)
            context, errors, notes, observed = task_context(args, record)
            errors += check_task(record, args.root, context,
                                 read_json(args.previous) if args.previous else None, notes)
            if args.chain:
                errors += check_chain(args.chain, args.path)
            if observed and not shape(record, CONTRACT["root"]):
                root = pathlib.Path(args.root)
                if observed["patch"] != record["patch_id"]:
                    old = load_manifest(root, record["patch_id"])
                    if old is None:
                        notes.append("no stored manifest for the record's patch; refresh stores one")
                    else:
                        extra["changed_files"] = diff_entries(old, observed["entries"])
                base = record.get("fingerprint", {}).get("baseline")
                if record["work_units"] and base:
                    old = load_manifest(root, base)
                    if old is None:
                        notes.append("no stored manifest for the baseline patch; cannot compare against work units")
                    else:
                        changed = diff_entries(old, observed["entries"])
                        files = sorted(set(changed["added"] + changed["modified"] + changed["removed"]))
                        extra["outside_work_units"] = [f for f in files if not any(
                            within(f, unit["allowed_paths"]) for unit in record["work_units"])]
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        errors = ["malformed/unreadable input: " + str(exc)]
    report = {"status": "failed" if errors else "passed",
              "claim": "consistency-only; not truth, host enforcement or model qualification"}
    report.update(extra)
    if notes or args.mode == "task":
        report["notes"] = notes
    report["errors"] = errors
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
