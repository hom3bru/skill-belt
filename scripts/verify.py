"""Verify portable snapshots and run all three local skill suites. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("adopt-adapt", "frankenmine", "estack")
WINDOWS_SKIP = ("test_research.ResearchTests.test_linked_source_entry_is_rejected", "symlink creation unavailable")


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


def structure():
    all_files = source_files(ROOT)
    expected = {"skills/" + name + "/SKILL.md" for name in SKILLS}
    actual = {name for name in all_files if name.endswith("/SKILL.md")}
    if actual != expected:
        raise ValueError("Expected exactly the three collection entrypoints")
    blocked = [r"[A-Za-z]:[/\\]Users[/\\]", r"libfile_[0-9a-f]{20,}",
               r"01a[0-9a-f]{5}-[0-9a-f-]{27,}", r"github\.com/hom3bru/Maginot",
               r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{50,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]
    patterns = [re.compile(pattern) for pattern in blocked]
    for relative, path in all_files.items():
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern.search(text):
                raise ValueError("Private identifier/credential candidate in " + relative)
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", target) or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    raise ValueError("Broken/escaping local link in " + relative + ": " + target)
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
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=300, env=env)
        (output / (label + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
        (output / (label + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
        entry = dict(check=label, exit_code=result.returncode)
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
        elif label in {"frankenmine-tests", "estack-tests"}:
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
        estack = ROOT / "skills/estack"
        run("adopt-adapt-manifest", [python, "-B", "scripts/package.py", "verify", "."], aa)
        run("adopt-adapt-tests", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], aa)
        run("frankenmine-package", [python, "-B", "scripts/package.py"], fm)
        run("frankenmine-tests", [python, "-B", "tests/run_tests.py", "--output", str(output / "frankenmine-results")], fm)
        run("estack-package", [python, "-B", "scripts/validate.py", "package", "."], estack)
        run("estack-tests", [python, "-B", "tests/run.py", "--output", str(output / "estack-results.json")], estack)
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
