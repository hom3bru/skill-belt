"""westack evidence helpers: receipts, matched broken-copy controls, content fingerprints and snapshots.

Standard library only. Reads files and Git metadata from disk; runs no process, opens no network
connection and never replaces an existing file (snapshots and manifests use exclusive create).
"""
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import stat

__all__ = [
    "RUNTIME", "NON_EXECUTION", "LIMIT", "REPARSE_POINT", "LINK_TAGS", "FINGERPRINT_HEADER", "ALWAYS_SKIP",
    "DEFAULT_EXCLUDE", "MANIFEST_FORMAT", "GIT_OBJECT", "GIT_REF",
    "UnsafeTarget", "WRITE_VERBS", "GLOB_VERBS", "GLOB_LIMIT", "judge_patch",
    "digest", "read_json", "read_small_text", "write_new", "safe_path", "scope_path", "portable", "within",
    "is_link", "check_excludes", "fingerprint_hash", "fingerprint", "plain_folder", "store_manifest",
    "load_manifest", "diff_entries", "git_location", "git_revision", "resolve_revision", "observe", "snapshot",
    "timestamp", "supports", "same_content", "short", "check_receipt", "control_errors",
]

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
GIT_OBJECT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
GIT_REF = re.compile(r"refs/[A-Za-z0-9._+/-]+")


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


def _create_exclusive(path, text):
    """Exclusive create for a filesystem that cannot hard link; a failed write removes the file this call made."""
    made = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            made = True
            stream.write(text)
    except BaseException:
        if made:
            path.unlink()
        raise


