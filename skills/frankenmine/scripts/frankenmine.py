#!/usr/bin/env python3
"""Frankenmine local records: never import/execute donor code, fetch URLs or launch tools."""
from __future__ import annotations
import argparse
import ast
import collections
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
SCHEMAS = {"1.0": "schemas/run-1.0.schema.json", "1.1": "schemas/run.schema.json"}
CURRENT_SCHEMA = "1.1"
SEAM_DIMENSIONS = ("exports_consumers", "closure", "initialization", "state_transactions",
                   "resources_lifetime", "concurrency_cancellation", "errors_retries",
                   "serialization", "permissions_effects", "tests", "licensing")
SEMANTIC_DIMENSIONS = ("numeric", "null_missing", "unicode_regex", "equality_order",
                      "time_units", "errors", "async_cancellation", "ownership",
                      "memory_threads", "persistence_transactions", "abi_layout",
                      "serialization", "initialization")
# Routes that move donor behaviour into the product; pattern-only carries a lesson, defer nothing.
REUSE_ROUTES = ("dependency", "narrow-port", "ffi", "process", "rpc", "wasm", "reimplementation")
PROTOCOL_ROUTES = ("process", "rpc")
# Routes that put donor code, or an artifact built from it, into the product. A reimplementation joins
# them when it is rewritten from the donor's code (basis "code"); rebuilt from the idea alone, it does not.
CODE_ROUTES = ("dependency", "narrow-port", "ffi", "process", "rpc", "wasm")
PERMISSION_CATEGORIES = ("source-available", "proprietary")  # code reuse only with explicit permission
INDEPENDENCE_LEVELS = ("self", "fresh-context-same-model", "different-model", "human")
GROUPS = ("donors", "evidence", "supporting_evidence", "discoveries", "candidates", "tests", "receipts",
          "discovery_searches")
SCAFFOLD_MARK = "TODO(scaffold)"
# Small extension map for language identity; ambiguous headers map to every plausible language.
LANGUAGE_BY_EXTENSION = {
    ".py": ("python",), ".pyi": ("python",), ".js": ("javascript",), ".mjs": ("javascript",),
    ".cjs": ("javascript",), ".jsx": ("javascript",), ".ts": ("typescript",), ".tsx": ("typescript",),
    ".mts": ("typescript",), ".cts": ("typescript",), ".rs": ("rust",), ".go": ("go",), ".java": ("java",),
    ".kt": ("kotlin",), ".kts": ("kotlin",), ".scala": ("scala",), ".c": ("c",), ".h": ("c", "c++", "objective-c"),
    ".cc": ("c++",), ".cpp": ("c++",), ".cxx": ("c++",), ".hpp": ("c++",), ".hh": ("c++",), ".cs": ("c#",),
    ".rb": ("ruby",), ".php": ("php",), ".swift": ("swift",), ".m": ("objective-c",), ".lua": ("lua",),
    ".dart": ("dart",), ".ex": ("elixir",), ".exs": ("elixir",), ".erl": ("erlang",), ".hs": ("haskell",),
    ".ml": ("ocaml",), ".clj": ("clojure",), ".zig": ("zig",), ".sh": ("shell",), ".bash": ("shell",),
    ".ps1": ("powershell",), ".sql": ("sql",)}
LANGUAGE_ALIASES = {"js": "javascript", "node": "javascript", "nodejs": "javascript", "node.js": "javascript",
                    "ts": "typescript", "py": "python", "python3": "python", "golang": "go", "cpp": "c++",
                    "cxx": "c++", "csharp": "c#", "rs": "rust", "bash": "shell", "sh": "shell", "objc": "objective-c"}
DISCOVERY_CONTENT = ("problem", "mechanism", "invariant", "assumptions", "target_need", "falsifier", "rationale")
UNRESOLVED_MESSAGE = "unresolved items remain; resolve or scope out blockers before readiness"
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


def parse_json_bytes(data):
    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number: " + text)
        return value
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_float=finite_float,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + x)))


def load_json(path):
    if path.stat().st_size > LIMIT:
        raise ValueError("JSON exceeds 8 MiB record limit")
    return parse_json_bytes(read_bounded(path))


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


def inside_package(path):
    target = os.path.normcase(str(Path(path).resolve()))
    package = os.path.normcase(str(PACKAGE))
    return target == package or target.startswith(package.rstrip(os.sep) + os.sep)


def refuse_package(path):
    if inside_package(path):
        raise ValueError("refusing to write inside the Frankenmine package root: " + str(Path(path).resolve()) +
                         "; choose an output path outside the skill folder")


