"""Rename guard: the skill once called "e-stack" is now westack, and no live file may say otherwise.

The guard scans every shipped file, and every file name, for the old name as a word start (a letter or digit
before it makes it part of another word, so the new name is never a hit). Each kept occurrence is listed in
KEEP with its keep rule from the 2026-10-28 rename spec and an exact count, so a new occurrence in a kept
receipt fails too. A plain find-and-replace of the old name turns the new name into a doubled prefix;
that is checked separately.

Written red first: it failed against the tree before the rename. The control cases below plant a violation in
a disposable copy of the package and require the scanner to notice it, so a scanner that stopped matching
would fail here rather than pass silently. Nothing outside the results directory is written.
"""
import json
import os
from pathlib import Path
import re
import shutil
import traceback

PACKAGE = Path(__file__).resolve().parents[1]
# Built from parts so that this file is not itself a hit.
OLD = "e" + "stack"
NEW = "w" + OLD
DOUBLED = "w" + NEW
HIT = re.compile(r"(?<![A-Za-z0-9])" + OLD, re.IGNORECASE)
HIT_BYTES = re.compile(rb"(?<![A-Za-z0-9])" + OLD.encode(), re.IGNORECASE)
# Live prose that states a fact about a version shipped under the old name may say this once per file.
THEN_CALLED = NEW + " (then called " + OLD + ")"

# Kept verbatim. Key: path relative to the package root, or "repo:" plus the path relative to the repository
# root (checked only inside a checkout). Value: (keep rule, exact number of matches or None, why).
# Keep rules (rename spec, 2026-10-28): 1 receipts and logs; 2 changelog and release notes of versions released
# before the rename; 3 hash-pinned inputs; 4 wire identifiers (none in this package); 5 the other project and
# its names; 6 real paths outside our repositories.
ARCHIVE = "repo:research/2026-10-26/kappa-implementation/"
KEEP = {
    "BUILD_REPORT.md": (2, 4, "release notes of the pre-rename 0.1.x iterations; also an engineering record"),
    "CHANGELOG.md": (5, 2, "the rename entry names the other project and its names"),
    # Public edition: the receipts and review records under evidence/ that carried the old name are omitted
    # (public-build.json), so their rows are removed here. Every other row is unchanged.
    "research/FRANKENMINE_DESIGN_SPEC.md": (3, 4, "pinned by SOURCE_HASHES in scripts/package.py"),
    ARCHIVE + "implementation-results.md": (1, 1, "engineering record of the 2026-10-26 local update"),
    ARCHIVE + "installed-baseline-v012.json": (1, 3, "installed-baseline snapshot; hashes a file by its old name"),
    ARCHIVE + "local-update-plan.json": (1, 3, "update plan receipt; hashes a file by its old name"),
    ARCHIVE + "local-update-result.json": (1, 3, "update result receipt; hashes a file by its old name"),
    ARCHIVE + "frankenmine-0.1.3.zip": (1, None, "binary archive of the 0.1.3 package; matches inside it are not counted"),
}


class Scan:
    def __init__(self):
        self.labels = set()
        self.found = {}
        self.doubled = []
        self.phrase = {}
        self.problems = []


def repo_root():
    """The repository root when this package sits in skills/<name> of a checkout, else None."""
    top = PACKAGE.parents[1]
    if PACKAGE.parent.name == "skills" and (top / ".git").exists() and (top / ".gitattributes").is_file() \
            and (top / "research").is_dir():
        return top
    return None


def _walk(root, skip=(".git", "__pycache__")):
    for directory, folders, names in os.walk(root):
        folders[:] = sorted(name for name in folders if name not in skip)
        for name in sorted(names):
            if not name.endswith(".pyc"):
                yield Path(directory) / name


