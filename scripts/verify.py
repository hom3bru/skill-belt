"""Verify portable snapshots and run all four local skill suites. Standard library only."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("adopt-adapt", "frankenmine", "westack", "carrier-pigeon")
# Sub-skills ship inside their parent's snapshot (skills/<parent>/skills/<name>/SKILL.md), with the parent's version and manifest row.
SUB_SKILLS = {"carrier-pigeon": ("co-audit", "co-build", "co-design", "co-research")}
WINDOWS_SKIP = ("test_research.ResearchTests.test_linked_source_entry_is_rejected", "symlink creation unavailable")
# The adopt-adapt suite alone takes about three minutes on an idle Windows machine.
DEFAULT_TIMEOUT = 900


def positive_seconds(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive number of seconds")
    return value


def text_of(output):
    if output is None:
        return ""
    return output.decode("utf-8", "replace") if isinstance(output, bytes) else output


def unittest_counts(stderr, windows=False):
    counts = re.findall(r"^Ran (\d+) tests? in ", stderr, re.M)
    if len(counts) != 1 or int(counts[0]) == 0:
        raise ValueError("Missing, ambiguous or zero unittest count")
    count = int(counts[0])
    skipped = re.search(r"skipped=(\d+)", stderr)
    skipped = int(skipped.group(1)) if skipped else 0
    skip_details = re.findall(r"^\w+ \(([^)]+)\) \.\.\. skipped '([^']+)'", stderr, re.M)
    if count <= skipped or skipped != len(skip_details):
        raise ValueError("No passing unittest cases or inconsistent skip counts")
    if skip_details and (not windows or any(tuple(item) != WINDOWS_SKIP for item in skip_details)):
        raise ValueError("Unexpected skipped unittest case")
    return dict(collected=count, passed=count - skipped, skipped=skipped,
                platform_limitations=[dict(test=test, reason=reason) for test, reason in skip_details])


def source_files(root):
    result = {}
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(name for name in folders if name not in {".git", ".validation", "__pycache__"})
        for name in folders + names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Linked publication path: " + str(path.relative_to(root)))
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix not in {".pyc", ".pyo"}:
                result[path.relative_to(root).as_posix()] = path
    return result


# Windows user paths (also JSON-escaped), private Library and session IDs,
# the private repository, and token/key shapes.
BLOCKED = [re.compile(pattern) for pattern in (
    r"[A-Za-z]:[/\\]{1,2}Users[/\\]", r"libfile_[0-9a-f]{20,}",
    r"01a[0-9a-f]{5}-[0-9a-f-]{27,}", r"github\.com/hom3bru/Maginot",
    r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{50,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
VOCABULARY = "references/evidence-vocabulary.md"

# The rename guard. The skill once called "<old>" is now westack, and "westack" contains the old name,
# so a careless find-and-replace produces a doubled prefix. The old name is assembled from pieces so
# that this file does not itself contain it.
_OLD = "e" + "stack"
STALE_NAME = re.compile(r"(?<![A-Za-z0-9])" + _OLD, re.I)
DOUBLED_PREFIX = re.compile("w" + "w" + _OLD, re.I)
KEEP_RULES = {
    "1": "receipt or log recording what ran under the old name",
    "2": "changelog entry for a version released before the rename",
    "3": "hash-pinned input whose bytes a manifest, test or record pins",
    "4": "wire identifier that feeds a hash or a stored ID",
    "5": "the other project that owns the old name, its skills, URLs and donor records",
    "6": "real path outside this repository that exists under the old name",
    "history": "one 'westack (then called <old>)' statement of a fact about a version shipped under the old name",
}
_WESTACK = "skills/westack/"


def _wire(*names):
    """A regex for the given wire identifiers, each prefixed with the old name."""
    return "(?:" + "|".join(re.escape(_OLD + "-" + name) for name in names) + ")"


# Every use of the old name in any casing, for a file whose count is fixed by the skill's own rename guard.
_ANY_CASE = r"(?i:(?<![A-Za-z0-9])" + _OLD + r")"


# Every pre-rename occurrence that may stay in a published file or path, with the keep rule that allows it.
# "path" is a whole relative path or an fnmatch glob ("*" also spans "/"). Without "pattern" the whole file
# (its text and its path) is allowed; with "pattern" only matches of that regex are, at most "max" per file.
STALE_NAME_ALLOWED = (
    dict(path="*", rule="history", max=1, pattern=r"\(then called " + _OLD + r"\)",
         why="A file stating a historical fact writes 'westack (then called <old>)' once, then uses westack"),
    dict(path="skills/frankenmine/research/FRANKENMINE_DESIGN_SPEC.md", rule="3",
         why="Research note pinned by scripts/package.py SOURCE_HASHES and research/SOURCE_PROVENANCE.json"),
    dict(path="public-overlays/frankenmine/research/FRANKENMINE_DESIGN_SPEC.md", rule="3",
         why="The redacted public copy of the same pinned note; the package.py overlay pins its published hash"),
    # skills/frankenmine: the rows of its own rename guard (tests/westack_rename_tests.py) for files this edition ships.
    # Its guard counts these exactly, so the maximum here matches it.
    dict(path="skills/frankenmine/BUILD_REPORT.md", rule="2", max=4, pattern=_ANY_CASE,
         why="Release notes of the pre-rename 0.1.x iterations; Frankenmine's guard counts exactly four"),
    dict(path="public-overlays/frankenmine/BUILD_REPORT.md", rule="2", max=4, pattern=_ANY_CASE,
         why="The overlay copy of the same release notes"),
    dict(path="skills/frankenmine/CHANGELOG.md", rule="5", max=2, pattern=_ANY_CASE,
         why="The rename entry names the other public project that owns the old names, and those names; "
             "Frankenmine's guard counts exactly two besides its one 'then called' note"),
    # skills/westack: the keep list of the 0.3.1 source (its own tests/test_rename_guard.py), whole files first.
    dict(path=_WESTACK + "CHANGELOG.md", rule="2",
         why="Entries for versions released under the old name stay as written; the rename entry names it"),
    dict(path=_WESTACK + "provenance/" + _OLD + "-0.2.0-package-manifest.json", rule="3",
         why="The 0.2.0 release manifest, kept under its old version's name"),
    dict(path=_WESTACK + "provenance/build-inputs.json", rule="3",
         why="Hashed input names inside the research archive"),
    dict(path=_WESTACK + "provenance/decisions.json", rule="1",
         why="The twenty donor decisions keep their original wording"),
    dict(path=_WESTACK + "provenance/source-qualification.json", rule="1",
         why="Source-qualification record; its format string is also a wire identifier (rule 4)"),
    dict(path=_WESTACK + "provenance/continuation.md", rule="1",
         why="Dated continuation findings"),
    dict(path=_WESTACK + "provenance/lineage.json", rule="1",
         why="The rename record; it also names the other project that owns the old name (rule 5)"),
    dict(path=_WESTACK + "tests/acceptance-results.json", rule="1",
         why="Acceptance results name the tests as they ran"),
    dict(path=_WESTACK + "provenance/ARTIFACT_REVIEW.md", rule="1",
         why="Dated review of the 2026-10-26 artifacts; ships because the skill's own rename guard lists it"),
    dict(path=_WESTACK + "tests/results/tests-final.json", rule="1",
         why="The final test receipt; ships because the skill's own rename guard lists tests/results"),
    # Wire identifiers inside live files (rule 4): changing one changes every stored patch ID or manifest.
    dict(path=_WESTACK + "scripts/validate.py", rule="4", max=2, pattern=_wire("fingerprint-v1", "manifest-v1"),
         why="Fingerprint and manifest format identifiers that feed stored hashes"),
    dict(path=_WESTACK + "contracts/contract.json", rule="4", max=1, pattern=_wire("shape-v1"),
         why="Shape identifier that feeds stored hashes"),
    dict(path=_WESTACK + "contracts/README.md", rule="4", max=1, pattern=_wire("fingerprint-v1"),
         why="Names the fingerprint wire identifier"),
    dict(path=_WESTACK + "tests/test_hardening.py", rule="4", max=1, pattern=_wire("fingerprint-v1"),
         why="Asserts the fingerprint wire identifier"),
    # The collection's published-byte listing (written by generate_manifest.py) names the rule-3 file above.
    dict(path="skills-manifest.json", rule="3", max=1,
         pattern=re.escape("provenance/" + _OLD + "-0.2.0-package-manifest.json"),
         why="Lists the 0.2.0 release manifest by its old file name"),
)


def valid_stale_name_entries(allowed):
    entries = []
    for entry in allowed:
        where = "Stale-name allowlist entry " + repr(entry.get("path") if isinstance(entry, dict) else entry)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]:
            raise ValueError(where + " needs a path")
        if entry.get("rule") not in KEEP_RULES:
            raise ValueError(where + " needs a keep rule: one of " + ", ".join(KEEP_RULES))
        if not isinstance(entry.get("why"), str) or not entry["why"].strip():
            raise ValueError(where + " needs a reason")
        limit = entry.get("max")
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise ValueError(where + " has an invalid max")
        pattern = re.compile(entry["pattern"]) if entry.get("pattern") else None
        entries.append((entry["path"], pattern, limit))
    return entries


def check_stale_names(files, allowed=None, skip=()):
    """Fail on the pre-rename name, or a doubled prefix, in any published path or text outside the allowlist.

    skip lists path prefixes to leave unscanned; nothing is skipped by default.
    """
    entries = valid_stale_name_entries(STALE_NAME_ALLOWED if allowed is None else allowed)
    skip = tuple(skip)
    problems = []
    for relative, path in sorted(files.items()):
        if skip and relative.startswith(skip):
            continue
        text = Path(path).read_text(encoding="utf-8")
        covering = [(pattern, limit) for glob, pattern, limit in entries if fnmatch.fnmatchcase(relative, glob)]
        if DOUBLED_PREFIX.search(relative):
            problems.append("Doubled prefix in the path " + relative)
        for number, line in enumerate(text.splitlines(), 1):
            if DOUBLED_PREFIX.search(line):
                problems.append("Doubled prefix in " + relative + ":" + str(number) + ": " + line.strip()[:100])
        if any(pattern is None for pattern, _ in covering):
            continue  # a whole-file entry covers this file's text and path
        if STALE_NAME.search(relative):
            problems.append("Stale name in the path " + relative)
        for pattern, limit in covering:
            found = list(pattern.finditer(text))
            if limit is not None and len(found) > limit:
                problems.append("Stale name: " + relative + " uses an allowed phrase " + str(len(found)) + " times; at most " + str(limit))
            # Blank each allowed phrase, keeping line breaks, so only the remaining text is scanned.
            text = pattern.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), text)
        for number, line in enumerate(text.splitlines(), 1):
            if STALE_NAME.search(line):
                problems.append("Stale name in " + relative + ":" + str(number) + ": " + line.strip()[:100])
    if problems:
        more = " (and " + str(len(problems) - 12) + " more)" if len(problems) > 12 else ""
        raise ValueError(str(len(problems)) + " rename problem(s): " + "; ".join(problems[:12]) + more)


def check_publication(files, root, links=True):
    """Leak-pattern scan and local-link check; every local link must resolve inside root."""
    root = Path(root).resolve()
    for relative, path in files.items():
        text = path.read_text(encoding="utf-8")
        for pattern in BLOCKED:
            if pattern.search(text):
                raise ValueError("Private identifier/credential candidate in " + relative)
        if links and path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", target) or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError("Broken/escaping local link in " + relative + ": " + target)


def links_to_vocabulary(skill):
    """True when a Markdown file in the skill links to the skill's own references/evidence-vocabulary.md."""
    skill = Path(skill).resolve()
    target = (skill / VOCABULARY).resolve()
    for relative, path in source_files(skill).items():
        if path.suffix != ".md" or path.resolve() == target:
            continue
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", link) or link.startswith("#"):
                continue
            if (path.parent / link.split("#", 1)[0]).resolve() == target:
                return True
    return False


