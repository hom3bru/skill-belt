"""westack core check: is this core's version inside the range a sub-skill requires?

  python core_check.py --skill <sub-skill folder>     (reads its metadata.requires_core)
  python core_check.py --requires ">=1.0.0-alpha.0 <2"

Prints JSON. Exit 0 compatible, 1 incompatible, 2 when the range or a version cannot be read.
Ranges are space-separated comparators (>=, >, <=, <, =) with plain semantic-version precedence;
"<2" also excludes 2.0.0 prereleases. Reads two front-matter blocks; runs nothing.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys


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


def front(folder):
    path = pathlib.Path(folder) / "SKILL.md"
    with path.open("rb") as stream:
        return meta.skill_metadata(stream.read(256 * 1024).decode("utf-8", errors="replace"))


def check(requires, core=CORE):
    result = {"core": str(core), "core_version": None, "requires": requires, "status": "invalid", "errors": []}
    try:
        keys, nested, _ = front(core)
    except OSError as exc:
        result["errors"].append("cannot read the core's SKILL.md: " + str(exc))
        return result
    result["core_version"] = nested.get("version")
    version = meta.parse_version(nested.get("version", ""))
    comparators = meta.parse_range(requires or "")
    if keys.get("name") != meta.STACK or nested.get("stack") != meta.STACK:
        result["errors"].append("the core folder is not a westack core (name and metadata.stack must be westack)")
    if version is None:
        result["errors"].append("the core has no readable metadata.version")
    if comparators is None:
        result["errors"].append("unreadable range: " + str(requires))
    if not result["errors"]:
        result["status"] = "compatible" if meta.satisfies(version, comparators) else "incompatible"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--skill", help="sub-skill folder whose metadata.requires_core to check")
    group.add_argument("--requires", help="a version range such as \">=1.0.0-alpha.0 <2\"")
    parser.add_argument("--core", default=str(CORE), help="core folder (default: the one holding this script)")
    args = parser.parse_args(argv)
    requires = args.requires
    if args.skill:
        try:
            requires = front(args.skill)[1].get("requires_core")
        except OSError as exc:
            requires = None
            sys.stderr.write("core_check.py: cannot read " + args.skill + ": " + str(exc) + "\n")
    result = check(requires, pathlib.Path(args.core))
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return {"compatible": 0, "incompatible": 1}.get(result["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
