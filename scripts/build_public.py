"""Generate public skill editions from their canonical sources. Standard library only.

    python -B scripts/build_public.py --westack DIR [--frankenmine DIR] [--adopt-adapt DIR] [--check]

Each named skill is copied from its canonical directory into a fresh staging
directory inside this repository, minus the exclude globs in public-build.json,
with its overlays and any description override applied. The staged copy must
contain no links or junctions, pass the collection's leak-pattern scan and
local-link check, and carry a copy of shared/evidence-vocabulary.md that is byte-identical (required
only where the skill links to references/evidence-vocabulary.md; any copy present must match).
Only when every named skill passes is skills/<name> replaced. --check stages and
checks without replacing anything. Canonical sources are only read.

Exclude globs match whole POSIX paths relative to the skill: "*" stays within one
path segment, "**" spans segments, and a leading "!" re-includes. The last
matching pattern wins, as in .gitignore. A pattern that matches nothing fails.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAME = "public-build.json"
OVERLAY_DIR = "public-overlays"
STAGING_NAME = ".public-build"
FORMAT = "skill-belt-public-build-1"
# Generated content is never published; verify.py does not scan these directories either.
GENERATED_DIRS = {".git", ".validation", "__pycache__"}
GENERATED_SUFFIXES = (".pyc", ".pyo")
SHA256 = re.compile(r"[0-9a-f]{64}")


def _load(name):
    spec = importlib.util.spec_from_file_location("belt_" + name + "_for_build", Path(__file__).resolve().with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _load("verify")


def adopt_adapt_release(stage):
    """adopt-adapt's release.json from the staged skill's own scripts/package.py manifest(), which hashes what is present."""
    spec = importlib.util.spec_from_file_location("staged_adopt_adapt_package", Path(stage) / "scripts/package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (json.dumps(module.manifest(Path(stage)), indent=2) + "\n").encode("utf-8")


# Files that describe the published bytes themselves, so they are generated in staging, not copied.
# westack has none: 0.3.1 deliberately ships no package manifest, and its own rename guard scans every published file.
GENERATED_FILES = {"adopt-adapt": {"release.json": adopt_adapt_release}}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(files):
    """One digest for a {path: bytes} tree, so a rebuild from the same input is checkable."""
    lines = "".join(path + "\0" + sha256(data) + "\n" for path, data in sorted(files.items()))
    return sha256(lines.encode("utf-8"))


def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def portable(text, glob=False):
    """A relative POSIX path (or glob) with no drive, backslash, empty, '.' or '..' segment."""
    allowed = r"[^\\:\"<>|\x00-\x1f]+" if glob else r"[^\\:*?\"<>|\x00-\x1f]+"
    return (isinstance(text, str) and bool(re.fullmatch(allowed, text)) and not text.startswith("/")
            and all(part not in ("", ".", "..") for part in text.split("/")))


def glob_regex(pattern):
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts))


def load_config(root):
    config = json.loads((root / CONFIG_NAME).read_text(encoding="utf-8"))
    if config.get("format") != FORMAT or not isinstance(config.get("skills"), dict):
        raise ValueError(CONFIG_NAME + ": expected format " + FORMAT + " with a skills object")
    for name, entry in config["skills"].items():
        where = CONFIG_NAME + ": " + name
        unknown = set(entry) - {"exclude", "overlays", "description", "notes"}
        if unknown:
            raise ValueError(where + ": unknown keys " + ", ".join(sorted(unknown)))
        for pattern in entry.get("exclude", []):
            if not portable(pattern.removeprefix("!") if isinstance(pattern, str) else None, glob=True):
                raise ValueError(where + ": exclude pattern is not a relative POSIX glob: " + repr(pattern))
        for relative, spec in entry.get("overlays", {}).items():
            if not portable(relative) or not isinstance(spec, dict) or not SHA256.fullmatch(str(spec.get("base_sha256"))):
                raise ValueError(where + ": overlay " + repr(relative) + " needs a portable path and a base_sha256")
            if set(spec) - {"base_sha256", "reason"}:
                raise ValueError(where + ": overlay " + relative + " has unknown keys")
        description = entry.get("description")
        if description is not None:
            text = description.get("text") if isinstance(description, dict) else None
            if (not SHA256.fullmatch(str(description.get("base_sha256"))) or not isinstance(text, str)
                    or not text.strip() or "\n" in text or "\r" in text or set(description) - {"base_sha256", "text", "reason"}):
                raise ValueError(where + ": description needs base_sha256 and a one-line text")
            if "SKILL.md" in entry.get("overlays", {}):
                raise ValueError(where + ": use either a SKILL.md overlay or a description override, not both")
    return config


def canonical_files(source):
    """Regular files under source keyed by POSIX path; links are refused before descent."""
    files, skipped = {}, []

    def unreadable(exc):
        raise ValueError("Unreadable canonical directory: " + str(exc))

    for directory, folders, names in os.walk(source, followlinks=False, onerror=unreadable):
        here = Path(directory)
        for name in folders + names:
            path = here / name
            relative = path.relative_to(source).as_posix()
            info = path.lstat()
            if is_link(info):
                raise ValueError("Link or junction in canonical source: " + relative)
            if name in names and not stat.S_ISREG(info.st_mode):
                raise ValueError("Nonregular file in canonical source: " + relative)
        skipped.extend((here / name).relative_to(source).as_posix() + "/" for name in folders if name in GENERATED_DIRS)
        folders[:] = sorted(name for name in folders if name not in GENERATED_DIRS)
        for name in sorted(names):
            relative = (here / name).relative_to(source).as_posix()
            if name.endswith(GENERATED_SUFFIXES):
                skipped.append(relative)
            else:
                with open(here / name, "rb") as handle:
                    files[relative] = handle.read()
    return files, skipped


def select(files, patterns, name):
    rules = [(pattern.startswith("!"), glob_regex(pattern.removeprefix("!")), pattern) for pattern in patterns]
    used, kept, excluded = set(), {}, []
    for relative, data in files.items():
        drop = False
        for negate, regex, pattern in rules:
            if regex.fullmatch(relative):
                drop = not negate
                used.add(pattern)
        if drop:
            excluded.append(relative)
        else:
            kept[relative] = data
    stale = [pattern for pattern in patterns if pattern not in used]
    if stale:
        raise ValueError(name + ": exclude pattern matches nothing (update " + CONFIG_NAME + "): " + ", ".join(stale))
    return kept, excluded


def apply_overlays(files, excluded, overlays, root, name):
    folder = root / OVERLAY_DIR / name
    present = set(verify.source_files(folder)) if folder.is_dir() else set()
    if present != set(overlays):
        raise ValueError(name + ": overlay files and " + CONFIG_NAME + " disagree: "
                         + ", ".join(sorted(present ^ set(overlays))))
    for relative, spec in sorted(overlays.items()):
        if relative not in files:
            state = "is excluded" if relative in excluded else "has no canonical file"
            raise ValueError(name + ": overlay " + relative + " " + state)
        base = sha256(files[relative])
        if base != spec["base_sha256"]:
            raise ValueError(name + ": overlay base drifted for " + relative + ": canonical sha256 is " + base
                             + ", the overlay was made from " + spec["base_sha256"] + ". Re-derive "
                             + OVERLAY_DIR + "/" + name + "/" + relative + " from the canonical file, then update base_sha256.")
        files[relative] = (folder / relative).read_bytes()


def apply_description(files, description, name):
    data = files.get("SKILL.md")
    text = data.decode("utf-8") if data is not None else ""
    front = re.match(r"---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not front:
        raise ValueError(name + ": description override needs SKILL.md front matter")
    start = front.start(1)
    lines = list(re.finditer(r"^description: ?(.*?)\r?$", front.group(1), re.M))
    if len(lines) != 1:
        raise ValueError(name + ": SKILL.md front matter needs exactly one description line")
    value = lines[0].group(1)
    if not value or value[0] in ">|":
        raise ValueError(name + ": only a one-line SKILL.md description can be overridden")
    if sha256(value.encode("utf-8")) != description["base_sha256"]:
        raise ValueError(name + ": description override base drifted: the canonical SKILL.md description now hashes to "
                         + sha256(value.encode("utf-8")) + "; review the new text, then update text and base_sha256.")
    begin, end = start + lines[0].start(1), start + lines[0].end(1)
    files["SKILL.md"] = (text[:begin] + description["text"] + text[end:]).encode("utf-8")


def write_stage(files, stage, stage_root):
    for relative, data in files.items():
        target = (stage / relative).resolve()
        if not target.is_relative_to(stage_root):
            raise ValueError("Refusing to write outside the staging directory: " + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as handle:
            handle.write(data)


def changes(stage, current):
    new = {path: sha256(file.read_bytes()) for path, file in verify.source_files(stage).items()}
    old = {path: sha256(file.read_bytes()) for path, file in verify.source_files(current).items()} if current.is_dir() else {}
    return dict(added=sorted(set(new) - set(old)), removed=sorted(set(old) - set(new)),
                changed=sorted(path for path in set(new) & set(old) if new[path] != old[path]),
                unchanged=len([path for path in set(new) & set(old) if new[path] == old[path]]))


def stage_skill(name, source, entry, root, stage_root):
    source = Path(source).resolve(strict=True)
    if source.is_relative_to(root) or root.is_relative_to(source):
        raise ValueError(name + ": the canonical source must be a directory outside this repository")
    files, skipped = canonical_files(source)
    front = re.match(r"---\r?\n(.*?)\r?\n---", files.get("SKILL.md", b"").decode("utf-8"), re.S)
    if not front or not re.search(r"^name: " + re.escape(name) + r"\s*$", front.group(1), re.M):
        raise ValueError(name + ": " + str(source) + " is not the canonical " + name + " skill (SKILL.md name)")
    source_digest = tree_digest(files)
    files, excluded = select(files, entry.get("exclude", []), name)
    apply_overlays(files, excluded, entry.get("overlays", {}), root, name)
    if entry.get("description"):
        apply_description(files, entry["description"], name)
    stage = stage_root / name
    stage.mkdir()
    write_stage(files, stage, stage_root)
    for relative, generate in GENERATED_FILES.get(name, {}).items():
        if relative in entry.get("overlays", {}):
            raise ValueError(name + ": " + relative + " is generated by the build and cannot be overlaid")
        files[relative] = generate(stage)
        (stage / relative).write_bytes(files[relative])
    staged = verify.source_files(stage)  # refuses links; matches what verify.py will scan
    if set(staged) != set(files):
        raise ValueError(name + ": staged files differ from the selected files")
    verify.check_publication(staged, stage)
    verify.check_vocabulary(stage, name, root)
    report = dict(source_tree_sha256=source_digest, edition_tree_sha256=tree_digest(files), files=len(files),
                  excluded=len(excluded), overlays=sorted(entry.get("overlays", {})),
                  description_override=bool(entry.get("description")), skipped_generated=skipped)
    report.update(changes(stage, root / "skills" / name))
    return report


def remove_tree(path, stage_root):
    if not Path(path).resolve().is_relative_to(stage_root):
        raise ValueError("Refusing to delete outside the staging directory: " + str(path))

    def retry(function, target, *_):
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def swap(names, root, stage_root):
    """Move every current copy aside, move every staged copy in; restore all on any failure."""
    done = []
    try:
        for name in names:
            current, previous = root / "skills" / name, stage_root / (name + ".previous")
            had = current.exists()
            if had:
                os.rename(current, previous)
            done.append((name, current, previous, had))
            os.rename(stage_root / name, current)
    except OSError as exc:
        try:
            for name, current, previous, had in reversed(done):
                if current.exists() and (not had or previous.exists()):
                    os.rename(current, stage_root / (name + ".rejected"))
                if had and previous.exists():
                    os.rename(previous, current)
        except OSError as restore:
            raise ValueError("Replacement failed (" + str(exc) + ") and restoring failed (" + str(restore)
                             + "); the previous copies are under " + str(stage_root)) from exc
        remove_tree(stage_root, stage_root)
        raise ValueError("Replacement failed; skills/ was restored: " + str(exc)) from exc


def build(sources, root=ROOT, check=False):
    """Stage and check every named skill; replace skills/<name> only when all of them pass."""
    root = Path(root).resolve()
    config = load_config(root)
    unknown = sorted(set(sources) - set(config["skills"]))
    if unknown:
        raise ValueError("No " + CONFIG_NAME + " entry for: " + ", ".join(unknown))
    stage_root = root / STAGING_NAME
    if os.path.lexists(stage_root):
        raise ValueError(str(stage_root) + " already exists; an earlier build may have left previous copies there. "
                         "Inspect it, restore anything needed, then remove it.")
    stage_root.mkdir()
    names = sorted(sources)
    try:
        report = dict(mode="check" if check else "build",
                      skills={name: stage_skill(name, sources[name], config["skills"][name], root, stage_root) for name in names})
    except BaseException:
        remove_tree(stage_root, stage_root)
        raise
    if not check:
        swap(names, root, stage_root)
        report["next"] = "python -B scripts/generate_manifest.py, then python -B scripts/verify.py"
    remove_tree(stage_root, stage_root)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--westack", type=Path, help="canonical westack skill directory")
    parser.add_argument("--frankenmine", type=Path, help="canonical Frankenmine skill directory")
    parser.add_argument("--adopt-adapt", dest="adopt_adapt", type=Path, help="canonical adopt-adapt skill directory")
    parser.add_argument("--check", action="store_true", help="stage and check only; never replace skills/")
    args = parser.parse_args()
    sources = {name: path for name, path in (("adopt-adapt", args.adopt_adapt), ("westack", args.westack),
                                             ("frankenmine", args.frankenmine)) if path is not None}
    if not sources:
        parser.error("name at least one canonical skill directory")
    try:
        report = build(sources, check=args.check)
    except (OSError, ValueError) as exc:
        # Failures before replacement leave skills/ untouched; swap() reports its own state.
        print("Public build failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