def check_vocabulary(skill, name, root):
    """A copy of the evidence vocabulary is required only if the skill's files link to it; any copy must equal shared/."""
    master = (Path(root) / "shared/evidence-vocabulary.md").read_bytes()
    copy = Path(skill) / VOCABULARY
    if copy.exists():
        if not copy.is_file() or copy.read_bytes() != master:
            raise ValueError("The evidence vocabulary in " + name + " differs from shared/evidence-vocabulary.md")
    elif links_to_vocabulary(skill):
        raise ValueError("Missing evidence vocabulary copy in " + name + ": " + VOCABULARY + " (linked from the skill's files)")


def structure():
    all_files = source_files(ROOT)
    expected = {"skills/" + name + "/SKILL.md" for name in SKILLS}
    expected |= {"skills/" + parent + "/skills/" + sub + "/SKILL.md" for parent, subs in SUB_SKILLS.items() for sub in subs}
    actual = {name for name in all_files if name.endswith("/SKILL.md")}
    if actual != expected:
        raise ValueError("Expected exactly the four collection entrypoints and their declared sub-skills; unexpected: "
                         + ", ".join(sorted(actual - expected)) + "; missing: " + ", ".join(sorted(expected - actual)))
    for name in SKILLS:
        check_vocabulary(ROOT / "skills" / name, name, ROOT)
    # Overlay links resolve inside the skill they replace a file in; build_public.py checks them there.
    overlays = {name: path for name, path in all_files.items() if name.startswith("public-overlays/")}
    check_publication({name: path for name, path in all_files.items() if name not in overlays}, ROOT)
    check_publication(overlays, ROOT, links=False)
    check_stale_names(all_files)
    manifest = json.loads((ROOT / "skills-manifest.json").read_text(encoding="utf-8"))
    if {row["name"] for row in manifest["skills"]} != set(SKILLS):
        raise ValueError("Collection manifest identities differ")
    for row in manifest["skills"]:
        root = ROOT / "skills" / row["name"]
        expected_files = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in source_files(root).items()}
        if expected_files != row["files"]:
            raise ValueError("Published-byte snapshot mismatch: " + row["name"])
    return len(all_files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new directory for raw verification output")
    parser.add_argument("--timeout", type=positive_seconds, default=DEFAULT_TIMEOUT,
                        help="seconds allowed for each check (default %(default)s)")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Verification requires assertions; remove -O/PYTHONOPTIMIZE")
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="skill-belt-verification-"))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    records = []
    def run(label, command, cwd=ROOT):
        print(label, flush=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=args.timeout, env=env)
        except subprocess.TimeoutExpired as exc:
            # Keep whatever the check printed; a slow machine should look slow, not broken.
            (output / (label + ".stdout.txt")).write_text(text_of(exc.stdout), encoding="utf-8")
            (output / (label + ".stderr.txt")).write_text(text_of(exc.stderr), encoding="utf-8")
            records.append(dict(check=label, exit_code=None, seconds=round(time.monotonic() - started, 1), timed_out=True))
            raise ValueError(label + " timed out after " + str(args.timeout) + " s; partial output is in "
                             + str(output) + "; rerun on a quieter machine or raise --timeout")
        (output / (label + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
        (output / (label + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
        entry = dict(check=label, exit_code=result.returncode, seconds=round(time.monotonic() - started, 1))
        records.append(entry)
        if result.returncode:
            # Keep CI failures diagnosable when its temporary directory is gone.
            # The full raw output remains in the selected results directory.
            if result.stdout:
                print(result.stdout[-16000:], file=sys.stderr)
            if result.stderr:
                print(result.stderr[-16000:], file=sys.stderr)
            raise ValueError(label + " failed; inspect " + str(output))
        if label in {"adopt-adapt-tests", "collection-tests"}:
            entry.update(unittest_counts(result.stderr, windows=label == "adopt-adapt-tests" and os.name == "nt"))
        elif label in {"frankenmine-tests", "westack-tests", "carrier-pigeon-tests"}:
            counts = json.loads(result.stdout)
            total = counts.get("total", counts.get("collected", 0))
            if total <= 0 or counts["failed"] or counts["skipped"] or counts["passed"] != total:
                raise ValueError(label + " has empty, failing, skipped or inconsistent counts")
            entry.update(collected=total, passed=counts["passed"], skipped=0)
    try:
        count = structure()
        python = sys.executable
        run("collection-tests", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])
        aa = ROOT / "skills/adopt-adapt"
        fm = ROOT / "skills/frankenmine"
        westack = ROOT / "skills/westack"
        run("adopt-adapt-manifest", [python, "-B", "scripts/package.py", "verify", "."], aa)
        run("adopt-adapt-tests", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], aa)
        run("frankenmine-package", [python, "-B", "scripts/package.py"], fm)
        run("frankenmine-tests", [python, "-B", "tests/run_tests.py", "--output", str(output / "frankenmine-results")], fm)
        run("westack-package", [python, "-B", "scripts/validate.py", "package", "."], westack)
        run("westack-tests", [python, "-B", "tests/run.py", "--output", str(output / "westack-results.json")], westack)
        run("carrier-pigeon-tests", [python, "-B", "tests/run.py"], ROOT / "skills/carrier-pigeon")
        structure()  # Tests must not mutate the published snapshots.
        status = "passed-with-platform-limitation" if any(row.get("skipped", 0) for row in records) else "passed"
        summary = dict(status=status, publication_files=count, checks=records,
                       scope="snapshot, link, publication-pattern and authored helper/fixture checks; no agent/host qualification")
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(dict(status=status, checks=len(records), results=str(output)), indent=2))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        (output / "summary.json").write_text(json.dumps(dict(status="failed", error=str(exc), checks=records), indent=2) + "\n", encoding="utf-8")
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
