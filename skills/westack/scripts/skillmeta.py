"""westack skill metadata: front matter parsing, semantic versions and package checks.

Standard library only; reads files, runs nothing. Shared by validate.py (package), registry.py,
core_check.py, build_core_block.py and tools/install.py.
"""
import importlib.util
import hashlib
import os
import pathlib
import re
import stat
import sys

__all__ = [
    "STACK", "FRONT_MATTER_KEYS", "FRONT_MATTER_NESTED", "NAME", "SEMVER",
    "SHIP_EXCLUDE_DIRS", "CACHE_DIRS", "CACHE_SUFFIXES", "INSTALL_MANIFEST",
    "front_matter", "plain_scalar", "skill_metadata", "parse_version", "compare_versions", "parse_range",
    "satisfies", "package_files", "is_shipped", "shipped_files", "ship_ignore", "check_package", "package_warnings",
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


is_link = _sibling("evidence").is_link

STACK = "westack"
FRONT_MATTER_KEYS = {"name", "description", "metadata", "disable-model-invocation", "license", "allowed-tools",
                     "compatibility"}
FRONT_MATTER_NESTED = {"metadata", "allowed-tools"}
NAME = re.compile(r"westack(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?")
# What stays out of any copy of a skill that a host or an eval run reads. One list: tools/install.py, the eval
# runner's work-folder copy (tools/eval/campaign_run.py) and the eval campaign's skill hash (westack-eval's
# campaign.py) all take it from here. The skill's own evals/ (rubrics, canaries, fixtures) and tests/ are an answer
# key, so they never ship; they are excluded at the skill's root, where the layout puts them. Bytecode caches
# are excluded at any depth.
SHIP_EXCLUDE_DIRS = ("evals", "tests", ".validation")
CACHE_DIRS = ("__pycache__",)
CACHE_SUFFIXES = (".pyc",)
INSTALL_MANIFEST = ".westack-install.json"
_IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
                    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
_PARTIAL = re.compile(r"(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?")
_COMPARATOR = re.compile(r"(>=|<=|>|<|=)?(.+)")
# package_warnings lints. They are the authors' heuristics, not measured effects, so they never fail a package.
MAX_STEPS = 10
_LABEL = r"^[ \t]*(?:#{1,6}[ \t]+|[-*][ \t]+|\*\*)?"
STEP_ONE = re.compile(_LABEL + r"Step 1\b", re.I | re.M)
STEP_NUMBER = re.compile(_LABEL + r"Step (\d+)\b", re.I | re.M)
MACHINE_PATH = re.compile(r"(?<![\w.])(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]|/Users/[^\s/]+/|/home/[^\s/]+/)")
# DG-42: a Markdown link, or a relative path naming at least one folder (references/x.md, ../westack/references/x.md).
# A bare file name in prose is not a path.
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NAMED_PATH = re.compile(r"(?<![\w.-])((?:[\w.-]+/)+[\w.-]+\.md)\b")


def front_matter(text):
    """Parse the small front-matter subset hosts share; return (keys, errors). Strict: our own packages."""
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


def _unquote(value):
    """Lenient scalar text for foreign skills: simple quotes removed, anything else kept verbatim."""
    value = value.strip()
    safe = plain_scalar(value) if value else ""
    if safe is not None:
        return safe
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
    return value


def skill_metadata(text):
    """Lenient parse of any skill's front matter: (top-level keys, metadata map, errors).

    Accepts CRLF, a byte-order mark, unknown keys and block scalars (| or >), which other packs use.
    Values are scalar text; nested lists (allowed-tools) are ignored. Never raises on content.
    """
    text = text.lstrip("﻿").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        return {}, {}, ["missing --- block"]
    keys, meta, errors = {}, {}, []
    current, block = None, None
    for line in match[1].split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t":
            if block is not None:
                block.append(line.strip())
            elif current == "metadata":
                parsed = re.fullmatch(r"\s+([A-Za-z0-9_.-]+):(?: (.*))?", line)
                if parsed:
                    if parsed[1] in meta:
                        errors.append("duplicate metadata key " + parsed[1])
                    meta[parsed[1]] = _unquote(parsed[2] or "")
                else:
                    errors.append("unparseable metadata line")
            continue
        block = None
        parsed = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):(?: (.*))?", line)
        if not parsed:
            errors.append("unparseable line")
            current = None
            continue
        key, value = parsed[1], (parsed[2] or "").strip()
        if key in keys:
            errors.append("duplicate key " + key)
        current = key
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            keys[key] = block
        else:
            keys[key] = _unquote(value)
    for key, value in list(keys.items()):
        if isinstance(value, list):
            keys[key] = " ".join(value)
    return keys, meta, errors


