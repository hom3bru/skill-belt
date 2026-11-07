"""westack Minimum Core block: inject the generated block into every westack-* sub-skill, or check
that each copy matches its source byte for byte.

  python build_core_block.py check  [--skills-dir DIR]
  python build_core_block.py inject [--skills-dir DIR]

The source is references/minimum-core.md in this core (at most 25 lines). Each sub-skill marks the
block's place with two lines of their own:

  <!-- westack:minimum-core:start -->
  <!-- westack:minimum-core:end -->

Only folders named westack-* whose front matter carries metadata.stack: westack are touched; any other
folder is skipped and never written. --skills-dir defaults to the folder holding this core. Exit 0
when every copy matches (check) or was written and re-verified (inject), else 1. Runs nothing.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

FORMAT = "westack-core-block-1"
START = "<!-- westack:minimum-core:start -->"
END = "<!-- westack:minimum-core:end -->"
MAX_LINES = 25


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


meta = _sibling("skillmeta")
CORE = pathlib.Path(__file__).resolve().parents[1]
SOURCE = CORE / "references" / "minimum-core.md"


def locate(data):
    """(start, end) byte offsets of the block between the marker lines, or raise ValueError."""
    lines = data.split(b"\n")
    starts = [i for i, line in enumerate(lines) if line.rstrip(b"\r") == START.encode()]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b"\r") == END.encode()]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError("needs exactly one start and one end marker line, start first (found %d start, %d end)"
                         % (len(starts), len(ends)))
    offset = lambda index: sum(len(line) + 1 for line in lines[:index])
    return offset(starts[0] + 1), offset(ends[0])


def sub_skills(skills_dir):
    """(ours, skipped): westack-* folders with metadata.stack westack, and the other westack-* folders."""
    ours, skipped = [], []
    for folder in sorted(pathlib.Path(skills_dir).iterdir()) if pathlib.Path(skills_dir).is_dir() else []:
        if not folder.is_dir() or folder.name == meta.STACK or not meta.NAME.fullmatch(folder.name):
            continue
        skill = folder / "SKILL.md"
        if not skill.is_file():
            continue
        _, nested, _ = meta.skill_metadata(skill.read_bytes().decode("utf-8", errors="replace"))
        (ours if nested.get("stack") == meta.STACK else skipped).append(folder)
    return ours, skipped


def write_replacing(path, data):
    """Write through an exclusive-create temporary file in the same folder, then swap it in."""
    temporary = path.with_name("." + path.name + ".westack-tmp-" + str(os.getpid()))
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def run(mode, skills_dir):
    source = SOURCE.read_bytes()
    report = {"format": FORMAT, "mode": mode, "source": str(SOURCE),
              "source_sha256": hashlib.sha256(source).hexdigest(), "source_lines": len(source.splitlines()),
              "skills_dir": str(skills_dir), "checked": 0, "skills": {}, "skipped": [], "errors": []}
    if report["source_lines"] > MAX_LINES:
        report["errors"].append("the source has %d lines; the block allows at most %d" % (report["source_lines"], MAX_LINES))
    if not source.endswith(b"\n"):
        report["errors"].append("the source must end with a newline")
    source_ok = not report["errors"]
    ours, skipped = sub_skills(skills_dir)
    report["skipped"] = [f.name for f in skipped]
    for folder in ours:
        path = folder / "SKILL.md"
        report["checked"] += 1
        data = path.read_bytes()
        try:
            start, end = locate(data)
        except ValueError as exc:
            report["skills"][folder.name] = "error: markers: " + str(exc)
            report["errors"].append(folder.name + ": markers: " + str(exc))
            continue
        if data[start:end] == source:
            report["skills"][folder.name] = "match" if mode == "check" else "unchanged"
            continue
        if mode == "check" or not source_ok:  # never spread an invalid source
            report["skills"][folder.name] = "differs"
            report["errors"].append(folder.name + ": the block differs from the source")
            continue
        write_replacing(path, data[:start] + source + data[end:])
        again = path.read_bytes()
        verified = again[slice(*locate(again))] == source
        report["skills"][folder.name] = "injected" if verified else "differs"
        if not verified:
            report["errors"].append(folder.name + ": the block still differs after writing")
    report["status"] = "failed" if report["errors"] else "passed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mode", choices=["check", "inject"])
    parser.add_argument("--skills-dir", default=str(CORE.parent), help="folder holding the westack-* sub-skills")
    args = parser.parse_args(argv)
    report = run(args.mode, pathlib.Path(args.skills_dir))
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
