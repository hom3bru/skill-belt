#!/usr/bin/env python3
"""westack-review's shared-code lens. Standard library only; reads files, runs no command, writes nothing.

  python sharedcode.py scan <root> [--changed <file of paths>] [--min-lines N] [--min-files N] [--limit N]

Finds Python functions copied into several files: the same body once formatting, comments and docstrings are set
aside ("exact"), or the same shape with local names renamed ("renamed"). Each candidate lists its sites and an estimate
of lines removed and added; with --changed, only candidates touching a changed file (new duplication) are kept.
Report-only: it proposes, never extracts. Exit codes: 0 ok (candidates or none); 64 usage.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist", ".tox", ".mypy_cache"}


class Rename(ast.NodeTransformer):
    """Local names and arguments to placeholders in order of first use; attributes and globals keep their names."""

    def __init__(self, local: set):
        self.local, self.map = local, {}

    def _name(self, n):
        if n not in self.local:
            return n
        return self.map.setdefault(n, f"v{len(self.map)}")

    def visit_Name(self, node):
        node.id = self._name(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self._name(node.arg)
        node.annotation = None
        return node


def body_of(fn) -> list:
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # the docstring is prose, not behaviour
    return body


def fingerprints(fn) -> tuple:
    """(exact, renamed) hashes of the function's arguments and body, docstring dropped, names normalised in renamed."""
    import copy
    args = fn.args
    exact = ast.dump(ast.Module(body=body_of(fn), type_ignores=[]), annotate_fields=False) + ast.dump(args)
    local = {a.arg for a in args.args + args.posonlyargs + args.kwonlyargs}
    local |= {a.arg for a in (args.vararg, args.kwarg) if a}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
    clone = copy.deepcopy(ast.Module(body=body_of(fn), type_ignores=[]))
    clone_args = copy.deepcopy(args)
    r = Rename(local)
    clone_args = r.visit(clone_args)
    clone = r.visit(clone)
    renamed = ast.dump(clone, annotate_fields=False) + ast.dump(clone_args)
    return (hashlib.sha256(exact.encode()).hexdigest(), hashlib.sha256(renamed.encode()).hexdigest())


def functions(path: Path, rel: str):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{m.name}", m


def scan(root: Path, changed: Optional[set] = None, min_lines: int = 4, min_files: int = 2, limit: int = 5) -> dict:
    groups, scanned = {}, 0
    for path in sorted(root.rglob("*.py")):
        if SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        scanned += 1
        for symbol, fn in functions(path, rel):
            body = body_of(fn)
            if not body:
                continue
            size = body[-1].end_lineno - body[0].lineno + 1
            if size < min_lines:
                continue
            exact, renamed = fingerprints(fn)
            groups.setdefault(renamed, []).append({"path": rel, "symbol": symbol, "lines": [fn.lineno, fn.end_lineno],
                                                   "body_lines": size, "exact": exact})
    candidates = []
    for sites in groups.values():
        files = {s["path"] for s in sites}
        if len(files) < min_files:
            continue
        if changed is not None and not files & changed:
            continue
        kind = "exact" if len({s["exact"] for s in sites}) == 1 else "renamed"
        each = max(s["body_lines"] for s in sites)
        n = len(sites)
        candidates.append({
            "kind": kind, "name": sites[0]["symbol"].split(".")[-1], "files": len(files),
            "sites": [{k: s[k] for k in ("path", "symbol", "lines")} for s in sites],
            "estimate": {"lines_removed": each * (n - 1), "lines_added": n + 2,
                         "net": each * (n - 1) - (n + 2), "note": "an estimate: one shared helper, one import per site; "
                                                                  "tests for the helper not counted"},
            "new": changed is not None})
    candidates.sort(key=lambda c: (-c["files"], -c["estimate"]["net"], c["name"]))
    return {"root": str(root), "python_files": scanned, "min_lines": min_lines, "min_files": min_files,
            "changed_filter": sorted(changed) if changed is not None else None,
            "candidates": candidates[:limit], "more": max(0, len(candidates) - limit),
            "note": "report-only: each candidate is a lead; read every site before recommending an extraction"}


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if len(argv) < 2 or argv[0] != "scan":
            raise ValueError("usage: sharedcode.py scan <root> [--changed FILE] [--min-lines N] [--min-files N] [--limit N]")
        root, rest = Path(argv[1]), argv[2:]
        if not root.is_dir():
            raise ValueError(f"not a folder: {root}")
        opts = {"--changed": None, "--min-lines": "4", "--min-files": "2", "--limit": "5"}
        while rest:
            if rest[0] not in opts or len(rest) < 2:
                raise ValueError(f"unknown option {rest[0]}")
            opts[rest[0]], rest = rest[1], rest[2:]
        changed = None
        if opts["--changed"]:
            changed = {l.strip().replace("\\", "/") for l in Path(opts["--changed"]).read_text(encoding="utf-8").splitlines()
                       if l.strip()}
        print(json.dumps(scan(root, changed, int(opts["--min-lines"]), int(opts["--min-files"]), int(opts["--limit"])),
                         indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"sharedcode.py: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    sys.exit(main())