def parse_version(text):
    """(major, minor, patch, prerelease identifiers) for a full semantic version, else None."""
    match = SEMVER.fullmatch(text.strip()) if isinstance(text, str) else None
    if not match:
        return None
    return int(match[1]), int(match[2]), int(match[3]), tuple(match[4].split(".")) if match[4] else ()


def compare_versions(a, b):
    """Semantic-version precedence of two parsed versions: -1, 0 or 1."""
    if a[:3] != b[:3]:
        return -1 if a[:3] < b[:3] else 1
    pa, pb = a[3], b[3]
    if pa == pb:
        return 0
    if not pa or not pb:
        return 1 if not pa else -1  # a release outranks its prereleases
    for x, y in zip(pa, pb):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return -1 if int(x) < int(y) else 1
        if x.isdigit() or y.isdigit():
            return -1 if x.isdigit() else 1  # numeric identifiers rank lower
        return -1 if x < y else 1
    return -1 if len(pa) < len(pb) else 1


def parse_range(text):
    """[(operator, version)] for a space-separated range such as ">=1.0.0-alpha.0 <2", else None.

    Missing minor or patch parts are 0. "<X" with no prerelease also excludes X's prereleases
    (it means "<X-0"), so "<2" never admits 2.0.0-alpha.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    result = []
    for token in text.split():
        match = _COMPARATOR.fullmatch(token)
        partial = _PARTIAL.fullmatch(match[2]) if match else None
        if not partial:
            return None
        version = (int(partial[1]), int(partial[2] or 0), int(partial[3] or 0),
                   tuple(partial[4].split(".")) if partial[4] else ())
        operator = match[1] or "="
        if operator == "<" and not version[3]:
            version = version[:3] + (("0",),)
        result.append((operator, version))
    return result


def satisfies(version, comparators):
    """True when a parsed version meets every (operator, version) comparator."""
    tests = {"=": lambda c: c == 0, ">": lambda c: c > 0, ">=": lambda c: c >= 0,
             "<": lambda c: c < 0, "<=": lambda c: c <= 0}
    return all(tests[op](compare_versions(version, bound)) for op, bound in comparators)


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


def is_shipped(relative):
    """True when a path relative to a skill's root belongs in an installed or run copy (see SHIP_EXCLUDE_DIRS)."""
    parts = [part for part in str(relative).replace("\\", "/").split("/") if part and part != "."]
    if not parts:
        return True  # the skill's own root
    if parts[0] in SHIP_EXCLUDE_DIRS or any(part in CACHE_DIRS for part in parts):
        return False
    return not parts[-1].endswith(CACHE_SUFFIXES)


def shipped_files(root):
    """The files of a skill folder that ship: package_files (links refused) less the answer key and the caches."""
    root = pathlib.Path(root)
    return [path for path in package_files(root) if is_shipped(path.relative_to(root).as_posix())]


