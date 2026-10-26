#!/usr/bin/env python3
"""Check package completeness and create a reproducible archive; never install it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HASHES = {
    "FRANKENMINE_DESIGN_SPEC.md": "23963bcbb31b0233d3d7d9d24acd11e45b30a96017157139c402cfd9d07b5f3d",
    "prior_art.json": "9da39037f96be4d1e579d64187e69a0577c57e63be7b22ad9d8b15e7c3c99b6b",
    "translation-research.json": "d4dcab448abebd0d4dbd38ad0558714bde6fac22349855ae800710935eef5bd6",
    "tool_map.json": "b91ec0810c20ed3dd4f1f494d71d50f6f398e48e03f8bd7b4c13d292c40ccc23",
}


def files():
    # Validate directory entries BEFORE descending: rglob traverses Windows
    # junctions, and checking only leaf symlinks leaks external source bytes.
    result = []
    def unreadable(exc):
        raise ValueError("Unreadable package directory: " + str(exc))
    for directory, folders, names in os.walk(ROOT, followlinks=False, onerror=unreadable):
        for name in list(folders) + names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Link/reparse point in package: " + str(path))
            if name in names and not stat.S_ISREG(info.st_mode):
                raise ValueError("Nonregular package file: " + str(path))
        folders[:] = sorted(name for name in folders if name != "__pycache__")
        result.extend(Path(directory) / name for name in sorted(names)
                      if not name.endswith(".pyc") and Path(directory) / name != ROOT / "MANIFEST.json")
    return sorted(result)


def validate():
    try:
        contents = files()
    except (OSError, ValueError) as exc:
        return [str(exc)]
    required = ["SKILL.md", "README.md", "agents/openai.yaml", "scripts/frankenmine.py", "schemas/run.schema.json",
                "tests/run_tests.py", "tests/fixture_builder.py", "tests/adversarial_tests.py", "evals/evals.json",
                "evals/LIVE_AGENT_PROTOCOL.md", "examples/synthetic/run.json", "examples/no-fusion/run.json"]
    errors = ["Missing " + x for x in required if not (ROOT / x).is_file()]
    for name, sha in SOURCE_HASHES.items():
        source = ROOT / "research" / name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != sha:
            errors.append("Research source hash mismatch: " + name)
        elif name.endswith(".json"):
            json.loads(source.read_bytes())
    for path in contents:
        if path.suffix == ".md":
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if re.match(r"^[a-zA-Z]+://", link) or link.startswith("#"):
                    continue
                target = (path.parent / link.split("#")[0]).resolve()
                if not target.is_relative_to(ROOT.resolve()) or not target.exists():
                    errors.append("Broken/escaping package link: " + str(path.relative_to(ROOT)) + " -> " + link)
    if not (ROOT / "SKILL.md").is_file():
        return errors
    front = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not front.startswith("---\nname: frankenmine\n") or "\ndescription: " not in front.split("---", 2)[1]:
        errors.append("Invalid skill frontmatter")
    if len(front.splitlines()) > 500:
        errors.append("SKILL.md exceeds progressive-disclosure budget")
    return errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.output and args.output.resolve().is_relative_to(ROOT.resolve()):
        print(json.dumps({"status": "fail", "errors": ["Archive output must be outside the package root"]}, indent=2))
        return 1
    errors = validate()
    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, indent=2))
        return 1
    if args.output:
        # Never overwrite an archive or install/register anything.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        entries = {str(p.relative_to(ROOT).as_posix()): p.read_bytes() for p in files()}
        manifest = {"format": "frankenmine-package-1", "scope": "Package integrity, not live-agent qualification",
                    "files": [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                              for name, raw in entries.items()]}
        entries["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, raw in sorted(entries.items()):
                info = zipfile.ZipInfo("frankenmine/" + name, date_time=(2026, 10, 26, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(args.output) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(entries):
                raise ValueError("Archive CRC/member verification failed")
            for row in manifest["files"]:
                if hashlib.sha256(archive.read("frankenmine/" + row["path"])).hexdigest() != row["sha256"]:
                    raise ValueError("Archive manifest verification failed: " + row["path"])
        data = args.output.read_bytes()
        print(json.dumps({"status": "pass", "archive": str(args.output.resolve()), "members": len(entries),
                          "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                          "live_agent_qualification": "not-run"}, indent=2))
    else:
        print(json.dumps({"status": "pass", "checks": ["required files", "source hashes", "local links",
                          "frontmatter", "progressive disclosure"], "live_agent_qualification": "not-run"}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2))
        raise SystemExit(1)
