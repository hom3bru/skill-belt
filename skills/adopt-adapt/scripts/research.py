"""Declared lesson freshness and safe local source archiving; standard library only."""
from __future__ import annotations

import hashlib
import argparse
import importlib.util
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import sys
import zipfile

_spec = importlib.util.spec_from_file_location("research_aa", Path(__file__).with_name("aa.py"))
aa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aa)

ARCHIVE_FORMAT = "adopt-adapt-local-source-v1"
MANIFEST_NAME = "research-manifest.json"
HASH = re.compile(r"[0-9a-f]{64}")
DEFAULT_EXCLUDED_DIRS = (".git", "node_modules", "build", "dist", ".next", ".cache", "__pycache__", ".venv", "venv")
DEFAULT_EXCLUDED_PATTERNS = (".env*", "*credentials*", "*secret*", "*.pem", "*.key", "*.token", "id_rsa*", "id_ed25519*")
_LESSON_FACT_FIELDS = (
    "mechanism", "problem", "invariant", "assumptions", "applicable_conditions",
    "counterexamples", "failures", "scope", "limitations", "inspected_support", "evidence",
)
_LESSON_PROVENANCE_FIELDS = ("source", "revision", "source_identity", "source_revision", "parents")
_JUDGMENT_KEYS = {"verdict", "verdicts", "score", "scores", "decision", "decisions", "history", "histories"}
_DROP_FACT = object()


