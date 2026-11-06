"""Read the canonical sibling manifest shared by builds and snapshot checks."""
import json
from pathlib import Path
import re


def sibling_names(skills_root):
    """Return built, discoverable children. Legacy single-skill editions have none."""
    manifest = Path(skills_root) / "westack/stack.json"
    if not manifest.exists():
        return ()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid westack stack manifest") from exc
    if not isinstance(data, dict) or data.get("format") != "westack-stack-1" or not isinstance(data.get("skills"), list):
        raise ValueError("Invalid westack stack manifest format")
    seen, names = set(), []
    for entry in data["skills"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid westack stack entry")
        name = entry.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in seen:
            raise ValueError("Invalid or duplicate westack stack name")
        seen.add(name)
        if entry.get("status") not in {"built", "planned"} or entry.get("invocation") not in {"model", "manual", "folded", "library"}:
            raise ValueError("Invalid westack stack status or invocation")
        if entry["status"] == "built" and entry["invocation"] in {"model", "manual"}:
            names.append("westack-" + name)
    return tuple(sorted(names))
