"""Load one explicitly selected private Jobscura context. No reference is opened."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1024 * 1024
REPARSE_POINT = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT
NAME_SURROGATE = 0x20000000    # symlinks, junctions and mount points redirect a name
V2_PREFERENCES = {"monitoring", "search"}
# Defaults used when a context (or no context) leaves monitoring unset. They are
# workflow conventions, never permissions.
MONITORING_DEFAULTS = {"dated_check_days": 1, "undated_check_days": 2,
                       "reminder_windows_days": [14, 7, 3, 1, 0], "closing_horizon_days": 14,
                       "shortlist_size": 3, "urgency_open_days": 14, "long_open_days": 60}


class ContextError(ValueError):
    pass


def is_link(path):
    """True for a symlink or name-surrogate reparse point; cloud placeholders are ordinary files."""
    info = Path(path).lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    if getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
        tag = getattr(info, "st_reparse_tag", None)
        return tag is None or bool(tag & NAME_SURROGATE)
    return False


def timezone_status(name):
    """Report whether the host can compute dates in this IANA zone; never guess one."""
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        return "zoneinfo_unavailable"
    try:
        ZoneInfo(name)
        return "available"
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return "unavailable_in_host"


def monitoring(value):
    """Effective monitoring conventions: validated context values over documented defaults."""
    selected = ((value or {}).get("preferences") or {}).get("monitoring") or {}
    return {**MONITORING_DEFAULTS, **selected}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContextError("Duplicate JSON key; context was not loaded")
        result[key] = value
    return result


def validate(value, schema):
    """Enforce the closed, versioned subset used by the bundled JSON Schema."""
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "integer": type(value) is int,
               "number": type(value) is int or type(value) is float and math.isfinite(value),
               "boolean": type(value) is bool}
    if kind not in matches or not matches[kind]:
        raise ContextError("Invalid context field type")
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        raise ContextError("Unsupported schema version or fixed convention")
    if "enum" in schema and value not in schema["enum"]:
        raise ContextError("Unsupported context field value")
    if kind == "object":
        props = schema["properties"]
        if not set(schema.get("required", ())) <= value.keys():
            raise ContextError("Required context field missing")
        if schema.get("additionalProperties") is not False or set(value) - props.keys():
            raise ContextError("Unknown context field; credentials and permissions do not belong here")
        for key, item in value.items():
            validate(item, props[key])
    elif kind in {"array", "string"}:
        lower, upper = (("minItems", "maxItems") if kind == "array" else ("minLength", "maxLength"))
        if not schema.get(lower, 0) <= len(value) <= schema.get(upper, MAX_BYTES):
            raise ContextError("Context field length outside schema limits")
        if kind == "string" and (not value.strip() or "\x00" in value):
            raise ContextError("Context text must be nonblank and contain no NUL")
        if kind == "array":
            for item in value:
                validate(item, schema["items"])
    elif kind in {"integer", "number"}:
        if not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
            raise ContextError("Numeric context field outside schema limits")


def load_context(context_path=None, environ=None):
    """Return validated private data in memory; never search, save, or dereference it."""
    env = os.environ if environ is None else environ
    selected = context_path if context_path is not None else env.get("JOBSCURA_CONTEXT_FILE")
    if not isinstance(selected, (str, os.PathLike)) or not str(selected).strip():
        raise ContextError("No context selected; supply --context or JOBSCURA_CONTEXT_FILE")
    path = Path(selected).expanduser()
    if not path.is_absolute():
        raise ContextError("Context path must be absolute")
    try:
        # The selected file itself must not redirect elsewhere. Folders above it may be
        # operating-system aliases (macOS /var, redirected profiles); containment below
        # is decided on the fully resolved path, so they cannot smuggle context inward.
        if is_link(path):
            raise ContextError("Linked context paths are not supported")
        resolved = path.resolve(strict=True)
        root = ROOT.resolve()
        forbidden = [root] + [p for p in root.parents if (p / ".git").exists()]
        if any(resolved.is_relative_to(p) for p in forbidden):
            raise ContextError("Keep actual context outside the installed toolkit and its repository")
        if not resolved.is_file() or resolved.stat().st_size > MAX_BYTES:
            raise ContextError("Context must be a regular JSON file at most 1 MiB")
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ContextError("Context exceeds 1 MiB")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ContextError("Nonfinite JSON number")))
        schema = json.loads((ROOT / "context/user-context.schema.json").read_text(encoding="utf-8"))
        validate(value, schema)
        if value["schema_version"] == 1 and V2_PREFERENCES & value["preferences"].keys():
            raise ContextError("Monitoring and search preferences require schema_version 2")
        windows = value["preferences"].get("monitoring", {}).get("reminder_windows_days", [])
        if len(set(windows)) != len(windows):
            raise ContextError("Reminder windows must be distinct")
        return value
    except ContextError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError):
        # Exception text may contain private paths or document text.
        raise ContextError("Context unavailable or malformed; no context was loaded") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", help="absolute path to private JSON, outside this repository")
    args = parser.parse_args(argv)
    try:
        value = load_context(args.context)
        print(json.dumps({"status": "validated", "schema_version": value["schema_version"],
                          "sections": sorted(value), "references_opened": False,
                          "timezone_status": timezone_status(value["preferences"]["timezone"])}))
        return 0
    except ContextError as exc:
        print(json.dumps({"status": "context_not_loaded", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
