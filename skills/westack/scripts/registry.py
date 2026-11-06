"""westack registry: list the skills installed in the documented host skill roots, as JSON.

Reads SKILL.md front matter only (at most 256 KiB each). Never executes, imports or writes anything
it finds. A listed skill is on disk; whether the host loaded it this session is a separate question
(the host's own skill listing answers that).

Roots (documented, not probed):
  claude  user ~/.claude/skills              project <project>/.claude/skills
  codex   user $CODEX_HOME/skills (default ~/.codex/skills) and ~/.agents/skills
          project <project>/.agents/skills
  cursor  user ~/.cursor/skills              project <project>/.cursor/skills and <project>/.agents/skills

A westack-* skill is ours only when its front matter carries metadata.stack: westack.

  python registry.py [--host claude|codex|cursor|all] [--project DIR] [--home DIR]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

FORMAT = "westack-registry-1"
HEAD_LIMIT = 256 * 1024
HOSTS = ("claude", "codex", "cursor")


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


def roots(hosts, home, project, codex_home=None):
    """[(path, scope, host)] for the selected hosts, in a stable order."""
    home, project = pathlib.Path(home), pathlib.Path(project)
    codex_home = pathlib.Path(codex_home) if codex_home else home / ".codex"
    table = {
        "claude": [(home / ".claude" / "skills", "user"), (project / ".claude" / "skills", "project")],
        "codex": [(codex_home / "skills", "user"), (home / ".agents" / "skills", "user"),
                  (project / ".agents" / "skills", "project")],
        "cursor": [(home / ".cursor" / "skills", "user"), (project / ".cursor" / "skills", "project"),
                   (project / ".agents" / "skills", "project")],
    }
    merged = {}
    for host in hosts:
        for path, scope in table[host]:
            entry = merged.setdefault(str(path), {"path": str(path), "scope": scope, "hosts": []})
            if host not in entry["hosts"]:
                entry["hosts"].append(host)
    return list(merged.values())


def skill_folders(root):
    """SKILL.md folders at <root>/<name> and one level deeper (<root>/<group>/<name>, e.g. .system)."""
    found = []
    try:
        children = sorted(p for p in pathlib.Path(root).iterdir() if p.is_dir())
    except OSError:
        return found
    for child in children:
        if (child / "SKILL.md").is_file():
            found.append(child)
            continue
        try:
            found.extend(sorted(g for g in child.iterdir() if g.is_dir() and (g / "SKILL.md").is_file()))
        except OSError:
            continue
    return found


def describe(folder, root):
    entry = {"name": None, "folder": folder.name, "path": str(folder), "root": root["path"], "scope": root["scope"],
             "hosts": list(root["hosts"]), "link": False, "version": None, "stack": None, "requires_core": None,
             "disable_model_invocation": None, "description_sha256": None, "description_chars": 0,
             "name_differs_from_folder": False, "ours": False, "errors": []}
    try:
        entry["link"] = folder.is_symlink() or bool(getattr(os.lstat(folder), "st_file_attributes", 0) & 0x400)
        with (folder / "SKILL.md").open("rb") as stream:
            head = stream.read(HEAD_LIMIT).decode("utf-8", errors="replace")
    except OSError as exc:
        entry["errors"].append("unreadable SKILL.md: " + str(exc))
        return entry
    keys, nested, errors = meta.skill_metadata(head)
    entry["errors"].extend(errors)
    name = keys.get("name") or None
    description = keys.get("description") or ""
    entry.update(name=name, version=nested.get("version") or keys.get("version") or None,
                 stack=nested.get("stack") or None, requires_core=nested.get("requires_core") or None,
                 description_chars=len(description),
                 description_sha256=hashlib.sha256(description.encode("utf-8")).hexdigest() if description else None,
                 name_differs_from_folder=bool(name) and name != folder.name)
    flag = keys.get("disable-model-invocation")
    entry["disable_model_invocation"] = None if flag is None else str(flag).strip().lower() == "true"
    label = name or folder.name
    entry["ours"] = bool(meta.NAME.fullmatch(label)) and entry["stack"] == meta.STACK
    return entry


def scan(hosts, home, project, codex_home=None):
    listed, by_path = [], {}
    selected = roots(hosts, home, project, codex_home)
    for root in selected:
        folders = skill_folders(root["path"])
        root["exists"] = pathlib.Path(root["path"]).is_dir()
        root["skill_count"] = len(folders)
        for folder in folders:
            key = os.path.normcase(str(folder.resolve()))
            if key in by_path:  # the same folder reached through another root or a link
                for host in root["hosts"]:
                    if host not in by_path[key]["hosts"]:
                        by_path[key]["hosts"].append(host)
                continue
            entry = describe(folder, root)
            by_path[key] = entry
            listed.append(entry)
    ours = sorted({s["name"] or s["folder"] for s in listed if s["ours"]})
    foreign = sorted({s["name"] or s["folder"] for s in listed
                      if meta.NAME.fullmatch(s["name"] or s["folder"]) and not s["ours"]})
    core = next((s for s in listed if s["ours"] and (s["name"] or s["folder"]) == meta.STACK), None)
    return {
        "format": FORMAT,
        "claim": "front matter read from documented roots; nothing executed; on disk is not the same as loaded "
                 "by the host this session",
        "hosts": list(hosts), "project": str(project), "roots": selected, "skills": listed,
        "ours": ours, "foreign_westack_names": foreign,
        "core": {"present": core is not None, "version": core["version"] if core else None,
                 "path": core["path"] if core else None},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", choices=HOSTS + ("all",), default="all")
    parser.add_argument("--project", default=".", help="project folder (default: the current directory)")
    parser.add_argument("--home", default=str(pathlib.Path.home()), help="home folder (default: your home)")
    args = parser.parse_args(argv)
    hosts = HOSTS if args.host == "all" else (args.host,)
    report = scan(hosts, pathlib.Path(args.home).absolute(), pathlib.Path(args.project).absolute(),
                  os.environ.get("CODEX_HOME") or None)
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
