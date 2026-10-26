#!/usr/bin/env python3
"""Frankenmine local records: never import/execute donor code, fetch URLs or launch tools."""
from __future__ import annotations
import argparse
import ast
import hashlib
import html
import itertools
import json
import math
import os
from pathlib import Path
import platform
import re
import stat
import sys
from urllib.parse import unquote, urlsplit

PACKAGE = Path(__file__).resolve().parents[1]
SEAM_DIMENSIONS = ("exports_consumers", "closure", "initialization", "state_transactions",
                   "resources_lifetime", "concurrency_cancellation", "errors_retries",
                   "serialization", "permissions_effects", "tests", "licensing")
SEMANTIC_DIMENSIONS = ("numeric", "null_missing", "unicode_regex", "equality_order",
                      "time_units", "errors", "async_cancellation", "ownership",
                      "memory_threads", "persistence_transactions", "abi_layout",
                      "serialization", "initialization")
LIMIT = 8 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key: " + key)
        out[key] = value
    return out


def load_json(path):
    if path.stat().st_size > LIMIT:
        raise ValueError("JSON exceeds 8 MiB record limit")
    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number: " + text)
        return value
    return json.loads(read_bounded(path).decode("utf-8-sig"), object_pairs_hook=unique_object,
                      parse_float=finite_float,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + x)))


