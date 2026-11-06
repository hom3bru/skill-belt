#!/usr/bin/env python3
"""westack-onboard's read verbs as an MCP server over stdio, opt-in. Standard library only; runs no command.

  python mcpserver.py --repo <path> [--db <file>]

Speaks JSON-RPC 2.0, one message per line, on stdin and stdout (the MCP stdio transport): initialize, tools/list and
tools/call for search, show, def, refs, callers, callees, context, delta and doctor. It never builds, updates, sets a
tier or writes guidance, and every call obeys the repository's trust tier. Registering it with a host (an MCP entry in
the host's settings) is persistent configuration: the user does it, or grants it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
PROTOCOL = "2025-06-18"
NAME_ARG = {"name": {"type": "string", "description": "a symbol: a bare name or Class.method"},
            "in": {"type": "string", "description": "optional repository path that pins one definition"}}
TOOLS = [
    {"name": "search", "description": "Search the repository index; returns files with their best chunks.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                      "budget": {"type": "string", "enum": ["conservative", "balanced"]},
                                                      "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "show", "description": "One indexed file's chunks (symbols and line ranges) and backlinks.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "def", "description": "Where a symbol is defined.",
     "inputSchema": {"type": "object", "properties": NAME_ARG, "required": ["name"]}},
    {"name": "refs", "description": "Chunks that mention a symbol, other than its definition.",
     "inputSchema": {"type": "object", "properties": NAME_ARG, "required": ["name"]}},
    {"name": "callers", "description": "Chunks that call a symbol, labelled by how they link to it.",
     "inputSchema": {"type": "object", "properties": NAME_ARG, "required": ["name"]}},
    {"name": "callees", "description": "What a symbol calls, resolved where possible.",
     "inputSchema": {"type": "object", "properties": NAME_ARG, "required": ["name"]}},
    {"name": "context", "description": "A symbol's definition, callees and callers inside a token budget.",
     "inputSchema": {"type": "object", "properties": dict(NAME_ARG, budget={"type": "string",
                                                                            "enum": ["conservative", "balanced"]}),
                     "required": ["name"]}},
    {"name": "delta", "description": "Files the index recorded as changed since a commit (seven or more characters).",
     "inputSchema": {"type": "object", "properties": {"since": {"type": "string"}}, "required": ["since"]}},
    {"name": "doctor", "description": "The index's health: OK, WARN or ERR with reasons.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def load_codeindex():
    spec = importlib.util.spec_from_file_location("westack_codeindex", HERE / "codeindex.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Server:
    def __init__(self, repo: Path, db: Optional[str]):
        self.ci = load_codeindex()
        self.repo = repo
        self.db = self.ci.resolve_db(repo, db)
        self.cfg = self.ci.config()

    def call(self, name: str, args: dict):
        ci = self.ci
        if name == "doctor":
            return ci.doctor(self.repo, self.db, self.cfg)
        ci.enforce(self.repo, "read")
        if not self.db.exists():
            raise ci.UsageError(f"no index at {self.db}: run codeindex.py build")
        conn = ci.connect(self.db)
        try:
            within = args.get("in")
            if name == "search":
                return ci.search(conn, args["query"], self.cfg, args.get("budget", "conservative"),
                                 int(args.get("limit", 10)))
            if name == "show":
                return ci.show(conn, args["path"].replace("\\", "/"))
            if name == "def":
                return {"definitions": ci.definitions(conn, args["name"], within), "note": ci.GRAPH_NOTE}
            if name == "refs":
                return {"references": ci.references(conn, args["name"], path=within), "note": ci.GRAPH_NOTE}
            if name == "callers":
                return {"callers": ci.callers(conn, args["name"], within), "note": ci.GRAPH_NOTE}
            if name == "callees":
                return {"callees": ci.callees(conn, args["name"], within), "note": ci.GRAPH_NOTE}
            if name == "context":
                return ci.context_pack(conn, args["name"], self.cfg, args.get("budget", "conservative"), within)
            if name == "delta":
                result = ci.delta(conn, args["since"])
                if result is None:
                    raise ci.UsageError(f"no advanced run at {args['since']} in this index's log")
                return result
        finally:
            conn.close()
        raise ci.UsageError(f"unknown tool {name}")

    def handle(self, msg: dict) -> Optional[dict]:
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:
            return None  # a notification, such as notifications/initialized
        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "westack-onboard-index", "version": "1.0.0-alpha.3"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = msg.get("params") or {}
                try:
                    payload = self.call(params.get("name"), params.get("arguments") or {})
                    result = {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}], "isError": False}
                except (self.ci.UsageError, self.ci.PolicyRefused, KeyError) as exc:
                    result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}}
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}}


def serve(server: Server, stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = server.handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="mcpserver.py")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--db")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    serve(Server(Path(args.repo), args.db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
