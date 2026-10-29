"""Render the compact field table in contracts/README.md from contract.json.

`python tests/field_table.py` prints the table; the suite checks that the README copy matches."""
import json
import pathlib

CONTRACT = json.loads((pathlib.Path(__file__).resolve().parents[1] / "contracts/contract.json").read_text(encoding="utf-8"))
ORDER = ["task", "fingerprint", "requirement", "decision", "work_unit", "acceptance", "action", "evidence",
         "finding", "review", "lesson", "doc", "event", "capability"]


def fields(spec):
    required = spec.get("required", [])
    optional = [key for key in spec.get("properties", {}) if key not in required]
    return required, optional


def describe(name, spec):
    def label(key):
        prop = spec["properties"][key]
        if "enum" in prop:
            return key + " (" + "/".join(map(str, prop["enum"])) + ")"
        return key
    required, optional = fields(spec)
    return "| " + name + " | " + ", ".join(map(label, required)) + " | " + (", ".join(map(label, optional)) or "—") + " |"


def render():
    defs = CONTRACT["$defs"]
    rows = ["| Object | Required | Optional |", "| --- | --- | --- |"]
    for name in ORDER:
        rows.append(describe(name, defs[name]))
        if name == "task":
            for nested in ("authority", "host"):
                rows.append(describe("task." + nested, defs["task"]["properties"][nested]))
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    print(render(), end="")