def ship_ignore(root):
    """A shutil.copytree `ignore` that copies exactly what is_shipped allows (and never an install manifest)."""
    root = pathlib.Path(root).resolve()

    def ignore(directory, names):
        try:
            relative = pathlib.Path(directory).resolve().relative_to(root).as_posix()
        except ValueError:
            relative = ""
        prefix = "" if relative in ("", ".") else relative + "/"
        return {name for name in names if name == INSTALL_MANIFEST or not is_shipped(prefix + name)}
    return ignore


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
    name = keys.get("name")
    if not name or not NAME.fullmatch(name):
        problems.append("name must be westack or westack-<slug>")
    elif name != root.name:
        # A host keys a skill by its folder, so a name that differs from it can stop the skill triggering.
        errors.append("skill name " + name + " differs from its folder name " + root.name + "; rename one so they match")
    description = plain_scalar(keys["description"]) if keys.get("description") else None
    if not description:
        problems.append("description missing or not a safe plain/quoted YAML scalar")
    elif len(description) > 1024:
        problems.append("description exceeds 1024 characters")
    if "compatibility" in keys:
        compatibility = plain_scalar(keys["compatibility"]) if keys["compatibility"] else None
        if not compatibility or len(compatibility) > 500:
            problems.append("compatibility must be a safe scalar of 1-500 characters")
    _, meta, meta_errors = skill_metadata(text)
    problems.extend(meta_errors)
    if "stack" not in meta:
        problems.append("metadata.stack missing (every westack skill carries metadata.stack: westack)")
    elif meta["stack"] != STACK:
        problems.append("metadata.stack must be westack, found " + meta["stack"])
    if parse_version(meta.get("version", "")) is None:
        problems.append("metadata.version missing or not a semantic version")
    if name and NAME.fullmatch(name) and name != STACK and parse_range(meta.get("requires_core", "")) is None:
        problems.append("a westack-* sub-skill needs metadata.requires_core, a version range such as \">=1.0.0-alpha.0 <2\"")
    errors.extend("invalid skill trigger metadata (front matter): " + x for x in problems)
    for file in (path for path in files if path.suffix == ".md"):
        ships = is_shipped(file.relative_to(root).as_posix())
        for target in MD_LINK.findall(file.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            relative = target.split("#")[0]
            path = (file.parent / relative).resolve()
            if not path.is_relative_to(root) or not path.exists():
                errors.append(str(file.relative_to(root)) + ": broken/escaping reference " + target)
            elif ships and not is_shipped(path.relative_to(root).as_posix()):
                errors.append(str(file.relative_to(root)) + ": reference " + target + " does not ship (its folder is "
                              "left out of installed and run copies); name the path in code instead of linking it")
    reached = reached_files(root)
    orphans = [path for path in files if path.suffix == ".md" and path.resolve() not in reached
               and is_shipped(path.relative_to(root).as_posix()) and path.relative_to(root).parts[0] == "references"]
    if orphans:
        named = set()
        for sibling in _westack_siblings(root):
            named |= reached_files(sibling)
        errors.extend(path.relative_to(root).as_posix() + ": reference page not reached; link it or name its path "
                      "from SKILL.md, a page SKILL.md reaches, or another westack skill beside this one (DG-42)"
                      for path in orphans if path.resolve() not in named)
    return errors


def _named(file, root):
    """The files one Markdown file links to or names by a relative path, resolved from its folder or the skill root."""
    text = file.read_text(encoding="utf-8")
    out = set()
    for target in MD_LINK.findall(text):
        if not target.startswith(("https://", "http://", "#")):
            out.add((file.parent / target.split("#")[0]).resolve())
    for path in NAMED_PATH.findall(text):
        out.update(p for p in ((file.parent / path).resolve(), (root / path).resolve()) if p.is_file())
    return out


def reached_files(root):
    """DG-42: every file reached from root/SKILL.md through links and named paths in the skill's shipped Markdown,
    including another skill's files it names (those are listed, never read). Empty for an unreadable package."""
    root = pathlib.Path(root).resolve()
    try:
        shipped = {path.resolve() for path in shipped_files(root) if path.suffix == ".md"}
        seen, todo = set(), [(root / "SKILL.md").resolve()]
        while todo:
            file = todo.pop()
            if file in seen:
                continue
            seen.add(file)
            if file in shipped:
                todo.extend(_named(file, root) - seen)
        return seen
    except (OSError, ValueError):
        return set()


def _westack_siblings(root):
    """The westack skills beside root (a folder named westack or westack-*, holding a SKILL.md, not a link)."""
    try:
        folders = sorted(pathlib.Path(root).parent.iterdir())
    except OSError:
        return []
    return [p for p in folders if p != root and NAME.fullmatch(p.name) and not is_link(p.lstat())
            and (p / "SKILL.md").is_file()]


def package_warnings(root):
    """Advisory lints for a skill package, as strings; check_package holds the errors.

    Over shipped Markdown: a file that opens "Step 1" twice, more than MAX_STEPS numbered steps in one file, and
    a hard-coded machine path (a user's home folder). Never raises: an unreadable package has no lints, and
    check_package reports it.
    """
    root = pathlib.Path(root).resolve()
    try:
        files = shipped_files(root)
    except (OSError, ValueError):
        return []
    warnings = []
    for file in (path for path in files if path.suffix == ".md"):
        relative = file.relative_to(root).as_posix()
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(STEP_ONE.findall(text)) > 1:
            warnings.append(relative + ": repeated 'Step 1' blocks (one procedure restarted, or a copied section)")
        steps = max((int(n) for n in STEP_NUMBER.findall(text)), default=0)
        if steps > MAX_STEPS:
            warnings.append(relative + ": over-numbered: " + str(steps) + " steps (more than " + str(MAX_STEPS) + ")")
        found = MACHINE_PATH.search(text)
        if found:
            warnings.append(relative + ": hard-coded machine path " + found.group(0) + " (a skill is read on other machines)")
    return warnings