def is_link(path):
    """Include Windows junctions/reparse points on Python 3.10 and later."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) &
                                            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def read_bounded(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("not a regular file: " + str(path))
    with path.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("file exceeds 8 MiB limit: " + str(path))
    return data


def write_new(path, content):
    """Explicit caller-selected output; exclusive create prevents accidental replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def schema_errors(value, schema, root=None, path="$", depth=0):
    """Validate ONLY the JSON Schema features used in our bundled schema."""
    import re
    root = schema if root is None else root
    if depth > 80:
        return [path + ": nesting limit"]
    if "$ref" in schema:
        target = schema["$ref"]
        if not target.startswith("#/$defs/"):
            return [path + ": unsupported schema reference"]
        return schema_errors(value, root["$defs"][target.split("/")[-1]], root, path, depth + 1)
    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(path + ": const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(path + ": invalid enum")
    types = {"object": lambda x: isinstance(x, dict),
             "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str),
             "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
             "boolean": lambda x: isinstance(x, bool)}
    if "type" in schema and not types[schema["type"]](value):
        return errors + [path + ": expected " + schema["type"]]
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(path + ": missing " + key)
        props = schema.get("properties", {})
        for key, child in value.items():
            if key in props:
                errors.extend(schema_errors(child, props[key], root, path + "." + key, depth + 1))
            elif schema.get("additionalProperties") is False:
                errors.append(path + ": unknown field " + key)
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(path + ": too few items")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append(path + ": duplicate items")
        for i, child in enumerate(value):
            if "items" in schema:
                errors.extend(schema_errors(child, schema["items"], root, path + "[" + str(i) + "]", depth + 1))
    elif isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append(path + ": empty string")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(path + ": pattern mismatch")
    elif isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(path + ": below minimum")
    return errors


def local_bytes(root, relative):
    """Evidence paths are portable, confined and cannot traverse links."""
    if not relative or "\\" in relative or ":" in relative or relative.startswith("/"):
        raise ValueError("evidence path must be portable and relative: " + relative)
    parts = relative.split("/")
    if any(x in ("", ".", "..") for x in parts):
        raise ValueError("unsafe evidence path: " + relative)
    path = root.resolve()
    for part in parts:
        path = path / part
        if is_link(path):
            raise ValueError("evidence links are not followed: " + relative)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("evidence escapes run directory")
    if path.stat().st_size > LIMIT:
        raise ValueError("evidence exceeds 8 MiB limit: " + relative)
    return read_bounded(path)


def check(run, root):
    errors = schema_errors(run, load_json(PACKAGE / "schemas/run.schema.json"))
    if errors:
        return errors
    groups = ("donors", "evidence", "discoveries", "candidates", "tests", "receipts")
    all_ids = [x["id"] for g in groups for x in run[g]]
    if len(all_ids) != len(set(all_ids)):
        errors.append("duplicate stable IDs")
    by = {g: {x["id"]: x for x in run[g]} for g in groups}
    needs = {x["id"] for x in run["brief"]["requirements"]}
    if not needs or len(needs) != len(run["brief"]["requirements"]):
        errors.append("requirements must have unique nonempty IDs")

    def refs(values, group, label, nonempty=True):
        if nonempty and not values:
            errors.append(label + ": no " + group + " links")
        for ident in values:
            if ident not in by[group]:
                errors.append(label + ": unknown " + group + " " + ident)

    def required_test(ident, label):
        refs([ident], "tests", label)
        test = by["tests"].get(ident)
        if test and test["status"] in ("fail", "skipped", "blocked"):
            errors.append(label + ": required test is " + test["status"])
        return test

    def verify_file(path, expected, label):
        try:
            data = local_bytes(root, path)
            if digest(data) != expected:
                errors.append(label + ": hash mismatch")
            return data
        except (OSError, ValueError) as exc:
            errors.append(label + ": " + str(exc))
            return None

    for ev in run["evidence"]:
        refs([ev["donor"]], "donors", ev["id"])
        donor = by["donors"].get(ev["donor"])
        if donor and ev["revision"] != donor["revision"]:
            errors.append(ev["id"] + ": donor revision mismatch")
        data = verify_file(ev["snapshot"], ev["sha256"], ev["id"])
        if data is not None:
            try:
                count = len(data.decode("utf-8").splitlines())
                if not 1 <= ev["start_line"] <= ev["end_line"] <= count:
                    errors.append(ev["id"] + ": invalid source line range")
            except UnicodeError:
                errors.append(ev["id"] + ": source evidence must be UTF-8 text")
        # Claim strength is supplied by the author. Hash/line checks cannot prove
        # either wiring or an observation; the independent review must inspect it.

    for d in run["donors"]:
        if d["status"] == "queued":
            errors.append(d["id"] + ": donor still queued")
        if d["status"] == "reviewed":
            directions = {x["direction"] for x in run["discoveries"] if x["donor"] == d["id"]}
            if directions != {"target-led", "donor-led"}:
                errors.append(d["id"] + ": dual discovery missing")
            if not any(e["donor"] == d["id"] for e in run["evidence"]):
                errors.append(d["id"] + ": reviewed without evidence")
    for clue in run["discoveries"]:
        refs([clue["donor"]], "donors", clue["id"])
        refs(clue["evidence"], "evidence", clue["id"])
        if not any(by["evidence"].get(e, {}).get("donor") == clue["donor"] for e in clue["evidence"]):
            errors.append(clue["id"] + ": discovery lacks matching donor evidence")
        if clue["target_need"] not in needs and not clue["target_need"].startswith("hypothesis:"):
            errors.append(clue["id"] + ": unknown target need/hypothesis")

    selected = [c for c in run["candidates"] if c["phase"] in ("selected", "design-reviewed")]
    if run["unresolved"]:
        errors.append("unresolved items remain; resolve or scope out blockers before readiness")
    owner_keys = [x["key"] for x in run["ownership"]]
    if len(set(owner_keys)) != len(owner_keys):
        errors.append("ownership conflict: multiple entries for one state/policy/interface")
    for c in run["candidates"]:
        refs([c["donor"]], "donors", c["id"])
        refs(c["evidence"], "evidence", c["id"])
        refs(c["discovery"], "discoveries", c["id"])
        if c["need"] not in needs:
            errors.append(c["id"] + ": unestablished target requirement")
        if run["mode"] == "design" and c["implementation"] != "not-started":
            errors.append(c["id"] + ": design cannot claim implementation")
        if c["route"] == "defer" and c in selected:
            errors.append(c["id"] + ": deferred route cannot be selected")
        if c["implementation"] in ("tested", "demonstrated"):
            for ident in (c["acceptance"], c["negative_control"]):
                if by["tests"].get(ident, {}).get("status") != "pass":
                    errors.append(c["id"] + ": runtime promotion without passed acceptance/control")
            if c["implementation"] == "demonstrated":
                errors.append(c["id"] + ": demonstrated benefit needs independent evaluation beyond this helper")
        if c in selected or c["implementation"] in ("tested", "demonstrated"):
            acceptance = required_test(c["acceptance"], c["id"] + " acceptance")
            if acceptance and acceptance["purpose"] not in ("product", "adapter", "integration"):
                errors.append(c["id"] + ": acceptance must test product, adapter or integration behavior")
            control = required_test(c["negative_control"], c["id"] + " control")
            if control and control["purpose"] != "negative-control":
                errors.append(c["id"] + ": control is not a negative-control test")
            if c["acceptance"] == c["negative_control"]:
                errors.append(c["id"] + ": acceptance and control must differ")
        if c not in selected:
            continue
        if not c["closure"]:
            errors.append(c["id"] + ": selected closure must be recorded, including reasoned no-dependency cases")
        if not any(by["discoveries"].get(d, {}).get("donor") == c["donor"] for d in c["discovery"]):
            errors.append(c["id"] + ": selected unit lacks matching donor discovery")
        for label, text in list(c["seam"].items()) + list(c["protocol"].items()):
            if text.strip().lower() in ("unknown", "todo", "pending", "n/a"):
                errors.append(c["id"] + ": unexplained seam/protocol field " + label)
        if not any(by["evidence"].get(e, {}).get("donor") == c["donor"] for e in c["evidence"]):
            errors.append(c["id"] + ": selected unit lacks matching donor provenance")
        donor = by["donors"].get(c["donor"])
        if donor and donor["status"] != "reviewed":
            errors.append(c["id"] + ": selected donor not reviewed")
        if donor and c["source_language"].strip().casefold() not in {x.strip().casefold() for x in donor["languages"]}:
            errors.append(c["id"] + ": source language not declared by donor")
        if c["target_language"].strip().casefold() != run["brief"]["target_language"].strip().casefold():
            errors.append(c["id"] + ": target language disagrees with product brief")
        if c["rights"]["status"] != "reviewed" or c["rights"]["route"] == "unresolved":
            errors.append(c["id"] + ": rights unresolved or restricted")
        refs(c["rights"]["evidence"], "evidence", c["id"] + " rights")
        if not any(by["evidence"].get(e, {}).get("donor") == c["donor"] for e in c["rights"]["evidence"]):
            errors.append(c["id"] + ": rights lack matching donor evidence")
        if not any(x["owner"] == c["owner"] for x in run["ownership"]):
            errors.append(c["id"] + ": no authoritative owner entry")
        if c["source_language"].strip().casefold() != c["target_language"].strip().casefold():
            dimensions = [x["dimension"] for x in c["deltas"]]
            if set(dimensions) != set(SEMANTIC_DIMENSIONS) or len(dimensions) != len(set(dimensions)):
                errors.append(c["id"] + ": incomplete or duplicate semantic delta dimensions")
            for delta in c["deltas"]:
                if delta["status"] == "unknown":
                    errors.append(c["id"] + ": semantic mismatch unresolved: " + delta["dimension"])
                if delta["status"] != "not-applicable":
                    required_test(delta["test"], c["id"] + " delta")

    selected_ids = {c["id"] for c in selected}
    if run["decision"]["choice"] == "fusion" and not needs <= {c["need"] for c in selected}:
        errors.append("selected fusion does not account for every requirement")
    if any(x.strip().lower() in ("unknown", "todo", "pending", "n/a") for x in run["global_review"].values()):
        errors.append("global interaction review incomplete")
    covered = set()
    for inter in run["interactions"]:
        refs(inter["components"], "candidates", "interaction")
        if len(inter["components"]) < 2 or len(set(inter["components"])) != len(inter["components"]):
            errors.append("interaction requires distinct components")
        pair = frozenset(inter["components"])
        if len(pair) == 2:
            if pair in covered:
                errors.append("duplicate interaction pair")
            covered.add(pair)
        if pair <= selected_ids:
            if inter["status"] not in ("compatible", "resolved"):
                errors.append("unresolved multi-donor interaction")
            refs(inter["evidence"], "evidence", "interaction")
            required_test(inter["test"], "interaction")
    for pair in itertools.combinations(sorted(selected_ids), 2):
        if frozenset(pair) not in covered:
            errors.append("missing interaction review: " + " / ".join(pair))
    if {x["kind"] for x in run["alternatives"]} != {"best-existing", "minimal-fresh", "fusion"}:
        errors.append("compare best existing, minimal fresh and fusion")
    for alt in run["alternatives"]:
        refs(alt["evidence"], "evidence", "alternative " + alt["kind"])
    if run["decision"]["choice"] == "fusion" and len({c["donor"] for c in selected}) < 2:
        errors.append("fusion choice needs at least two selected donors")
    if run["decision"]["choice"] in ("best-existing", "minimal-fresh") and selected:
        errors.append("non-fusion choice must defer/reject fusion candidates")
    if run["decision"]["choice"] == "defer":
        errors.append("design decision deferred")
    if run["review"]["disposition"] != "accepted" or not run["review"]["independent"]:
        errors.append("independent design review not accepted")

    for test in run["tests"]:
        verify_file(test["oracle"], test["oracle_sha256"], test["id"] + " oracle")
        if not test["frozen"]:
            errors.append(test["id"] + ": oracle not frozen")
        receipts = [r for r in run["receipts"] if r["test"] == test["id"]]
        if test["status"] in ("pass", "fail") and len(receipts) != 1:
            errors.append(test["id"] + ": executed status needs exactly one receipt")
        if test["status"] in ("not-run", "skipped", "blocked") and receipts:
            errors.append(test["id"] + ": unexecuted status has receipt")
    for receipt in run["receipts"]:
        refs([receipt["test"]], "tests", receipt["id"])
        verify_file(receipt["raw_output"], receipt["raw_sha256"], receipt["id"] + " raw")
        if receipt["cases"] != receipt["passed"] + receipt["failed"] + receipt["skipped"]:
            errors.append(receipt["id"] + ": inconsistent counts")
        test = by["tests"].get(receipt["test"], {})
        if test.get("status") == "pass":
            if receipt["cases"] <= 0 or receipt["passed"] <= 0 or receipt["failed"] or receipt["skipped"] or receipt["exit_code"]:
                errors.append(receipt["id"] + ": empty, failing, skipped or nonzero run cannot pass")
            if test.get("purpose") == "negative-control" and not receipt["control_detected"]:
                errors.append(receipt["id"] + ": negative control not detected")
        if test.get("status") == "fail" and not (receipt["failed"] > 0 or receipt["exit_code"] != 0):
            errors.append(receipt["id"] + ": failure status lacks failing observation")
    return errors


def skeleton():
    return dict(schema_version="1.0", id="new-product", mode="design", synthetic=False,
                brief=dict(outcome="TODO: new product outcome", users="TODO", non_goals=[],
                           requirements=[], constraints=[], target_language="TODO",
                           write_scope="TODO: isolated output root", authorization="Design only; no donor execution"),
                donors=[], evidence=[], discoveries=[], candidates=[], ownership=[], interactions=[],
                global_review=dict(cycles="Unknown", shared_versions="Unknown", resource_budget="Unknown", higher_order="Unknown"),
                alternatives=[], decision=dict(choice="defer", rationale="Await source analysis and alternatives"),
                tests=[], receipts=[], review=dict(independent=False, reviewer="not-run", disposition="not-run",
                                                  findings=[], adjudication="Pending"),
                unresolved=["Populate brief, register all donors before triage, then inspect sources."])


def decision_donors(path):
    """Register manifest declarations only; never retrieve or qualify their sources."""
    manifest = load_json(path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("decisions"), list) or not manifest["decisions"]:
        raise ValueError("decisions input requires an object with a nonempty decisions array")

    def text(value, label):
        if not isinstance(value, str) or not value or value != value.strip() or any(
                ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError(label + " must be a nonempty, trimmed text string without control/surrogate characters")
        return value

    donors, seen = [], set()
    for index, decision in enumerate(manifest["decisions"]):
        label = "decisions[" + str(index) + "]"
        if not isinstance(decision, dict):
            raise ValueError(label + " must be an object")
        ident = text(decision.get("id"), label + ".id")
        if ident in seen:
            raise ValueError("duplicate decision ID: " + ident)
        seen.add(ident)
        url = text(decision.get("source_url"), label + ".source_url")
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or any(char.isspace() for char in url) or "\\" in url
                or re.search(r"%(?![0-9a-fA-F]{2})", url)):
            raise ValueError(label + ".source_url must be an absolute HTTP(S) URL without credentials or whitespace")
        port = parsed.port  # Validate malformed/out-of-range ports without opening a connection.
        catalogue = text(decision["catalogue_id"], label + ".catalogue_id") if "catalogue_id" in decision else None
        # Only a literal full commit in an unambiguous GitHub blob/tree path is a pin.
        source_path = parsed.path[:-1] if parsed.path.endswith("/") else parsed.path
        match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/(blob|tree)/([0-9a-fA-F]{40})(?:/(.+))?", source_path)
        suffix = match.group(5) if match else None
        safe_path = match and all(part not in (".", "..") for part in match.group(1, 2)) and (match.group(3) == "tree" or suffix) and all(
            unquote(part) not in ("", ".", "..") and "/" not in unquote(part) and "\\" not in unquote(part)
            for part in (suffix.split("/") if suffix else []))
        pinned = parsed.hostname.lower() == "github.com" and port in (None, 443 if parsed.scheme == "https" else 80) and safe_path
        revision = match.group(4).lower() if pinned else "unpinned"
        blind_spots = ["Registration only: source not inspected; languages, closure, rights and runtime behavior unassessed."]
        blind_spots.append("URL declares a full commit; source existence and revision were not verified." if pinned else
                           "Unpinned: URL does not declare an unambiguous GitHub blob/tree full commit.")
        donors.append(dict(id=ident, url=url, revision=revision, languages=[], status="queued",
            reason="Registered from decisions input before triage; decision metadata is not source evidence.",
            scope="Registration only" + ("; catalogue_id=" + catalogue if catalogue else "; catalogue_id not supplied"),
            blind_spots=blind_spots))
    return donors


def inspect_python(root, revision):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("donor root is not a directory")
    records, edges, omissions = [], [], []
    skipped = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for directory, folders, files in os.walk(root, followlinks=False,
            onerror=lambda exc: omissions.append(str(exc.filename) + ": unreadable directory: " + str(exc))):
        keep = []
        for folder in sorted(folders):
            entry = Path(directory) / folder
            if folder in skipped or is_link(entry):
                omissions.append(entry.relative_to(root).as_posix() + ": skipped directory/link")
            else:
                keep.append(folder)
        folders[:] = keep
        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue
            path = Path(directory) / filename
            rel = path.relative_to(root).as_posix()
            if is_link(path):
                omissions.append(rel + ": skipped link")
                continue
            try:
                if path.stat().st_size > LIMIT:
                    raise ValueError("source exceeds 8 MiB")
                raw = read_bounded(path)
                tree = ast.parse(raw, filename=rel)
            except (OSError, SyntaxError, ValueError, UnicodeError) as exc:
                omissions.append(rel + ": " + type(exc).__name__ + ": " + str(exc))
                continue
            records.append(dict(id=rel, sha256=digest(raw), revision=revision,
                                lines=len(raw.splitlines()), top_level_effects=[
                                    getattr(n, "lineno", 0) for n in tree.body
                                    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                                          ast.Import, ast.ImportFrom))]))
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for name in n.names:
                        edges.append(dict(source=rel, target=name.name, line=n.lineno, relation="import",
                                          evidence="static", resolution="unresolved-module"))
                elif isinstance(n, ast.ImportFrom):
                    edges.append(dict(source=rel, target="." * n.level + (n.module or ""), line=n.lineno,
                                      relation="import", evidence="static", resolution="unresolved-module"))
                elif isinstance(n, ast.Call):
                    edges.append(dict(source=rel, target=ast.unparse(n.func), line=n.lineno,
                                      relation="call", evidence="static", resolution="unresolved-symbol"))
    return dict(schema_version="1.0", adapter="python-ast", tool_version=platform.python_version(),
                revision=revision, root=str(root), nodes=records, edges=edges, omissions=omissions,
                limits=["Syntax-level candidates only; no donor imports/execution.",
                        "Calls/imports unresolved; external deps, dynamic dispatch/imports, reflection, generated code,",
                        "framework injection, initialization in decorators/classes and runtime state need manual inspection.",
                        "No rights clearance, complete closure or seam qualification is implied."])