def _examine(scan, path, label):
    raw = path.read_bytes()
    scan.labels.add(label)
    hits = len(HIT.findall(label))
    if DOUBLED in label.lower():
        scan.doubled.append(label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        hits += len(HIT_BYTES.findall(raw))
        if DOUBLED.encode() in raw.lower():
            scan.doubled.append(label)
    else:
        uses = text.count(THEN_CALLED)
        if uses:
            scan.phrase[label] = uses
        hits += len(HIT.findall(text.replace(THEN_CALLED, "")))
        if DOUBLED in text.lower():
            scan.doubled.append(label)
    if hits:
        scan.found[label] = hits


def scan_tree(package, repo=None):
    scan = Scan()
    for path in _walk(package):
        _examine(scan, path, path.relative_to(package).as_posix())
    if repo is not None:
        readme = repo / "README.md"
        if readme.is_file():
            _examine(scan, readme, "repo:README.md")
        # The repository's .gitignore excludes research/**/disposable/ (generated test workspaces).
        for path in _walk(repo / "research", skip=(".git", "__pycache__", "disposable")):
            _examine(scan, path, "repo:" + path.relative_to(repo).as_posix())
    for label, hits in sorted(scan.found.items()):
        entry = KEEP.get(label)
        if entry is None:
            scan.problems.append(label + ": " + str(hits) + " old-name reference(s) outside the allowlist")
        elif entry[1] is not None and entry[1] != hits:
            scan.problems.append(label + ": " + str(hits) + " old-name reference(s); the allowlist (keep rule "
                                 + str(entry[0]) + ") expects " + str(entry[1]))
    for label in sorted(KEEP):
        if label.startswith("repo:") and repo is None:
            continue
        if label not in scan.labels:
            scan.problems.append(label + ": allowlisted file is missing")
        elif label not in scan.found:
            scan.problems.append(label + ": allowlisted, but no old-name reference remains; drop the entry")
    for label, uses in sorted(scan.phrase.items()):
        if uses > 1:
            scan.problems.append(label + ": the 'then called' note appears " + str(uses) + " times; once per file")
    for label in sorted(set(scan.doubled)):
        scan.problems.append(label + ": doubled prefix (a plain find-and-replace of the old name)")
    return scan


def run_tests(test, scratch):
    repo = repo_root()
    base = scratch / "rename-guard"

    def real_scan():
        return scan_tree(PACKAGE, repo)

    def copy_of(name):
        target = base / name
        assert not target.exists(), target
        shutil.copytree(PACKAGE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return target

    def append(target, relative, text):
        path = target / relative
        path.write_bytes(path.read_bytes() + text.encode("utf-8"))

    def by_rule(scan):
        counts = {}
        for label, hits in scan.found.items():
            rule = KEEP[label][0]
            counts[rule] = counts.get(rule, 0) + hits
        return "; ".join("keep rule " + str(rule) + ": " + str(counts[rule]) for rule in sorted(counts))

    def no_old_name():
        scan = real_scan()
        assert not scan.problems, "\n" + "\n".join(scan.problems)
        return (str(len(scan.labels)) + " files scanned" + ("" if repo else " (package only)") + "; kept references "
                + str(sum(scan.found.values())) + " in " + str(len(scan.found)) + " files; " + by_rule(scan))
    test("rename guard: no old-name reference outside the allowlist", no_old_name)

    def no_doubled():
        scan = real_scan()
        assert not scan.doubled, scan.doubled
        return "no doubled prefix in " + str(len(scan.labels)) + " files or file names"
    test("rename guard: no doubled prefix anywhere", no_doubled)

    def planted_live():
        target = copy_of("planted-live")
        before = set(scan_tree(target).problems)
        append(target, "SKILL.md", "\nA stray mention of " + OLD + " in a live file.\n")
        new = set(scan_tree(target).problems) - before
        assert any(p.startswith("SKILL.md:") for p in new), new
        return "planted reference in SKILL.md reported: " + sorted(new)[0]
    test("rename guard control: a planted old-name reference in a live file is caught", planted_live)

    def planted_name():
        target = copy_of("planted-name")
        before = set(scan_tree(target).problems)
        (target / "examples" / (OLD + "-extra.md")).write_text("# extra\n", encoding="utf-8")
        new = set(scan_tree(target).problems) - before
        assert any(p.startswith("examples/" + OLD + "-extra.md:") for p in new), new
        return "planted file name reported: " + sorted(new)[0]
    test("rename guard control: a planted old-name file name is caught", planted_name)

    def planted_receipt():
        target = copy_of("planted-receipt")
        before = set(scan_tree(target).problems)
        append(target, "BUILD_REPORT.md", "\n" + OLD + "\n")
        new = set(scan_tree(target).problems) - before
        assert any(p.startswith("BUILD_REPORT.md:") and "expects 4" in p for p in new), new
        return "extra match in a kept receipt reported: " + sorted(new)[0]
    test("rename guard control: an extra old-name match inside a kept receipt is caught", planted_receipt)

    def planted_doubled():
        target = copy_of("planted-doubled")
        before = set(scan_tree(target).problems)
        append(target, "README.md", "\nA doubled prefix, " + DOUBLED + ", from a plain replace.\n")
        scan = scan_tree(target)
        new = set(scan.problems) - before
        assert "README.md" in scan.doubled and any("doubled prefix" in p for p in new), new
        return "planted doubled prefix reported: " + sorted(new)[0]
    test("rename guard control: a planted doubled prefix is caught", planted_doubled)

    def new_name_is_clean():
        target = copy_of("new-name-clean")
        before = set(scan_tree(target).problems)
        append(target, "SKILL.md", "\n" + NEW + " " + NEW.capitalize() + " " + NEW.upper() + " my-" + NEW + " "
               + NEW + "/" + NEW + "\n" + THEN_CALLED + "\n")
        assert set(scan_tree(target).problems) == before, set(scan_tree(target).problems) ^ before
        append(target, "SKILL.md", THEN_CALLED + "\n")
        twice = set(scan_tree(target).problems) - before
        assert any("'then called' note appears 2 times" in p for p in twice), twice
        return "new name and one 'then called' note are clean; a second note is reported"
    test("rename guard control: the new name is not flagged, one 'then called' note per file", new_name_is_clean)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    results = []

    def test(name, fn):
        try:
            results.append(dict(name=name, status="pass", detail=fn()))
        except Exception:
            results.append(dict(name=name, status="fail", raw=traceback.format_exc()))
    run_tests(test, out)
    summary = dict(total=len(results), passed=sum(r["status"] == "pass" for r in results),
                   failed=sum(r["status"] == "fail" for r in results))
    (out / "results.json").write_text(json.dumps(dict(summary, tests=results), indent=2, default=str) + "\n",
                                      encoding="utf-8")
    for r in results:
        print(r["status"].upper(), "-", r["name"])
        print("   ", (r.get("detail") or r.get("raw") or "").strip().replace("\n", "\n    "))
    print(json.dumps(summary, indent=2))
    raise SystemExit(1 if summary["failed"] else 0)