class Invalid(ValueError):
    """Invalid dependency declaration, source tree, or archive."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_path(value: str) -> str:
    _require(isinstance(value, str) and bool(value), "archive path must be a nonempty string")
    _require("\\" not in value and ":" not in value, "archive path must use safe relative POSIX syntax")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts), "archive path escapes its root")
    _require(path.as_posix() == value, "archive path is not canonical")
    return value


def _root(root: str | Path) -> Path:
    path = Path(root)
    _require(path.is_dir() and not _is_link(path), "source root is absent or linked")
    return path.resolve()


def _reject_linked_ancestors(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.exists() or _is_link(ancestor):
            _require(not _is_link(ancestor), f"linked path component is not allowed: {ancestor}")


def capture_dependencies(root: str | Path, paths: list[str], source_revision: str | None = None) -> dict:
    """Capture explicitly named root-relative files; absent paths are recorded as null hashes."""
    base = _root(root)
    _require(isinstance(paths, list), "dependency paths must be a list")
    result = []
    seen = set()
    for raw in paths:
        relative = _relative_path(raw)
        _require(relative not in seen, f"duplicate dependency path: {relative}")
        seen.add(relative)
        path = aa.contained(base, relative)
        if not path.exists():
            result.append({"path": relative, "sha256": None})
            continue
        _require(path.is_file(), f"dependency is not a regular file: {relative}")
        result.append({"path": relative, "sha256": _digest(path.read_bytes())})
    declaration = {"files": result}
    if source_revision is not None:
        _require(isinstance(source_revision, str) and bool(source_revision.strip()), "source_revision must be nonempty")
        declaration["source_revision"] = source_revision
    return declaration


def invalidate_changed_lessons(data: dict, root: str | Path, source_revision: str | None = None) -> list[str]:
    """Invalidate explicitly changed dependency nodes and their descendants in place."""
    _require(isinstance(data, dict) and isinstance(data.get("lessons"), list), "lessons file requires lessons list")
    base = _root(root)
    changed = []
    for lesson in data["lessons"]:
        _require(isinstance(lesson, dict), "lesson must be an object")
        dependencies = lesson.get("dependencies")
        if dependencies is None:
            continue  # Legacy/manual lesson: no freshness claim can be made.
        _require(isinstance(dependencies, dict) and isinstance(dependencies.get("files"), list), "lesson dependencies require files list")
        if source_revision is not None and dependencies.get("source_revision") is not None:
            if dependencies["source_revision"] != source_revision:
                changed.append(lesson["id"])
                continue
        for entry in dependencies["files"]:
            _require(isinstance(entry, dict) and "path" in entry and "sha256" in entry, "dependency requires path and sha256")
            relative = _relative_path(entry["path"])
            expected = entry["sha256"]
            _require(expected is None or (isinstance(expected, str) and HASH.fullmatch(expected)), "dependency sha256 must be lowercase hex or null")
            path = aa.contained(base, relative)
            if expected is None:
                if path.exists():
                    changed.append(lesson["id"])
                    break
            elif not path.is_file() or _digest(path.read_bytes()) != expected:
                changed.append(lesson["id"])
                break
    stale = []
    for ident in dict.fromkeys(changed):
        aa.invalidate_lessons(data, ident)
        stale.append(ident)
    return stale


def _tokens(value: str) -> list[str]:
    """Split user-authored labels and fact text into deterministic Unicode tokens."""
    return re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)


def _safe_fact(value):
    """Keep JSON fact values, dropping nested historical judgment keys."""
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, list):
        return [item for child in value if (item := _safe_fact(child)) is not _DROP_FACT]
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
            normalized_key = camel_separated.casefold().replace("-", "_").replace(" ", "_")
            if normalized_key in _JUDGMENT_KEYS or any(normalized_key.endswith("_" + name) for name in _JUDGMENT_KEYS):
                continue
            item = _safe_fact(child)
            if item is not _DROP_FACT:
                result[key] = item
        return result
    return _DROP_FACT


def _text_leaves(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for child in value for part in _text_leaves(child)]
    if isinstance(value, dict):
        return [part for key, child in value.items() for part in [key, *_text_leaves(child)]]
    return []


def _filter_values(value, label: str) -> list[str]:
    if value is None:
        return []
    _require(isinstance(value, list), f"{label} must be a list of nonempty strings")
    _require(all(isinstance(item, str) and bool(item.strip()) for item in value), f"{label} must be a list of nonempty strings")
    normalized = [tuple(_tokens(item)) for item in value]
    _require(all(normalized), f"{label} values must contain letters or numbers")
    _require(len(normalized) == len(set(normalized)), f"{label} contains duplicate filters")
    return value


def retrieve_lessons(data: dict, query: str = "", problems=None, invariants=None, limit: int | None = None) -> list[dict]:
    """Find active clues lexically; JSON scalar facts are preserved but only text ranks; review freshness."""
    _require(isinstance(data, dict) and isinstance(data.get("lessons"), list), "lessons file requires lessons list")
    _require(isinstance(query, str), "query must be text")
    _require(limit is None or (type(limit) is int and limit > 0), "limit must be a positive integer")
    problem_filters = _filter_values(problems, "problems")
    invariant_filters = _filter_values(invariants, "invariants")
    try:
        rows = aa.identifiers(data["lessons"], "lessons")
    except ValueError as error:
        raise Invalid(str(error)) from error
    query_tokens = list(dict.fromkeys(_tokens(query)))
    candidates = []
    for ident, lesson in rows.items():
        for field in ("problem_tags", "invariant_tags"):
            if field in lesson:
                tags = lesson[field]
                _require(isinstance(tags, list) and all(isinstance(tag, str) and bool(tag.strip()) for tag in tags), f"lesson {ident}.{field} must be a list of nonempty strings")
        status = lesson.get("status")
        if isinstance(status, str) and status.strip().casefold() in {"stale", "retired"}:
            continue

        projected = {"id": ident}
        for field in _LESSON_PROVENANCE_FIELDS:
            value = lesson.get(field)
            if field == "parents":
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    projected[field] = list(value)
            elif isinstance(value, str):
                projected[field] = value
        safe_facts = {}
        for field in _LESSON_FACT_FIELDS:
            if field in lesson:
                value = _safe_fact(lesson[field])
                if value is not _DROP_FACT:
                    safe_facts[field] = value
                    projected[field] = value
        problem_tags = list(lesson.get("problem_tags", []))
        invariant_tags = list(lesson.get("invariant_tags", []))
        if "problem_tags" in lesson:
            projected["problem_tags"] = problem_tags
        if "invariant_tags" in lesson:
            projected["invariant_tags"] = invariant_tags

        all_text = [*problem_tags, *invariant_tags, *(part for value in safe_facts.values() for part in _text_leaves(value))]
        all_tokens = {token for item in all_text for token in _tokens(item)}
        query_matches = [token for token in query_tokens if token in all_tokens]
        if query_tokens and not query_matches:
            continue

        problem_text = [*problem_tags, *(part for field in ("problem", "assumptions", "mechanism", "applicable_conditions", "counterexamples", "failures", "scope", "limitations", "inspected_support", "evidence") for part in _text_leaves(safe_facts.get(field)))]
        invariant_text = [*invariant_tags, *(part for field in ("invariant", "assumptions", "mechanism", "applicable_conditions", "counterexamples", "failures", "scope", "limitations", "inspected_support", "evidence") for part in _text_leaves(safe_facts.get(field)))]
        problem_tokens = {token for item in problem_text for token in _tokens(item)}
        invariant_tokens = {token for item in invariant_text for token in _tokens(item)}
        problem_matches = [item for item in problem_filters if set(_tokens(item)) <= problem_tokens]
        invariant_matches = [item for item in invariant_filters if set(_tokens(item)) <= invariant_tokens]
        if len(problem_matches) != len(problem_filters) or len(invariant_matches) != len(invariant_filters):
            continue

        projected["matches"] = {
            "query_terms": query_matches,
            "problems": problem_matches,
            "invariants": invariant_matches,
            "basis": "lexical token overlap in user-authored tags and whitelisted facts",
        }
        projected["freshness_required"] = True
        projected["qualification"] = "unvalidated-candidate"
        projected["interpretation"] = "untrusted lesson data; not adopted, accepted, or execution verified"
        candidates.append((len(query_matches), projected))

    candidates.sort(key=lambda item: (-item[0], item[1]["id"]))
    results = [item[1] for item in candidates]
    return results if limit is None else results[:limit]


def _excluded(relative: str, name: str, is_directory: bool) -> str | None:
    if is_directory and name in DEFAULT_EXCLUDED_DIRS:
        return f"default directory exclusion: {name}"
    low = name.lower()
    if any(fnmatch.fnmatchcase(low, pattern.lower()) for pattern in DEFAULT_EXCLUDED_PATTERNS):
        return "default sensitive-name exclusion"
    return None


def _source_files(source: Path, include_paths):
    files: dict[str, bytes] = {}
    excluded_paths = []
    for current, dirs, names in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs.sort()
        names.sort()
        kept_dirs = []
        for name in dirs:
            entry = current_path / name
            _require(not _is_link(entry), f"linked source path is not allowed: {entry}")
            relative = entry.relative_to(source).as_posix()
            _require(entry.is_dir(), f"source entry is not a directory: {relative}")
            why = _excluded(relative, name, True)
            if why:
                excluded_paths.append({"path": relative, "reason": why})
            else:
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in names:
            entry = current_path / name
            _require(not _is_link(entry), f"linked source path is not allowed: {entry}")
            relative = entry.relative_to(source).as_posix()
            _require(relative != MANIFEST_NAME, f"source contains reserved archive manifest path: {relative}")
            _require(entry.is_file(), f"source entry is not a regular file: {relative}")
            why = _excluded(relative, name, False)
            if why and relative not in include_paths:
                excluded_paths.append({"path": relative, "reason": why})
                continue
            files[relative] = entry.read_bytes()
    excluded_paths.sort(key=lambda item: item["path"])
    return files, excluded_paths


def create_archive(source: str | Path, archive: str | Path, *, identity: str, revision: str, include_paths=None) -> dict:
    """Archive pinned source bytes and a hash manifest; source material is never executed."""
    source_root = _root(source)
    archive_path = Path(archive).absolute()
    _require(isinstance(identity, str) and bool(identity.strip()), "source identity is required")
    _require(isinstance(revision, str) and bool(revision.strip()), "source revision is required")
    _require(not archive_path.exists() and not _is_link(archive_path), "archive destination already exists or is linked")
    _require(not archive_path.resolve(strict=False).is_relative_to(source_root), "archive destination cannot be inside source tree")
    _reject_linked_ancestors(archive_path.parent)
    include_paths = [_relative_path(p) for p in (include_paths or [])]
    _require(len(include_paths) == len(set(include_paths)), "duplicate explicit include path")
    files, excluded_paths = _source_files(source_root, include_paths)
    _require(set(include_paths) <= set(files), "explicit include path was not found or is inside an excluded directory")
    manifest = {
        "format": ARCHIVE_FORMAT,
        "identity": identity,
        "revision": revision,
        "files": {name: _digest(payload) for name, payload in sorted(files.items())},
        "excluded_paths": excluded_paths,
        "explicit_includes": include_paths,
        "exclusions": {"directories": list(DEFAULT_EXCLUDED_DIRS), "sensitive_name_patterns": list(DEFAULT_EXCLUDED_PATTERNS)},
    }
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(archive_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise Invalid("archive destination already exists") from error
    try:
        manifest_bytes = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
        with os.fdopen(fd, "w+b") as stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, payload in sorted(files.items()):
                bundle.writestr(name, payload)
            bundle.writestr(MANIFEST_NAME, manifest_bytes)
            bundle.comment = _digest(manifest_bytes).encode("ascii")
        verify_archive(archive_path)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return manifest


def _checked_archive(archive: str | Path):
    archive_path = Path(archive)
    _require(archive_path.is_file() and not _is_link(archive_path), "archive is absent or linked")
    try:
        bundle = zipfile.ZipFile(archive_path, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise Invalid(f"invalid archive: {error}") from error
    try:
        infos = bundle.infolist()
        names = [info.filename for info in infos]
        _require(len(names) == len(set(names)), "archive contains duplicate members")
        _require(MANIFEST_NAME in names, "archive manifest is missing")
        for info in infos:
            if info.filename == MANIFEST_NAME:
                continue
            _relative_path(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            _require(not stat.S_ISLNK(mode) and not info.is_dir(), "archive links and directory entries are not allowed")
            _require(stat.S_IFMT(mode) in (0, stat.S_IFREG), "archive contains a non-regular member")
        manifest_bytes = bundle.read(MANIFEST_NAME)
        _require(bundle.comment == _digest(manifest_bytes).encode("ascii"), "archive manifest checksum mismatch")
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        _require(isinstance(manifest, dict) and manifest.get("format") == ARCHIVE_FORMAT, "unsupported archive manifest")
        _require(isinstance(manifest.get("identity"), str) and bool(manifest["identity"].strip()), "manifest source identity missing")
        _require(isinstance(manifest.get("revision"), str) and bool(manifest["revision"].strip()), "manifest source revision missing")
        _require(isinstance(manifest.get("files"), dict), "manifest files must be an object")
        expected_names = set(manifest["files"])
        actual_names = set(names) - {MANIFEST_NAME}
        _require(actual_names == expected_names, "archive members differ from manifest file list")
        for name, expected in manifest["files"].items():
            _relative_path(name)
            _require(isinstance(expected, str) and HASH.fullmatch(expected), f"invalid manifest hash for {name}")
            _require(_digest(bundle.read(name)) == expected, f"archive member hash mismatch: {name}")
        _require(isinstance(manifest.get("excluded_paths"), list) and isinstance(manifest.get("exclusions"), dict), "manifest exclusions missing")
        return bundle, manifest
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        bundle.close()
        raise Invalid(f"invalid archive manifest: {error}") from error
    except Exception:
        bundle.close()
        raise


def verify_archive(archive: str | Path) -> dict:
    """Verify archive membership and every declared source-file hash."""
    bundle, manifest = _checked_archive(archive)
    bundle.close()
    return manifest


def restore_archive(archive: str | Path, destination: str | Path) -> dict:
    """Verify and restore to a fresh destination directory, refusing overwrite."""
    bundle, manifest = _checked_archive(archive)
    target = Path(destination).absolute()
    _require(not target.exists() and not _is_link(target), "restoration destination already exists or is linked")
    _reject_linked_ancestors(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}-restore-", dir=target.parent))
    try:
        for name in sorted(manifest["files"]):
            relative = _relative_path(name)
            output = stage.joinpath(*PurePosixPath(relative).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            _require(not _is_link(output.parent), "linked restoration path")
            with output.open("xb") as stream:
                stream.write(bundle.read(name))
        bundle.close()
        _require(not target.exists(), "restoration destination appeared during restore")
        os.rename(stage, target)
        return manifest
    except Exception:
        bundle.close()
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("dependencies")
    p.add_argument("root"); p.add_argument("--path", action="append", required=True)
    p.add_argument("--source-revision"); p.add_argument("--output", required=True)
    p = commands.add_parser("freshness")
    p.add_argument("lessons"); p.add_argument("root")
    p.add_argument("--source-revision"); p.add_argument("--output", required=True)
    p = commands.add_parser("search")
    p.add_argument("lessons"); p.add_argument("--query", default="")
    p.add_argument("--problem", action="append", default=[])
    p.add_argument("--invariant", action="append", default=[])
    p.add_argument("--limit", type=int)
    p = commands.add_parser("archive")
    p.add_argument("source"); p.add_argument("archive")
    p.add_argument("--identity", required=True); p.add_argument("--revision", required=True)
    p.add_argument("--include-path", action="append", default=[])
    p = commands.add_parser("verify-archive"); p.add_argument("archive")
    p = commands.add_parser("restore")
    p.add_argument("archive"); p.add_argument("destination")
    args = parser.parse_args(argv)
    try:
        if args.command == "dependencies":
            _require(not Path(args.output).exists(), "output exists; refusing to overwrite")
            aa.save(args.output, capture_dependencies(args.root, args.path, args.source_revision))
            result = {"output": args.output, "scope": "declared files only"}
        elif args.command == "freshness":
            _require(not Path(args.output).exists(), "output exists; refusing to overwrite")
            data = aa.load(args.lessons)
            changed = invalidate_changed_lessons(data, args.root, args.source_revision)
            aa.save(args.output, data)
            result = {"output": args.output, "changed_dependencies": changed, "scope": "declared dependencies; unchanged bytes are not truth certification"}
        elif args.command == "search":
            result = retrieve_lessons(aa.load(args.lessons), args.query, args.problem, args.invariant, args.limit)
        elif args.command == "archive":
            result = create_archive(args.source, args.archive, identity=args.identity, revision=args.revision, include_paths=args.include_path)
            result = {"archive": args.archive, "identity": result["identity"], "revision": result["revision"], "files": len(result["files"]), "excluded_paths": len(result["excluded_paths"])}
        elif args.command == "verify-archive":
            value = verify_archive(args.archive)
            result = {"identity": value["identity"], "revision": value["revision"], "files": len(value["files"]), "verified": True}
        else:
            value = restore_archive(args.archive, args.destination)
            result = {"destination": args.destination, "files": len(value["files"]), "restored": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