def write_new(path, content):
    """Explicit caller-selected output; exclusive create prevents accidental replacement.

    Outputs never land inside this package: an installed skill folder is not a run directory."""
    path = Path(path)
    refuse_package(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def write_new_bytes(path, data):
    """Binary twin of write_new: exclusive create, never inside the package."""
    path = Path(path)
    refuse_package(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def schema_errors(value, schema, root=None, path="$", depth=0):
    """Validate ONLY the JSON Schema features used in our bundled schemas."""
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
             "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
             "boolean": lambda x: isinstance(x, bool)}
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(types[name](value) for name in allowed):
            return errors + [path + ": expected " + "|".join(allowed)]
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


def record_schema_errors(run):
    """Validate against the schema the record declares; 1.0 records keep their frozen contract."""
    version = run.get("schema_version") if isinstance(run, dict) else CURRENT_SCHEMA
    if version not in SCHEMAS:
        return ["$.schema_version: unsupported schema_version " + json.dumps(version, ensure_ascii=False) +
                "; supported: " + ", ".join(SCHEMAS)]
    return schema_errors(run, load_json(PACKAGE / SCHEMAS[version]))


# --- readiness text rules ---------------------------------------------------------------
_MARKER = re.compile(r"^\s*(?:(?:todo|to\s+do|tbd|tba|tbc|fixme|xxx|wip|placeholder|fill[\s-]+in|not\s+yet\s+known|"
                     r"to be (?:determined|decided|confirmed))(?![\w-])|\?)", re.I)
_VAGUE_LEAD = ("unknown", "unclear", "unsure", "unspecified", "undecided", "pending", "later")
_EMPTY_WORDS = ("none", "nil", "null", "na")
_NOT_APPLICABLE = re.compile(r"^\s*(?:n\s*/\s*a|n\.\s*a\.?|not[\s_-]*applicable|na\s*:)(?![a-z])", re.I)
_NA_FORM = re.compile(r"^n/a: (?P<reason>\S.*)$", re.I | re.S)
_NONE_FORM = re.compile(r"^none\s*:\s*(?P<reason>\S.*)$", re.I | re.S)


def text_issue(value):
    """Why free text is not yet content, or None. 'n/a: <reason>' is the one not-applicable form,
    and 'none: <reason>' is the honest answer where nothing exists (no effects, no dependencies).

    Unfinished markers (TODO, To do, TBD, WIP, Not yet known, ?, FIXME...) are caught as prefixes.
    A short value (three words or fewer) led by unknown/pending/unclear, or such a word followed by
    ':', is a placeholder; an explanatory sentence that starts with one of those words is content."""
    text = value.strip()
    if _NOT_APPLICABLE.match(text):
        match = _NA_FORM.match(text)
        reason = match.group("reason").strip() if match else ""
        if len(reason) < 8 or text_issue(reason):
            return "not-applicable text must read 'n/a: <reason>' with a real reason"
        return None
    none = _NONE_FORM.match(text)
    if none:
        reason = none.group("reason").strip()
        if len(reason) < 8 or text_issue(reason):
            return "'none: <reason>' needs a real reason"
        return None
    if _MARKER.match(text):
        return "placeholder"
    words = re.findall(r"[^\W_]+", text.casefold())
    if not words or text.casefold().strip(" .!:;,-") in _EMPTY_WORDS:
        return "placeholder (write 'none: <reason>' or 'n/a: <reason>' where nothing applies)"
    if words[0] in _VAGUE_LEAD and (len(words) <= 3 or re.match(r"^\s*[^\W_]+\s*[:;]", text)):
        return "placeholder"
    return None


# Reference, enum, digest and deliberately-uncertain fields are not free-text content.
_SKIP_KEYS = frozenset((
    "id", "donor", "evidence", "discovery", "test", "acceptance", "negative_control", "components",
    "snapshot", "oracle", "raw_output", "url", "revision", "sha256", "oracle_sha256", "raw_sha256",
    "requirement", "by", "path", "need", "target_need", "limitations", "blind_spots", "retrieved",
    "status", "kind", "direction", "stage", "disposition", "route", "phase", "implementation", "purpose",
    "mode", "choice", "dimension", "question", "category", "independence", "basis", "origin", "candidates",
    "date", "pin", "artifacts", "report"))


def placeholder_errors(value, where, errors, skip=_SKIP_KEYS):
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in skip:
                placeholder_errors(child, where + "." + key, errors, skip)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            placeholder_errors(child, where + "[" + str(index) + "]", errors, skip)
    elif isinstance(value, str):
        issue = text_issue(value)
        if issue:
            errors.append("placeholder text in " + where + ": " + issue)


def norm_key(text):
    """Ownership/touch keys compare without case, whitespace or separator differences."""
    return re.sub(r"[\s._:/\\-]+", ":", text.strip().casefold()).strip(":")


def norm_name(text):
    return " ".join(str(text).split()).casefold()


_COMMIT = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_TAG_DIGEST = re.compile(r"^(?P<tag>[A-Za-z0-9][A-Za-z0-9._+/-]*)@sha256:[0-9a-f]{64}$")
_FLOATING = frozenset(("main", "master", "head", "latest", "trunk", "develop", "dev", "default", "stable",
                       "unpinned", "current", "tip", "release", "nightly", "edge"))


def is_real_pin(revision):
    """A full commit hash, or an immutable tag with a content digest; never a branch-like name."""
    text = revision.strip()
    if _COMMIT.match(text):
        return True
    match = _TAG_DIGEST.match(text)
    return bool(match) and match.group("tag").casefold() not in _FLOATING


_EXACT_VERSION = re.compile(r"^v?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.-]*)?$")


def is_exact_pin(text):
    """A retained dependency's pin: a real revision pin, or one exact version (no ranges or tags)."""
    return is_real_pin(text) or bool(_EXACT_VERSION.match(text.strip()))


def language_key(name):
    """Compare language labels without case, version suffixes or common aliases."""
    text = re.sub(r"\s+v?\d[\d.]*$", "", str(name).strip().casefold())
    return LANGUAGE_ALIASES.get(text, text)


def scaffold_marks(value, where="$"):
    """JSON paths of every string the scaffold helper left unfilled."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from scaffold_marks(child, where + "." + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scaffold_marks(child, where + "[" + str(index) + "]")
    elif isinstance(value, str) and value.lstrip().startswith(SCAFFOLD_MARK):
        yield where


def is_code_route(candidate):
    """True when the product keeps donor code: a code route, or a reimplementation rewritten from the code."""
    return candidate["route"] in CODE_ROUTES or (candidate["route"] == "reimplementation" and
                                                  candidate.get("basis") == "code")


def needs_of(candidate):
    need = candidate["need"]
    return [need] if isinstance(need, str) else list(need)


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
    errors = record_schema_errors(run)
    if errors:
        return errors
    # Rules that need a 1.1 field apply to 1.1 records; a 1.0 record keeps its frozen messages.
    v11 = run["schema_version"] == "1.1"
    group = {g: run.get(g, []) for g in GROUPS}
    all_ids = [x["id"] for g in GROUPS for x in group[g]]
    if len(all_ids) != len(set(all_ids)):
        errors.append("duplicate stable IDs")
    by = {g: {x["id"]: x for x in group[g]} for g in GROUPS}
    brief = run["brief"]
    needs = {x["id"] for x in brief["requirements"]}
    if len(needs) != len(brief["requirements"]) or (not needs and brief.get("question") != "exploratory"):
        errors.append("requirements must have unique nonempty IDs")

    def refs(values, kind, label, nonempty=True, groups=None):
        if nonempty and not values:
            errors.append(label + ": no " + kind + " links")
        for ident in values:
            if not any(ident in by[g] for g in (groups or (kind,))):
                errors.append(label + ": unknown " + kind + " " + ident)

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

    placeholder_errors(brief, "brief", errors)
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
        placeholder_errors(ev, "evidence[" + ev["id"] + "]", errors)
        # Claim strength is supplied by the author. Hash/line checks cannot prove
        # either wiring or an observation; the independent review must inspect it.

    for item in group["supporting_evidence"]:
        # Weaker than source snapshots: documentation, observation, images and derived graphs.
        sid, kind, data, donor = item["id"], item["kind"], None, None
        if "donor" in item:
            refs([item["donor"]], "donors", sid)
            donor = by["donors"].get(item["donor"])
        if "snapshot" in item:
            if "sha256" not in item:
                errors.append(sid + ": snapshot needs sha256")
            else:
                data = verify_file(item["snapshot"], item["sha256"], sid)
        elif kind in ("screenshot", "static-graph", "license-scan"):
            errors.append(sid + ": " + kind + " evidence needs a local snapshot and sha256")
        if kind == "license-scan":
            # Scanner output is accepted as data; the helper never installs or runs a scanner.
            for field in ("tool", "tool_version"):
                if not item.get(field) or text_issue(item[field]):
                    errors.append(sid + ": license-scan evidence needs " + field + " (the scanner and its version)")
            if donor is not None and "revision" in item and item["revision"] != donor["revision"]:
                errors.append(sid + ": license-scan revision must equal the donor revision")
        if "url" in item:
            parsed = urlsplit(item["url"])
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                errors.append(sid + ": url must be absolute http(s)")
        if kind in ("documentation", "product-observation") and not ("url" in item and "retrieved" in item):
            errors.append(sid + ": " + kind + " evidence needs url and retrieved date")
        if kind == "screenshot" and "retrieved" not in item:
            errors.append(sid + ": screenshot evidence needs a retrieved date")
        if kind == "static-graph":
            if donor is None:
                errors.append(sid + ": static-graph evidence must name its donor")
            elif item.get("revision") != donor["revision"]:
                errors.append(sid + ": static-graph revision field must equal the donor revision")
            if data is not None:
                try:
                    graph = parse_json_bytes(data)
                except (ValueError, UnicodeError):
                    graph = None
                    errors.append(sid + ": static graph is not valid JSON")
                if graph is not None and (not isinstance(graph, dict) or graph.get("revision") != item.get("revision")):
                    errors.append(sid + ": graph revision does not match the recorded donor revision")
        placeholder_errors(item, "supporting_evidence[" + sid + "]", errors)

    for d in run["donors"]:
        if d["status"] == "queued":
            errors.append(d["id"] + ": donor still queued")
        placeholder_errors(d, "donors[" + d["id"] + "]", errors)
        if d["status"] == "reviewed":
            mine = [x for x in run["discoveries"] if x["donor"] == d["id"]]
            if {x["direction"] for x in mine} != {"target-led", "donor-led"}:
                errors.append(d["id"] + ": dual discovery missing")
            if not any(e["donor"] == d["id"] for e in run["evidence"]):
                errors.append(d["id"] + ": reviewed without evidence")
            for donor_led in (x for x in mine if x["direction"] == "donor-led"):
                for target_led in (x for x in mine if x["direction"] == "target-led"):
                    if all(norm_name(donor_led[k]) == norm_name(target_led[k]) for k in DISCOVERY_CONTENT):
                        errors.append(d["id"] + ": donor-led discovery " + donor_led["id"] + " duplicates target-led " +
                                      target_led["id"] + "; record a genuinely donor-led lesson (or a bounded no-gain search)")
    for clue in run["discoveries"]:
        refs([clue["donor"]], "donors", clue["id"])
        refs(clue["evidence"], "evidence", clue["id"])
        if not any(by["evidence"].get(e, {}).get("donor") == clue["donor"] for e in clue["evidence"]):
            errors.append(clue["id"] + ": discovery lacks matching donor evidence")
        if clue["target_need"] not in needs and not clue["target_need"].startswith("hypothesis:"):
            errors.append(clue["id"] + ": unknown target need/hypothesis")
        placeholder_errors(clue, "discoveries[" + clue["id"] + "]", errors)
    for item in group["discovery_searches"]:
        placeholder_errors(item, "discovery_searches[" + item["id"] + "]", errors)
    marks = list(scaffold_marks(run))
    if marks:
        errors.append("scaffold placeholders remain (" + str(len(marks)) + " values, first at " + marks[0] +
                      "); fill or remove every " + SCAFFOLD_MARK + " value")

    selected = [c for c in run["candidates"] if c["phase"] in ("selected", "design-reviewed")]
    selected_ids = {c["id"] for c in selected}
    if run["unresolved"]:
        errors.append(UNRESOLVED_MESSAGE)
    owned = {}
    for index, entry in enumerate(run["ownership"]):
        key = norm_key(entry["key"])
        if key in owned:
            errors.append("ownership conflict: multiple entries for one state/policy/interface (" + entry["key"].strip() + ")")
        owned.setdefault(key, entry)
        placeholder_errors(entry, "ownership[" + str(index) + "]", errors)
    owners = {norm_name(x["owner"]) for x in run["ownership"]}
    for c in run["candidates"]:
        cid = c["id"]
        refs([c["donor"]], "donors", cid)
        refs(c["evidence"], "evidence", cid)
        refs(c["discovery"], "discoveries", cid)
        for need in needs_of(c):
            if need not in needs:
                errors.append(cid + ": unestablished target requirement " + need)
        if run["mode"] == "design" and c["implementation"] != "not-started":
            errors.append(cid + ": design cannot claim implementation")
        if c["route"] == "defer" and c in selected:
            errors.append(cid + ": deferred route cannot be selected")
        if c["implementation"] in ("tested", "demonstrated"):
            for ident in (c["acceptance"], c["negative_control"]):
                if by["tests"].get(ident, {}).get("status") != "pass":
                    errors.append(cid + ": runtime promotion without passed acceptance/control")
            if c["implementation"] == "demonstrated":
                errors.append(cid + ": demonstrated benefit needs independent evaluation beyond this helper")
        if c in selected or c["implementation"] in ("tested", "demonstrated"):
            acceptance = required_test(c["acceptance"], cid + " acceptance")
            if acceptance and acceptance["purpose"] not in ("product", "adapter", "integration"):
                errors.append(cid + ": acceptance must test product, adapter or integration behavior")
            control = required_test(c["negative_control"], cid + " control")
            if control and control["purpose"] != "negative-control":
                errors.append(cid + ": control is not a negative-control test")
            if c["acceptance"] == c["negative_control"]:
                errors.append(cid + ": acceptance and control must differ")
        if c not in selected:
            continue
        if not c["closure"]:
            errors.append(cid + ": selected closure must be recorded, including reasoned no-dependency cases")
        if not any(by["discoveries"].get(d, {}).get("donor") == c["donor"] for d in c["discovery"]):
            errors.append(cid + ": selected unit lacks matching donor discovery")
        for label, text in c["seam"].items():
            if label != "evidence" and text_issue(text):
                errors.append(cid + ": unexplained seam field " + label + ": " + text_issue(text))
        seam_evidence = c["seam"].get("evidence", [])
        if not seam_evidence:
            errors.append(cid + ": seam lacks evidence links (add seam.evidence; schema 1.1)")
        else:
            refs(seam_evidence, "evidence", cid + " seam", groups=("evidence", "supporting_evidence"))
            if not any(by["evidence"].get(e, {}).get("donor") == c["donor"] for e in seam_evidence):
                errors.append(cid + ": seam evidence lacks matching donor source evidence")
            for e in seam_evidence:
                extra = by["supporting_evidence"].get(e)
                if extra and (extra["kind"] != "static-graph" or extra.get("donor") != c["donor"]):
                    errors.append(cid + ": seam may cite only source evidence or a static graph of its own donor: " + e)
        placeholder_errors({k: v for k, v in c.items() if k not in ("seam", "protocol", "deltas")},
                           "candidates[" + cid + "]", errors)
        if c["route"] in PROTOCOL_ROUTES:
            protocol = c.get("protocol")
            if not protocol:
                errors.append(cid + ": " + c["route"] + " route needs a protocol contract (protocol fields)")
            else:
                for label, text in protocol.items():
                    if text_issue(text):
                        errors.append(cid + ": unexplained protocol field " + label + ": " + text_issue(text))
                if all(_NOT_APPLICABLE.match(text) for text in protocol.values()):
                    errors.append(cid + ": " + c["route"] + " protocol cannot be entirely n/a")
        if not any(by["evidence"].get(e, {}).get("donor") == c["donor"] for e in c["evidence"]):
            errors.append(cid + ": selected unit lacks matching donor provenance")
        donor = by["donors"].get(c["donor"])
        if donor and donor["status"] != "reviewed":
            errors.append(cid + ": selected donor not reviewed")
        if donor and not is_real_pin(donor["revision"]):
            errors.append(cid + ": selected donor " + donor["id"] + " needs a real pin, not " + repr(donor["revision"]) +
                          " (full commit hash, or <immutable-tag>@sha256:<64-hex digest>)")
        if donor and c["source_language"].strip().casefold() not in {x.strip().casefold() for x in donor["languages"]}:
            errors.append(cid + ": source language not declared by donor")
        if c["target_language"].strip().casefold() != brief["target_language"].strip().casefold():
            errors.append(cid + ": target language disagrees with product brief")
        rights = c["rights"]
        if rights["status"] != "reviewed" or rights["route"] == "unresolved":
            errors.append(cid + ": rights unresolved or restricted")
        if rights.get("category") == "unknown":
            errors.append(cid + ": rights category unknown; classify it (open-source, source-available, "
                          "proprietary, public-domain or task-authored)")
        refs(rights["evidence"], "evidence", cid + " rights", groups=("evidence", "supporting_evidence"))
        scans = [by["supporting_evidence"][e] for e in rights["evidence"] if e in by["supporting_evidence"]]
        for scan in scans:
            if scan["kind"] != "license-scan" or scan.get("donor") != c["donor"]:
                errors.append(cid + ": rights may cite only source evidence or a license-scan of its own donor: " +
                              scan["id"])
        if not any(by["evidence"].get(e, {}).get("donor") == c["donor"] for e in rights["evidence"]) and not any(
                scan["kind"] == "license-scan" and scan.get("donor") == c["donor"] for scan in scans):
            errors.append(cid + ": rights lack matching donor evidence")
        category = rights.get("category")
        if v11 and category is None:
            errors.append(cid + ": record rights.category (open-source, source-available, proprietary, "
                          "public-domain or task-authored)")
        if v11 and c["route"] == "reimplementation" and "basis" not in c:
            errors.append(cid + ": reimplementation needs basis: code (rewritten from the donor's source) or "
                          "idea (rebuilt from the documented behaviour)")
        if is_code_route(c):
            route_label = c["route"] + (" from code" if c["route"] == "reimplementation" else "")
            if rights["route"] not in ("licensed-reuse", "permission"):
                errors.append(cid + ": route " + route_label + " reuses donor code; rights route " + rights["route"] +
                              " does not permit it (use licensed-reuse or permission, or reimplement from the idea)")
            elif category in PERMISSION_CATEGORIES and rights["route"] != "permission":
                errors.append(cid + ": " + category + " code needs rights route permission for " + route_label)
        for index, item in enumerate(c["closure"]):
            where = cid + " closure[" + str(index) + "]"
            if isinstance(item, dict):
                refs(item.get("evidence", []), "evidence", where, nonempty=False,
                     groups=("evidence", "supporting_evidence"))
                if item["category"] == "unknown":
                    errors.append(where + ": licence category unknown for " + item["name"])
                if item["disposition"] == "unresolved":
                    errors.append(where + ": dependency " + item["name"] + " has an unresolved disposition")
                if item["disposition"] in ("retain", "bridge"):
                    if not is_exact_pin(item["pin"]):
                        errors.append(where + ": retained " + item["name"] + " needs an exact pin (commit, "
                                      "tag@sha256 or one exact version), not " + repr(item["pin"]))
                    if item["category"] in PERMISSION_CATEGORIES and rights["route"] != "permission":
                        errors.append(where + ": retained " + item["category"] + " dependency " + item["name"] +
                                      " needs rights route permission")
            elif c["route"] in CODE_ROUTES and not _NONE_FORM.match(item.strip()) and not _NA_FORM.match(item.strip()):
                errors.append(cid + ": route " + c["route"] + " retains donor code; record retained dependencies as "
                              "structured closure items {name, pin, category, disposition}, or write 'none: <reason>'")
        implied = set()
        for e in c["evidence"]:
            source = by["evidence"].get(e)
            if source and source["donor"] == c["donor"]:
                implied.update(LANGUAGE_BY_EXTENSION.get(os.path.splitext(source["path"])[1].casefold(), ()))
        if implied and language_key(c["source_language"]) not in implied:
            errors.append(cid + ": source_language " + repr(c["source_language"]) + " disagrees with the evidence "
                          "file extension(s), which imply " + ", ".join(sorted(implied)))
        if norm_name(c["owner"]) not in owners:
            errors.append(cid + ": no authoritative owner entry")
        for key in c.get("touches", []):
            if norm_key(key) not in owned:
                errors.append(cid + ": touched key " + repr(key) + " has no ownership entry")
        crosses = c["source_language"].strip().casefold() != c["target_language"].strip().casefold()
        if crosses and c["route"] in REUSE_ROUTES:
            deltas = c.get("deltas", [])
            dimensions = [x["dimension"] for x in deltas]
            if set(dimensions) != set(SEMANTIC_DIMENSIONS) or len(dimensions) != len(set(dimensions)):
                errors.append(cid + ": incomplete or duplicate semantic delta dimensions")
            for delta in deltas:
                if delta["status"] == "unknown":
                    errors.append(cid + ": semantic mismatch unresolved: " + delta["dimension"])
                if delta["status"] != "not-applicable":
                    # A not-applicable delta needs only its reason; every other status carries the full mapping.
                    missing = [k for k in ("donor_semantics", "target_semantics", "conversion", "test") if k not in delta]
                    if missing:
                        errors.append(cid + ": delta " + delta["dimension"] + " needs " + ", ".join(missing) +
                                      " (only a not-applicable delta may omit them)")
                    if "test" in delta:
                        required_test(delta["test"], cid + " delta")
            placeholder_errors(deltas, "candidates[" + cid + "].deltas", errors)

    choice = run["decision"]["choice"]
    if choice == "fusion" and not any(c["route"] in REUSE_ROUTES for c in selected):
        errors.append("fusion needs at least one selected donor unit on a reuse route (" + ", ".join(REUSE_ROUTES) +
                      "); lessons alone are minimal-fresh or best-existing")
    if choice in ("best-existing", "minimal-fresh"):
        reuse = [c["id"] for c in selected if c["route"] != "pattern-only"]
        if reuse:
            errors.append("non-fusion choice must defer/reject fusion candidates; only pattern-only lessons may stay "
                          "selected: " + ", ".join(reuse))
    coverage = collections.defaultdict(set)
    for c in selected:
        for need in needs_of(c):
            coverage[need].add(c["id"])
    mapped = set()
    for entry in run.get("requirement_coverage", []):
        req = entry["requirement"]
        if req not in needs:
            errors.append("requirement_coverage: unknown requirement " + req)
        if req in mapped:
            errors.append("requirement_coverage: duplicate entry for " + req)
        mapped.add(req)
        for ref in entry["by"]:
            prefix = next((p for p in ("new:", "existing:") if ref.startswith(p)), None)
            if prefix:
                if text_issue(ref[len(prefix):] or "?"):
                    errors.append("requirement_coverage " + req + ": " + prefix + "<" +
                                  ("component" if prefix == "new:" else "product") + "> needs a name")
            elif ref not in by["candidates"]:
                errors.append("requirement_coverage " + req + ": unknown candidate " + ref)
            elif ref not in selected_ids:
                errors.append("requirement_coverage " + req + ": candidate " + ref + " is not selected")
            coverage[req].add(ref)
    # The coverage map is selected parts' needs plus requirement_coverage. In 1.1 every decision maps
    # every requirement; a 1.0 record keeps its original fusion-only rule.
    if choice == "fusion" or (v11 and choice != "defer"):
        missing = sorted(needs - set(coverage))
        if missing:
            errors.append("selected " + choice + " does not account for every requirement: " + ", ".join(missing) +
                          " (map each to selected candidates, new:<component> or existing:<product> in "
                          "requirement_coverage)")
    for label, text in run["global_review"].items():
        if text_issue(text):
            errors.append("global interaction review incomplete: " + label + ": " + text_issue(text))
    covered = set()
    for index, inter in enumerate(run["interactions"]):
        components = inter["components"]
        label = "interaction " + " / ".join(components)
        refs(components, "candidates", "interaction")
        if len(components) < 2 or len(set(components)) != len(components):
            errors.append("interaction requires distinct components")
        pair = frozenset(components)
        if len(pair) == 2:
            if pair in covered:
                errors.append("duplicate interaction pair")
            covered.add(pair)
        placeholder_errors(inter, "interactions[" + str(index) + "]", errors)
        if not pair <= selected_ids:
            continue
        if inter["status"] == "independent":
            surfaces = [by["candidates"].get(ident, {}).get("touches") for ident in components]
            if any(item is None for item in surfaces):
                errors.append(label + ": independent disposition needs declared touches on every component")
                continue
            if any(not item for item in surfaces):
                # An empty surface is undeclared, not proven disjoint.
                errors.append(label + ": independent disposition needs non-empty touches on every component")
                continue
            shared = set()
            for left, right in itertools.combinations([{norm_key(k) for k in item} for item in surfaces], 2):
                shared |= left & right
            if shared:
                errors.append(label + ": independent but both touch " + ", ".join(sorted(shared)))
            continue
        if inter["status"] not in ("compatible", "resolved"):
            errors.append("unresolved multi-donor interaction")
            continue
        refs(inter.get("evidence", []), "evidence", "interaction")
        if "test" not in inter:
            errors.append(label + ": compatible/resolved disposition needs an interaction or integration test "
                          "(or an independent disposition with disjoint touches)")
            continue
        test = required_test(inter["test"], "interaction")
        if test and test["purpose"] not in ("interaction", "integration"):
            errors.append(label + ": test " + inter["test"] + " has purpose " + test["purpose"] +
                          "; verify with an interaction or integration test (a negative control cannot verify an interaction)")
        elif test and len(pair) >= 3 and test["purpose"] != "integration":
            errors.append(label + ": a group interaction needs an integration test exercising every part together, "
                          "not the pairwise " + test["purpose"] + " test " + inter["test"])
    for pair in itertools.combinations(sorted(selected_ids), 2):
        if frozenset(pair) not in covered:
            errors.append("missing interaction review: " + " / ".join(pair))
    # Higher-order sharing: a key touched by three or more selected parts needs one group record.
    touched = collections.defaultdict(set)
    for c in selected:
        for key in c.get("touches", []):
            touched[norm_key(key)].add(c["id"])
    for key, parts in sorted(touched.items()):
        if len(parts) < 3:
            continue
        group_records = [inter for inter in run["interactions"] if parts <= set(inter["components"])]
        verified = [inter for inter in group_records if inter["status"] in ("compatible", "resolved") and
                    by["tests"].get(inter.get("test"), {}).get("purpose") == "integration"]
        if not group_records:
            errors.append("key " + key + " is touched by " + ", ".join(sorted(parts)) + ": record one group interaction "
                          "covering all of them, verified by an integration test (pairwise records do not cover it)")
        elif not verified:
            errors.append("group interaction for key " + key + " must be compatible or resolved and verified by an "
                          "integration test")
    if {x["kind"] for x in run["alternatives"]} != {"best-existing", "minimal-fresh", "fusion"}:
        errors.append("compare best existing, minimal fresh and fusion")
    directions = {}
    for index, alt in enumerate(run["alternatives"]):
        refs(alt["evidence"], "evidence", "alternative " + alt["kind"],
             groups=("evidence", "supporting_evidence", "discovery_searches"))
        placeholder_errors(alt, "alternatives[" + str(index) + "]", errors)
        names = [norm_name(d["name"]) for d in alt.get("dimensions", [])]
        if len(names) != len(set(names)):
            errors.append("alternative " + alt["kind"] + ": duplicate dimension name")
        for dimension in alt.get("dimensions", []):
            name = norm_name(dimension["name"])
            if directions.setdefault(name, dimension["direction"]) != dimension["direction"]:
                errors.append("dimension " + dimension["name"] + " must keep one direction across alternatives "
                              "(higher or lower is better)")
    placeholder_errors(run["decision"], "decision", errors)
    if choice == "defer":
        errors.append("design decision deferred")
    review_problems = review_issues(run["review"])
    if review_problems:
        errors.append("independent design review not accepted: " + "; ".join(review_problems))
    report = run["review"].get("report")
    if report and "sha256" in report:
        # The saved report is the review's evidence: hashed bytes that name the reviewer and level.
        data = verify_file(report["path"], report["sha256"], "review report")
        if data is not None:
            try:
                body = " ".join(data.decode("utf-8").split()).casefold()
            except UnicodeError:
                errors.append("review report must be UTF-8 text")
            else:
                level = run["review"].get("independence", "")
                if norm_name(run["review"]["reviewer"]) not in body or (level and level not in body):
                    errors.append("review report does not name the recorded reviewer (" + run["review"]["reviewer"] +
                                  ") and independence level (" + (level or "not recorded") + ")")

    history = collections.defaultdict(list)
    for receipt in run["receipts"]:
        history[receipt["test"]].append(receipt)
    latest = {}
    for ident, items in history.items():
        sequences = [r.get("sequence") for r in items]
        if len(items) > 1 and (None in sequences or len(set(sequences)) != len(sequences)):
            errors.append(ident + ": several receipts need unique sequence numbers (the latest decides status)")
            latest[ident] = items[-1]
        else:
            latest[ident] = max(items, key=lambda r: r.get("sequence") or 0)
    donor_files = {e["snapshot"] for e in run["evidence"]}
    donor_folders = {s.rsplit("/", 1)[0] for s in donor_files if "/" in s}
    for test in run["tests"]:
        verify_file(test["oracle"], test["oracle_sha256"], test["id"] + " oracle")
        if test["oracle"] in donor_files or any(test["oracle"].startswith(f + "/") for f in donor_folders):
            errors.append(test["id"] + ": oracle " + test["oracle"] + " is a donor file or sits in a donor snapshot "
                          "folder; keep oracles independent of donor code")
        if not test["frozen"]:
            errors.append(test["id"] + ": oracle not frozen")
        items = history.get(test["id"], [])
        if test["status"] in ("pass", "fail") and not items:
            errors.append(test["id"] + ": executed status needs exactly one receipt or an ordered receipt history")
        if test["status"] in ("not-run", "skipped", "blocked") and items:
            errors.append(test["id"] + ": unexecuted status has receipt")
        placeholder_errors(test, "tests[" + test["id"] + "]", errors)
    for receipt in run["receipts"]:
        refs([receipt["test"]], "tests", receipt["id"])
        verify_file(receipt["raw_output"], receipt["raw_sha256"], receipt["id"] + " raw")
        if receipt["cases"] != receipt["passed"] + receipt["failed"] + receipt["skipped"]:
            errors.append(receipt["id"] + ": inconsistent counts")
        placeholder_errors(receipt, "receipts[" + receipt["id"] + "]", errors)
        if latest.get(receipt["test"]) is not receipt:
            continue  # Earlier attempts stay as history; the latest receipt decides the status.
        test = by["tests"].get(receipt["test"], {})
        if test.get("status") == "pass":
            if receipt["cases"] <= 0 or receipt["passed"] <= 0 or receipt["failed"] or receipt["skipped"] or receipt["exit_code"]:
                errors.append(receipt["id"] + ": empty, failing, skipped or nonzero run cannot pass")
            if test.get("purpose") == "negative-control" and not receipt["control_detected"]:
                errors.append(receipt["id"] + ": negative control not detected")
        if test.get("status") == "fail" and not (receipt["failed"] > 0 or receipt["exit_code"] != 0):
            errors.append(receipt["id"] + ": failure status lacks failing observation")
    if v11:
        receipt_artifact_errors(run, by, latest, verify_file, errors)
    return errors


def receipt_artifact_errors(run, by, latest, verify_file, errors):
    """Bind 1.1 receipts to the product bytes they tested, and product files to their provenance."""
    manifest, current = {}, {}
    for item in run.get("artifacts", []):
        where = "artifact " + item["path"]
        if item["path"] in manifest:
            errors.append(where + ": listed twice in the artifact manifest")
        manifest[item["path"]] = item
        data = verify_file(item["path"], item["sha256"], where)
        if data is not None:
            current[item["path"]] = digest(data)
        for ident in item.get("candidates", []):
            if ident not in by["candidates"]:
                errors.append(where + ": unknown candidate " + ident)
        if item["origin"] in ("reused", "adapted"):
            if not item.get("unit") or text_issue(item["unit"]):
                errors.append(where + ": reused or adapted artifacts name their donor unit (unit)")
            parts = [by["candidates"][i] for i in item.get("candidates", []) if i in by["candidates"]]
            if not parts:
                errors.append(where + ": reused or adapted artifacts name the part they came from (candidates)")
            elif not any(is_code_route(part) for part in parts):
                errors.append(where + ": " + item["origin"] + " code needs a part on a code route (dependency, "
                              "narrow-port, ffi, process, rpc, wasm or reimplementation from code); its parts "
                              "reused only the idea")
    paths = collections.Counter(r["raw_output"] for r in run["receipts"])
    for receipt in run["receipts"]:
        if paths[receipt["raw_output"]] > 1 and not receipt.get("raw_shared"):
            errors.append(receipt["id"] + ": shares raw output " + receipt["raw_output"] + " with another receipt; "
                          "give each receipt its own raw output or declare raw_shared: <reason>")
        if latest.get(receipt["test"]) is not receipt:
            continue  # An earlier attempt may have tested earlier bytes; only the latest must be current.
        for item in receipt.get("artifacts", []):
            if item["path"] not in manifest:
                errors.append(receipt["id"] + ": artifact " + item["path"] + " is not in the artifact manifest")
            elif item["path"] in current and item["sha256"] != current[item["path"]]:
                errors.append(receipt["id"] + ": artifact " + item["path"] + " changed since this receipt (stale; "
                              "rerun and add a receipt with the next sequence)")
    for c in run["candidates"]:
        if c["implementation"] not in ("tested", "demonstrated"):
            continue
        mine = {path for path, item in manifest.items() if c["id"] in item.get("candidates", [])}
        if not mine:
            errors.append(c["id"] + ": " + c["implementation"] + " needs product artifacts listed for this part "
                          "(artifacts[].candidates)")
            continue
        for ident in (c["acceptance"], c["negative_control"]):
            receipt = latest.get(ident)
            if receipt is None or not any(item["path"] in mine for item in receipt.get("artifacts", [])):
                errors.append(c["id"] + ": the latest receipt for " + ident + " must list a product artifact of "
                              "this part (receipt.artifacts)")


def review_issues(review):
    """Design readiness needs an accepted review by someone other than the author, above self level."""
    problems = []
    if review["disposition"] != "accepted":
        problems.append("disposition " + review["disposition"])
    level = review.get("independence")
    if level is None:
        problems.append("record review.independence (" + " | ".join(INDEPENDENCE_LEVELS) + "; schema 1.1)")
    elif level == "self":
        problems.append("independence is self")
    if level is not None and "independent" in review and review["independent"] != (level != "self"):
        problems.append("independent flag contradicts review.independence")
    author = review.get("author")
    if author is None:
        problems.append("record review.author (schema 1.1)")
    elif norm_name(author) == norm_name(review["reviewer"]):
        problems.append("reviewer is the author")
    for label in ("reviewer", "author"):
        if label in review and text_issue(review[label]):
            problems.append("placeholder " + label)
    if review["disposition"] == "accepted":
        # An accepted review is an artifact, not a claim: its saved report is hashed and checked in check().
        if not review.get("report"):
            problems.append("no saved review report: cite the reviewer's saved report as review.report "
                            "(path and sha256 inside the run root)")
        if not review["findings"]:
            problems.append("record at least one finding (or one reading 'none: <reason>')")
    return problems


def implementation_state(run):
    """Implementation evidence, kept apart from design readiness."""
    if run.get("mode") != "implementation":
        return dict(state="design-mode", detail="design mode; no component is implemented or tested")
    tests = {t["id"]: t for t in run.get("tests", [])}
    selected = [c for c in run.get("candidates", []) if c["phase"] in ("selected", "design-reviewed")]
    selected_ids = {c["id"] for c in selected}
    required = []
    for c in selected:
        required += [c["acceptance"], c["negative_control"]]
        if c["source_language"].strip().casefold() != c["target_language"].strip().casefold() and c["route"] in REUSE_ROUTES:
            required += [d["test"] for d in c.get("deltas", []) if d["status"] != "not-applicable" and "test" in d]
    for inter in run.get("interactions", []):
        if frozenset(inter["components"]) <= selected_ids and inter["status"] in ("compatible", "resolved") and "test" in inter:
            required.append(inter["test"])
    statuses = collections.Counter(tests.get(t, {}).get("status", "missing") for t in dict.fromkeys(required))
    built = collections.Counter(c["implementation"] for c in selected)
    verified = bool(selected) and set(built) == {"tested"} and set(statuses) == {"pass"}
    detail = ("components " + ", ".join(k + " " + str(v) for k, v in sorted(built.items())) if built else
              "no selected donor components") + "; required tests " + (
              ", ".join(k + " " + str(v) for k, v in sorted(statuses.items())) or "none")
    return dict(state="recorded-checks-pass" if verified else "unverified", detail=detail)


def skeleton():
    return dict(schema_version=CURRENT_SCHEMA, id="new-product", mode="design", synthetic=False,
                brief=dict(outcome="TODO: new product outcome", users="TODO", question="product-led", non_goals=[],
                           requirements=[], constraints=[], target_language="TODO",
                           write_scope="TODO: isolated output root", authorization="Design only; no donor execution"),
                donors=[], evidence=[], supporting_evidence=[], discoveries=[], candidates=[], ownership=[],
                interactions=[], requirement_coverage=[],
                global_review=dict(cycles="Unknown", shared_versions="Unknown", resource_budget="Unknown", higher_order="Unknown"),
                alternatives=[], decision=dict(choice="defer", rationale="Await source analysis and alternatives"),
                tests=[], receipts=[], review=dict(author="Builder (name your agent and host)", reviewer="not-run",
                                                  independence="self", independent=False, disposition="not-run", findings=[],
                                                  adjudication="Independent review not yet requested"),
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
                        edge = dict(source=rel, target=name.name, line=n.lineno, relation="import",
                                    evidence="static", resolution="unresolved-module")
                        if name.asname:
                            edge["alias"] = name.asname
                        edges.append(edge)
                elif isinstance(n, ast.ImportFrom):
                    edge = dict(source=rel, target="." * n.level + (n.module or ""), line=n.lineno,
                                relation="import", evidence="static", resolution="unresolved-module",
                                names=[name.name for name in n.names])
                    aliases = {name.name: name.asname for name in n.names if name.asname}
                    if aliases:
                        edge["aliases"] = aliases
                    edges.append(edge)
                elif isinstance(n, ast.Call):
                    edges.append(dict(source=rel, target=ast.unparse(n.func), line=n.lineno,
                                      relation="call", evidence="static", resolution="unresolved-symbol"))
    return dict(schema_version="1.1", adapter="python-ast", tool_version=platform.python_version(),
                revision=revision, root=str(root), nodes=records, edges=edges, omissions=omissions,
                limits=["Syntax-level candidates only; no donor imports/execution.",
                        "Calls/imports unresolved; external deps, dynamic dispatch/imports, reflection, generated code,",
                        "framework injection, initialization in decorators/classes and runtime state need manual inspection.",
                        "No rights clearance, complete closure or seam qualification is implied."])


def closure_label(item):
    if isinstance(item, str):
        return item
    return (item["name"] + " @ " + item["pin"] + " (" + item["category"] + ", " + item["disposition"] +
            (", " + item["license"] if "license" in item else "") + ")")


def pareto_view(alternatives):
    """Non-dominated alternatives over the dimensions every scored alternative shares; None when unscored."""
    scored = [a for a in alternatives if a.get("dimensions")]
    if len(scored) < 2:
        return None
    tables = [{norm_name(d["name"]): (d["value"], d["direction"]) for d in a["dimensions"]} for a in scored]
    shared = sorted(set.intersection(*(set(t) for t in tables)))
    if not shared:
        return None

    def at_least(x, y, key):
        (vx, direction), (vy, _) = tables[x][key], tables[y][key]
        return vx <= vy if direction == "lower" else vx >= vy

    dominated = []
    for x in range(len(scored)):
        for y in range(len(scored)):
            if x != y and all(at_least(y, x, k) for k in shared) and any(not at_least(x, y, k) for k in shared):
                dominated.append((scored[x], scored[y]))
                break
    losers = {id(a) for a, _ in dominated}
    return dict(dimensions=shared, front=[a for a in scored if id(a) not in losers], dominated=dominated)


def report(run, errors, include_record=False):
    """Render the run as a readable dossier. Every record value is escaped as inert text."""
    def plain(value):
        # Donor-controlled fields must remain inert text in a rendered dossier.
        value = html.escape(str(value), quote=False).replace("\r", " ").replace("\n", " ")
        return re.sub(r"([\\`*_{}\[\]()#+.!|>~\-])", r"\\\1", value)

    def joined(values):
        return ", ".join(plain(v) for v in values) if values else "none"

    impl = implementation_state(run)
    readiness = ("design-blocked (" + str(len(errors)) + " findings)") if errors else "design-ready (record consistency only)"
    impl_label = {"design-mode": "not applicable", "unverified": "unverified",
                  "recorded-checks-pass": "recorded checks pass"}[impl["state"]]
    lines = ["# Frankenmine dossier: " + plain(run.get("id", "invalid")), "",
             "Design readiness: " + readiness,
             "Implementation: " + impl_label + " — " + plain(impl["detail"]),
             "Schema " + plain(run.get("schema_version", "unknown")) + "; mode " + plain(run.get("mode", "unknown")) +
             "; synthetic data: " + plain(run.get("synthetic", "unknown")), "",
             "This is a structural report, not semantic proof, authorization, or live-agent qualification. "
             "Supporting evidence is weaker than pinned source snapshots.", "", "## Findings", ""]
    lines.extend("- " + plain(item) for item in errors)
    if not errors:
        lines.append("- No structural/readiness errors detected.")
    brief = run["brief"]
    lines.extend(["", "## Brief", "",
                  "- Outcome: " + plain(brief["outcome"]), "- Users: " + plain(brief["users"]),
                  "- Question: " + plain(brief.get("question", "not recorded")),
                  "- Target language: " + plain(brief["target_language"]),
                  "- Write scope: " + plain(brief["write_scope"]), "- Authorization: " + plain(brief["authorization"])])
    lines.extend("- Requirement " + plain(x["id"]) + ": " + plain(x["criterion"]) for x in brief["requirements"])
    lines.extend("- Non-goal: " + plain(x) for x in brief["non_goals"])
    lines.extend("- Constraint: " + plain(x) for x in brief["constraints"])
    lines.extend(["", "## Donor accounting", ""])
    for d in run["donors"]:
        lines.append("- " + plain(d["id"]) + " @ " + plain(d["revision"]) + ": " + plain(d["status"]) + " — " +
                     plain(d["reason"]) + ". Languages: " + joined(d["languages"]) + ". Scope: " + plain(d["scope"]) +
                     ". Blind spots: " + joined(d["blind_spots"]))
    lines.extend(["", "## Evidence", ""])
    for e in run["evidence"]:
        lines.append("- " + plain(e["id"]) + " [" + plain(e["kind"]) + "] " + plain(e["donor"]) + " " + plain(e["path"]) +
                     " lines " + plain(e["start_line"]) + "–" + plain(e["end_line"]) + " — " + plain(e["scope"]) +
                     " (limits: " + plain(e["limitations"]) + ")")
    if run.get("supporting_evidence"):
        lines.extend(["", "Supporting evidence (weaker than source snapshots):", ""])
        for e in run["supporting_evidence"]:
            where = e.get("url") or e.get("snapshot") or "no locator"
            lines.append("- " + plain(e["id"]) + " [" + plain(e["kind"]) + "] " + plain(where) +
                         (", retrieved " + plain(e["retrieved"]) if "retrieved" in e else "") + " — " + plain(e["scope"]) +
                         " (limits: " + plain(e["limitations"]) + ")")
    lines.extend(["", "## Lesson ledger", ""])
    for d in run["donors"]:
        clues = [x for x in run["discoveries"] if x["donor"] == d["id"]]
        if not clues:
            continue
        lines.extend(["### " + plain(d["id"]), ""])
        for x in clues:
            lines.extend(["- " + plain(x["direction"]) + " · " + plain(x["stage"]) + " · " + plain(x["disposition"]) +
                          " — " + plain(x["problem"]) + " → " + plain(x["mechanism"]),
                          "  - Invariant: " + plain(x["invariant"]) + "; assumptions: " + plain(x["assumptions"]),
                          "  - Need or hypothesis: " + plain(x["target_need"]) + "; falsifier: " + plain(x["falsifier"]),
                          "  - Evidence: " + joined(x["evidence"]) + "; rationale: " + plain(x["rationale"])])
        lines.append("")
    lines.extend(["## Contracts", ""])
    for c in run["candidates"]:
        rights = c["rights"]
        lines.extend(["### " + plain(c["id"]) + ": " + plain(c["route"]) + "; design " + plain(c["phase"]) +
                      "; implementation " + plain(c["implementation"]), "",
                      "- Donor " + plain(c["donor"]) + ", unit " + plain(c["unit"]) + "; needs: " + joined(needs_of(c)),
                      "- Owner " + plain(c["owner"]) + "; caller " + plain(c["caller"]) + "; touches: " +
                      joined(c.get("touches", [])),
                      "- Contract: " + plain(c["contract"]) + "; intentional changes: " + plain(c["intentional_changes"]),
                      "- Closure: " + joined([closure_label(x) for x in c["closure"]]),
                      "- Seam (evidence: " + joined(c["seam"].get("evidence", [])) + "):"])
        lines.extend("  - " + plain(k) + ": " + plain(v) for k, v in c["seam"].items() if k != "evidence")
        lines.append("- Rights: " + plain(rights["status"]) + " / " + plain(rights["route"]) + " / " +
                     plain(rights.get("category", "category not recorded")) + " — " + plain(rights["license"]) +
                     "; unit " + plain(rights["unit"]) + "; obligations: " + joined(rights["obligations"]) +
                     "; evidence: " + joined(rights["evidence"]) + "; rationale: " + plain(rights["rationale"]))
        deltas = c.get("deltas", [])
        if deltas:
            counts = collections.Counter(x["status"] for x in deltas)
            lines.append("- Semantic deltas: " + ", ".join(plain(k) + " " + str(v) for k, v in sorted(counts.items())))
            lines.extend("  - " + plain(x["dimension"]) + " (" + plain(x["status"]) + "): " +
                         plain(x.get("donor_semantics", "not recorded")) + " → " +
                         plain(x.get("target_semantics", "not recorded")) + "; conversion: " +
                         plain(x.get("conversion", "not recorded")) + "; test: " + plain(x.get("test", "not recorded"))
                         for x in deltas if x["status"] != "not-applicable")
        if c["route"] in PROTOCOL_ROUTES and c.get("protocol"):
            lines.append("- Protocol:")
            lines.extend("  - " + plain(k) + ": " + plain(v) for k, v in c["protocol"].items())
        lines.extend(["- Recovery: " + plain(c["recovery"]) + "; maintenance: " + plain(c["maintenance"]) +
                      "; update: " + plain(c["update_strategy"]),
                      "- Acceptance " + plain(c["acceptance"]) + "; negative control " + plain(c["negative_control"]) +
                      "; falsifier: " + plain(c["falsifier"]) + "; alternative: " + plain(c["alternative"]), ""])
    lines.extend(["## Requirement coverage", ""])
    selected = [c for c in run["candidates"] if c["phase"] in ("selected", "design-reviewed")]
    for req in brief["requirements"]:
        covering = [c["id"] for c in selected if req["id"] in needs_of(c)]
        for entry in run.get("requirement_coverage", []):
            if entry["requirement"] == req["id"]:
                covering += [x for x in entry["by"] if x not in covering]
        lines.append("- " + plain(req["id"]) + ": " + (joined(covering) if covering else "not covered"))
    lines.extend(["", "## Ownership", ""])
    lines.extend("- " + plain(x["key"]) + " → " + plain(x["owner"]) + ": " + plain(x["rationale"]) for x in run["ownership"])
    lines.extend(["", "## Interactions", ""])
    for x in run["interactions"]:
        lines.append("- " + " / ".join(plain(c) for c in x["components"]) + ": " + plain(x["status"]) + " — " +
                     plain(x["rationale"]) + " (test: " + plain(x.get("test", "none")) + "; evidence: " +
                     joined(x.get("evidence", [])) + ")")
    review = run["global_review"]
    lines.append("- Global review — cycles: " + plain(review["cycles"]) + "; shared versions: " +
                 plain(review["shared_versions"]) + "; resource budget: " + plain(review["resource_budget"]) +
                 "; higher-order: " + plain(review["higher_order"]))
    if run.get("discovery_searches"):
        lines.extend(["", "## Donor search", ""])
        for s in run["discovery_searches"]:
            lines.append("- " + plain(s["id"]) + " (" + plain(s["date"]) + ") " + plain(s["source"]) +
                         (" — query: " + plain(s["query"]) if "query" in s else "") + "; considered: " +
                         joined(s["considered"]) + "; chosen: " + joined(s.get("chosen", [])) + "; rejected: " +
                         joined(s.get("rejected", [])) + " — " + plain(s["reason"]))
    lines.extend(["", "## Alternatives and decision", ""])
    for a in run["alternatives"]:
        lines.append("- " + plain(a["kind"]) + " — " + plain(a["name"]) + ": " + plain(a["tradeoffs"]) +
                     " (evidence: " + joined(a["evidence"]) + ")" + (
                         "; dimensions: " + ", ".join(plain(d["name"]) + " " + plain(d["value"]) + " (" +
                                                      plain(d["direction"]) + " is better)" for d in a["dimensions"])
                         if a.get("dimensions") else ""))
    front = pareto_view(run["alternatives"])
    if front:
        lines.append("- Pareto set on " + joined(front["dimensions"]) + ": " +
                     joined(a["kind"] + " (" + a["name"] + ")" for a in front["front"]))
        lines.append("- Dominated: " + ("; ".join(plain(a["kind"]) + " (by " + plain(b["kind"]) + ")"
                                                  for a, b in front["dominated"]) or "none"))
        if run["decision"]["choice"] in {a["kind"] for a, _ in front["dominated"]}:
            lines.append("- Note: the decision chooses a dominated alternative (" + plain(run["decision"]["choice"]) +
                         "); its rationale must justify that.")
    lines.append("- Decision: " + plain(run["decision"]["choice"]) + ". " + plain(run["decision"]["rationale"]))
    if run.get("artifacts"):
        lines.extend(["", "## Product artifacts and provenance", ""])
        for a in run["artifacts"]:
            lines.append("- " + plain(a["path"]) + " [" + plain(a["origin"]) + "] parts: " + joined(a.get("candidates", [])) +
                         ("; donor unit " + plain(a["unit"]) if "unit" in a else "") + "; sha256 " + plain(a["sha256"][:12]))
    lines.extend(["", "## Tests and receipts", ""])
    for t in run["tests"]:
        lines.append("- " + plain(t["id"]) + " (" + plain(t["purpose"]) + "): " + plain(t["status"]) + "; oracle " +
                     plain(t["oracle"]) + ("; frozen" if t["frozen"] else "; NOT frozen") + " — " + plain(t["spec"]))
        receipts = sorted((r for r in run["receipts"] if r["test"] == t["id"]), key=lambda r: r.get("sequence") or 0)
        for r in receipts:
            lines.append("  - receipt " + ("#" + plain(r["sequence"]) + " " if "sequence" in r else "") + plain(r["id"]) +
                         ": exit " + plain(r["exit_code"]) + "; cases " + plain(r["cases"]) + ", passed " + plain(r["passed"]) +
                         ", failed " + plain(r["failed"]) + ", skipped " + plain(r["skipped"]) +
                         ("; control detected" if r["control_detected"] else "") + "; raw " + plain(r["raw_output"]) +
                         ("; tested " + joined(x["path"] for x in r["artifacts"]) if r.get("artifacts") else ""))
    rv = run["review"]
    lines.extend(["", "## Review", "",
                  "- Author: " + plain(rv.get("author", "not recorded")) + "; reviewer: " + plain(rv["reviewer"]) +
                  "; independence: " + plain(rv.get("independence", "not recorded")) + "; disposition: " + plain(rv["disposition"]) +
                  "; saved report: " + (plain(rv["report"]["path"]) if rv.get("report") else "none")])
    lines.extend("- Finding: " + plain(x) for x in rv["findings"])
    lines.extend(["- Adjudication: " + plain(rv["adjudication"]), "", "## Unresolved", ""])
    lines.extend(("- " + plain(x) for x in run["unresolved"]) if run["unresolved"] else ["- none"])
    lines.append("")
    if include_record:
        record = encode(run).rstrip()
        fence = "`" * max(3, 1 + max((len(x) for x in re.findall(r"`+", record)), default=0))
        lines.extend(["## Full portable record", "", fence + "json", record, fence, ""])
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
    for name in ("check", "report", "handoff"):
        p = sub.add_parser(name)
        p.add_argument("run", type=Path)
        if name in ("report", "handoff"):
            p.add_argument("--output", type=Path, required=True)
        if name == "report":
            p.add_argument("--include-record", action="store_true", help="append the raw JSON record to the dossier")
        if name == "handoff":
            p.add_argument("--decisions", type=Path, help="optional original manifest; exact ID/URL joins only")
    p = sub.add_parser("check-lite", help="structure, checklist and file-hash check of a lite dossier")
    p.add_argument("dossier", type=Path)
    p = sub.add_parser("review-packet", help="write a conclusion-free packet for a fresh design reviewer")
    p.add_argument("run", type=Path)
    p.add_argument("--output", type=Path, required=True, help="new directory; never reused")
    p = sub.add_parser("stamp", help="fill missing file hashes into a NEW record or lite dossier (.md); recorded "
                                     "hashes are never rewritten")
    p.add_argument("run", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("scaffold-lite", help="write a lite dossier with numbered rows; it blocks until filled")
    p.add_argument("--output", type=Path, required=True)
    for flag in ("--donors", "--parts", "--requirements"):
        p.add_argument(flag, type=int, required=True)
    p.add_argument("--product", help="product name for the title")
    p = sub.add_parser("scaffold", help="add a candidate stub with placeholder seam and delta blocks to a NEW record")
    p.add_argument("run", type=Path)
    for flag in ("--donor", "--unit", "--route", "--id", "--output"):
        p.add_argument(flag, required=True, type=Path if flag == "--output" else str)
    p.add_argument("--source-language", help="defaults to the donor's first language")
    p.add_argument("--basis", choices=("code", "idea"), help="reimplementation only: rewritten from code, or from the idea")
    args = parser.parse_args(argv)
    try:
        if args.command == "check-lite":
            from lite_check import check_lite
            result = check_lite(args.dossier)
            print(encode(result), end="")
            return 0 if result["status"] == "lite-complete" else 2
        if args.command == "scaffold-lite" or (args.command == "stamp" and args.run.suffix.casefold() == ".md"):
            import lite_check
            if args.command == "stamp":
                result = lite_check.stamp_lite(args.run, args.output)
            else:
                result = lite_check.scaffold_lite(args.output, args.donors, args.parts, args.requirements, args.product)
            print(encode(result), end="")
            return 0 if result.get("ok", True) else 2
        if args.command in ("review-packet", "stamp", "scaffold"):
            import authoring
            if args.command == "review-packet":
                result = authoring.review_packet(args.run, args.output)
            elif args.command == "stamp":
                result = authoring.stamp(args.run, args.output)
            else:
                result = authoring.scaffold(args.run, args.output, donor=args.donor, unit=args.unit, route=args.route,
                                            ident=args.id, source_language=args.source_language, basis=args.basis)
            print(encode(result), end="")
            return 0 if result.get("ok", True) else 2
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
        if args.command == "handoff":
            from synthesis_handoff import build_index
            index = build_index(run, args.run, errors, args.decisions)
            write_new(args.output, encode(index))
            print(encode({"status": index["status"], "path": str(args.output),
                          "scope": "Derived continuation index; no benefit or temporal freshness qualification"}), end="")
            return 2 if index["status"] == "blocked" else 0
        shape_errors = record_schema_errors(run)
        if args.command == "report":
            if shape_errors:
                print(encode({"status": "invalid-record", "errors": shape_errors}), end="")
                return 2
            write_new(args.output, report(run, errors, include_record=args.include_record))
        impl = None if shape_errors else implementation_state(run)
        status = "design-blocked" if errors else "design-ready"
        if not errors and impl and impl["state"] != "design-mode":
            status += "; implementation-" + impl["state"]
        result = {"status": status, "scope": "record consistency; no semantic or live-agent qualification",
                  "errors": errors}
        if impl:
            result["implementation"] = impl["detail"]
        print(encode(result), end="")
        return 2 if errors else 0
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        print(encode({"status": "error", "reason": str(exc)}), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