def report(run, errors):
    def plain(value):
        # Donor-controlled fields must remain inert text in a rendered dossier.
        value = html.escape(str(value), quote=False).replace("\r", " ").replace("\n", " ")
        return re.sub(r"([\\`*_{}\[\]()#+.!|>~\-])", r"\\\1", value)

    result = "design-blocked" if errors else "design-ready (record consistency only)"
    lines = ["# Frankenmine dossier: " + plain(run.get("id", "invalid")), "", "Decision state: " + result,
             "", "This is a structural report, not semantic proof, authorization, or live-agent qualification.",
             "Synthetic data: " + str(run.get("synthetic", "unknown")), "",
             "## Findings", ""]
    lines.extend("- " + plain(item) for item in errors)
    if not errors:
        lines.append("- No structural/readiness errors detected.")
    lines.extend(["", "## Donor accounting", ""])
    for d in run.get("donors", []):
        lines.append("- " + plain(d["id"]) + " @ " + plain(d["revision"]) + ": " + plain(d["status"]) + " — " + plain(d["reason"]))
    lines.extend(["", "## Product and architecture", "", plain(run["brief"]["outcome"]), "",
                  "Choice: " + plain(run["decision"]["choice"]) + ". " + plain(run["decision"]["rationale"]), ""])
    for c in run.get("candidates", []):
        lines.append("- " + plain(c["id"]) + ": " + plain(c["route"]) + "; design=" + plain(c["phase"]) +
                     "; implementation=" + plain(c["implementation"]) + "; owner=" + plain(c["owner"]))
    lines.extend(["", "## Alternatives", ""])
    for a in run["alternatives"]:
        lines.append("- " + plain(a["kind"]) + " — " + plain(a["name"]) + ": " + plain(a["tradeoffs"]))
    lines.extend(["", "## Execution statuses", ""])
    for t in run.get("tests", []):
        lines.append("- " + plain(t["id"]) + " (" + plain(t["purpose"]) + "): " + plain(t["status"]))
    record = encode(run).rstrip()
    fence = "`" * max(3, 1 + max((len(x) for x in re.findall(r"`+", record)), default=0))
    lines.extend(["", "## Full portable record", "", fence + "json", record, fence, ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="create an incomplete run; refuses replacement")
    p.add_argument("output", type=Path)
    p.add_argument("--decisions", type=Path, help="register queued donors from a local decisions manifest; no retrieval")
    p = sub.add_parser("inspect-python", help="static syntax inventory; no donor execution")
    p.add_argument("root", type=Path)
    p.add_argument("--revision", required=True)
    p.add_argument("--output", type=Path, required=True)
    for name in ("check", "report"):
        p = sub.add_parser(name)
        p.add_argument("run", type=Path)
        if name == "report":
            p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            run = skeleton()
            result = {"status": "created-incomplete", "path": str(args.output)}
            if args.decisions is not None:
                run["donors"] = decision_donors(args.decisions)
                run["unresolved"] = ["Populate brief, triage queued decisions, then inspect in-scope sources."]
                result["donors_registered"] = len(run["donors"])
            write_new(args.output, encode(run))
            print(encode(result), end="")
            return 0
        if args.command == "inspect-python":
            result = inspect_python(args.root, args.revision)
            write_new(args.output, encode(result))
            print(encode({"status": "static-inventory", "nodes": len(result["nodes"]),
                          "omissions": len(result["omissions"]), "qualified": False}), end="")
            return 0
        run = load_json(args.run)
        errors = check(run, args.run.parent)
        if args.command == "report":
            shape_errors = schema_errors(run, load_json(PACKAGE / "schemas/run.schema.json"))
            if shape_errors:
                print(encode({"status": "invalid-record", "errors": shape_errors}), end="")
                return 2
            write_new(args.output, report(run, errors))
        print(encode({"status": "design-blocked" if errors else "design-ready",
                      "scope": "record consistency; no semantic or live-agent qualification",
                      "errors": errors}), end="")
        return 2 if errors else 0
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        print(encode({"status": "error", "reason": str(exc)}), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