def write_new(path, data):
    """Exclusive create; an existing file is never replaced and the final name never holds a partial file.

    The text is serialised first, written to a temporary file in the same folder, flushed to disk and then
    hard-linked to its final name. The link fails if the name exists, so a crash mid-write leaves at most a stray
    hidden temporary file, never a damaged next version that blocks the record chain. A filesystem without hard
    links falls back to exclusive create, where a failed write removes the partial file it just made.
    """
    path = pathlib.Path(path)
    text = json.dumps(data, indent=2) + "\n"
    temp = path.with_name("." + path.name + "." + os.urandom(6).hex() + ".tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            raise
        except OSError:
            _create_exclusive(path, text)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass  # cleanup only; a stray hidden temporary file is harmless and never matches a version name


class UnsafeTarget(ValueError):
    """A path that broke a containment invariant. `invariant` names the first one that broke; `failures`
    lists every (invariant, detail) pair when a whole patch was judged."""

    def __init__(self, invariant, detail, failures=None):
        self.invariant = invariant
        self.failures = failures or [(invariant, detail)]
        super().__init__("; ".join(text + " [" + name + "]" for name, text in self.failures))


# verb -> number of paths. A pattern (`*`, `?` or `[`) is allowed only for the verbs in GLOB_VERBS.
WRITE_VERBS = {"create": 1, "modify": 1, "delete": 1, "rename": 2}
GLOB_VERBS = {"modify", "delete"}
GLOB_LIMIT = 10000
WILDCARDS = frozenset("*?[")
GLOB_SEGMENT = re.compile(r"(?:[^\[\]]|\[[^\[\]]+\])*")


def _resolved(path):
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:  # a link loop or an unreadable parent: unknown is never inside
        raise UnsafeTarget("cannot-resolve", "cannot resolve " + str(path) + " (" + str(exc) + ")")


def _inside(root, resolved):
    # Components, never text: /work/proj-evil is not inside /work/proj.
    return resolved.is_relative_to(root)


def _portable_parts(relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or pathlib.PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise UnsafeTarget("not-portable", "nonportable or escaping path: " + str(relative))
    return relative.split("/")


def _contain(root, relative):
    """The resolved path of one literal path under `root` (already resolved). A path that does not exist
    yet resolves through its nearest existing parent."""
    resolved = _resolved(root.joinpath(*_portable_parts(relative)))
    if not _inside(root, resolved):
        raise UnsafeTarget("escapes-root", "resolved path escapes root: " + relative)
    return resolved


def safe_path(root, relative):
    # Diagnostic containment only; host enforcement must cover races and alternate tools.
    return _contain(pathlib.Path(root).resolve(strict=True), relative)


def _expand(root, parts, relative):
    """Existing paths a pattern matches under `root`, each resolved and judged."""
    for part in parts:
        if "**" in part and part != "**":
            raise UnsafeTarget("invalid-glob", "`**` must be a whole path segment: " + relative)
        if not GLOB_SEGMENT.fullmatch(part):
            raise UnsafeTarget("invalid-glob", "unbalanced or empty [ ] in pattern: " + relative)
    fixed = []
    for part in parts:
        if WILDCARDS & set(part):
            break
        fixed.append(part)
    base = _contain(root, "/".join(fixed)) if fixed else root
    found, failures = [], []
    for match in base.glob("/".join(parts[len(fixed):])):
        if len(found) + len(failures) >= GLOB_LIMIT:
            raise UnsafeTarget("too-many-matches", "pattern matches more than " + str(GLOB_LIMIT)
                               + " paths; narrow it: " + relative)
        resolved = _resolved(match)
        if _inside(root, resolved):
            found.append(resolved)
        else:
            failures.append(("escapes-root", "pattern match resolves outside the root: "
                             + match.relative_to(root).as_posix()))
    if failures:
        raise UnsafeTarget(failures[0][0], "", failures)
    return found


def _judge_operation(root, operation):
    arity = WRITE_VERBS.get(operation[0]) if isinstance(operation, (list, tuple)) and operation \
        and isinstance(operation[0], str) else None
    if arity is None or len(operation) != 1 + arity:
        raise UnsafeTarget("unknown-operation", "an operation is (create|modify|delete, path) or "
                           "(rename, source, destination): " + repr(operation))
    verb, found, failures = operation[0], [], []
    for relative in operation[1:]:
        try:
            parts = _portable_parts(relative)
            if WILDCARDS & set(relative):
                if verb not in GLOB_VERBS:
                    raise UnsafeTarget("invalid-glob", verb + " names one path, not a pattern: " + relative)
                found.extend(_expand(root, parts, relative))
            else:
                found.append(_contain(root, relative))
        except UnsafeTarget as exc:
            failures.extend(exc.failures)
    if failures:
        raise UnsafeTarget(failures[0][0], "", failures)
    return found


def judge_patch(root, operations):
    """Judge a whole patch before any file changes; return the resolved paths it would touch.

    `operations` is a list of ("create" | "modify" | "delete", path) and ("rename", source, destination),
    each path a portable slash path relative to `root`. Every path is resolved first (links followed; a
    file that does not exist yet is judged through its nearest existing parent) and then compared with the
    root by path components, never by text prefix. A rename judges both ends. A delete judges what it
    would delete, so a link that points outside is refused even when only the link is meant. A path with
    `*`, `?` or `[` is a pattern, allowed only for modify and delete: it must be well formed, is expanded
    against what exists, and every match is judged.

    The patch is judged by its worst path: one failing path refuses all of it. The error is an
    UnsafeTarget (a ValueError) that names the invariant that broke (not-portable, escapes-root,
    invalid-glob, too-many-matches, cannot-resolve, unknown-operation or no-operations) and lists every
    failing path. Anything unclear is refused, and no operations is an error, not a pass. A missing root is
    an OSError.

    Diagnostic containment, not a sandbox. It does not cover hard links, a path changed between this
    check and the write, other processes or tools, or aliases the filesystem resolves differently.
    """
    root = pathlib.Path(root).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError("root must be a directory: " + str(root))
    if not isinstance(operations, (list, tuple)) or not operations:
        raise UnsafeTarget("no-operations", "nothing to judge; an empty patch is not a pass")
    touched, failures = [], []
    for index, operation in enumerate(operations):
        try:
            touched.extend(_judge_operation(root, operation))
        except UnsafeTarget as exc:
            failures.extend((name, "operation %d: %s" % (index + 1, text)) for name, text in exc.failures)
    if failures:
        raise UnsafeTarget(failures[0][0], "", failures)
    return list(dict.fromkeys(touched))


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


def supports(evidence, claim):
    """A receipt backs its claim_id and any listed claim_ids."""
    return evidence["claim_id"] == claim or claim in evidence.get("claim_ids", [])


def same_content(item, task):
    """Staleness follows content and authority: patch fingerprint and scope, not the commit."""
    return (item["patch_id"], item["scope_id"]) == (task["patch_id"], task["scope_id"])


def short(value):
    return (value[:12] + "...") if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) else str(value)


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


def control_errors(claim, receipt, control, scope):
    """Errors unless `control` is a matched broken-copy run for `receipt`.

    A matched control is a failed receipt with actual failing cases and no skips, for the same claim and
    scope, of the same evidence type and operation, with the same collected count (both runs selected the
    same cases), on a different artifact. Its patch may differ, so a red run before the fix qualifies.
    """
    if not (control and control["status"] == "failed" and control["executed"] > 0
            and control["failed"] > 0 and not control["skipped"] and supports(control, claim)
            and control["scope_id"] == scope):
        return [claim + ": missing failed negative control for current claim/context (" + receipt["id"] + ")"]
    errors = []
    for key, noun in (("type", "type"), ("operation", "operation"), ("collected", "collected count")):
        if control[key] != receipt[key]:
            errors.append(claim + ": negative control " + control["id"] + " " + noun + " differs from "
                          + receipt["id"] + " (a control reruns the same check)")
    if control["artifact_sha256"] == receipt["artifact_sha256"]:
        errors.append(claim + ": negative control " + control["id"] + " uses the same artifact as " + receipt["id"])
    return errors
