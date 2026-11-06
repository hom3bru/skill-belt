#!/usr/bin/env python3
"""westack-onboard index sharing, opt-in. Standard library only; runs no command.

  python indexsync.py export --repo <path> [--db <file>] --out <folder> [--exclude <path> ...]
  python indexsync.py import --repo <path> [--db <file>] --from <folder>

`export` writes the index's pages and chunks as JSONL (pages.jsonl, chunks.jsonl, meta.json) into a folder, after a
secret scan of every chunk: one finding refuses the whole export and writes nothing. `import` merges such a folder into
this machine's index: a page this index lacks is added; a page it has with other content is kept as it is (local wins)
and counted as a conflict. Moving the folder through a private git repository is the agent's job under the user's grant
(git add, commit, push, pull); this script never runs git. Exit codes: 0 ok; 1 the secret scan found something;
64 usage; 69 no index; 77 refused by the trust tier.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
EXPORT_FORMAT = "westack-index-export-1"
SECRETS = [
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----")),
    ("openai-style key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("assigned secret", re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*"
                                   r"['\"][^'\"\s]{12,}['\"]")),
]


def load_codeindex():
    spec = importlib.util.spec_from_file_location("westack_codeindex", HERE / "codeindex.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan(text: str, start_line: int) -> list:
    found = []
    for k, line in enumerate(text.split("\n")):
        for name, pattern in SECRETS:
            if pattern.search(line):
                found.append({"line": start_line + k, "kind": name})
    return found


def export(ci, repo: Path, db: Path, out: Path, exclude: Optional[list] = None) -> tuple:
    ci.enforce(repo, "read")
    exclude = {e.replace("\\", "/") for e in (exclude or [])}
    conn = ci.connect(db)
    try:
        pages = [dict(r) for r in conn.execute("SELECT id, path, title, kind, sha256, deleted, renamed_from FROM pages "
                                               "WHERE deleted = 0 ORDER BY path") if r["path"] not in exclude]
        ids = {p["id"]: p["path"] for p in pages}
        chunks, findings = [], []
        for r in conn.execute("SELECT * FROM chunks ORDER BY page_id, ord"):
            if r["page_id"] not in ids:
                continue
            for f in scan(r["body"], r["start_line"]):
                findings.append(dict(f, path=ids[r["page_id"]]))
            chunks.append({"path": ids[r["page_id"]], "ord": r["ord"], "symbol": r["symbol"], "kind": r["kind"],
                           "lines": [r["start_line"], r["end_line"]], "body": r["body"]})
        src = ci.source_row(conn)
    finally:
        conn.close()
    if findings:
        return 1, {"status": "refused", "reason": "the secret scan found likely secrets: nothing was written",
                   "findings": findings, "hint": "remove the secret from the file, or leave the file out with --exclude"}
    out.mkdir(parents=True, exist_ok=True)
    for p in pages:
        p.pop("id")
    (out / "pages.jsonl").write_text("".join(json.dumps(p, sort_keys=True) + "\n" for p in pages), encoding="utf-8")
    (out / "chunks.jsonl").write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in chunks), encoding="utf-8")
    meta = {"format": EXPORT_FORMAT, "repo_key": ci.repo_key(repo), "watermark": src["last_commit"],
            "schema": ci.SCHEMA_VERSION, "chunker": ci.CHUNKER_VERSION, "pages": len(pages), "chunks": len(chunks),
            "excluded": sorted(exclude)}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0, dict(meta, status="exported", out=str(out))


def import_(ci, repo: Path, db: Path, src_dir: Path) -> tuple:
    ci.enforce(repo, "update")
    meta = json.loads((src_dir / "meta.json").read_text(encoding="utf-8"))
    if meta.get("format") != EXPORT_FORMAT:
        raise ci.UsageError(f"{src_dir} is not a {EXPORT_FORMAT} export")
    if meta.get("repo_key") != ci.repo_key(repo):
        raise ci.UsageError(f"the export is for {meta.get('repo_key')}, not {ci.repo_key(repo)}")
    pages = [json.loads(l) for l in (src_dir / "pages.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    chunks = {}
    for line in (src_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            chunks.setdefault(c["path"], []).append(c)
    cfg = ci.config()
    fts = ci.fts5_available()
    conn = ci.connect(db, fts=fts, create=True)
    added, conflicts, same = [], [], 0
    try:
        fts = bool(ci.source_row(conn)["fts"])
        for p in pages:
            local = conn.execute("SELECT * FROM pages WHERE path = ?", (p["path"],)).fetchone()
            if local and not local["deleted"]:
                if local["sha256"] == p["sha256"]:
                    same += 1
                else:
                    conflicts.append(p["path"])
                continue
            text = "\n".join(c["body"] for c in sorted(chunks.get(p["path"], []), key=lambda c: c["ord"]))
            st = type("Stat", (), {"st_size": 0, "st_mtime_ns": 0})()
            ci.store_page(conn, p["path"], text, p["sha256"], st, cfg, fts)
            conn.execute("UPDATE pages SET title = ? WHERE path = ?", (p["title"], p["path"]))
            added.append(p["path"])
        conn.commit()
    finally:
        conn.close()
    return 0, {"status": "imported", "added": added, "same": same, "conflicts_kept_local": conflicts,
               "note": "imported pages are re-chunked from the exported text; their size and time are unknown, so "
                       "the next update re-reads any that exist in this working tree"}


def main(argv: Optional[list] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="indexsync.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    i = sub.add_parser("import")
    for p in (e, i):
        p.add_argument("--repo", required=True)
        p.add_argument("--db")
    e.add_argument("--out", required=True)
    e.add_argument("--exclude", action="append", default=[])
    i.add_argument("--from", dest="src", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 64
    ci = load_codeindex()
    try:
        repo = Path(args.repo)
        db = ci.resolve_db(repo, args.db)
        if not db.exists() and args.cmd == "export":
            print(f"indexsync.py: no index at {db}: run codeindex.py build", file=sys.stderr)
            return 69
        code, result = (export(ci, repo, db, Path(args.out), args.exclude) if args.cmd == "export"
                        else import_(ci, repo, db, Path(args.src)))
        print(json.dumps(result, indent=2))
        return code
    except ci.PolicyRefused as exc:
        print(f"indexsync.py: refused by policy: {exc}", file=sys.stderr)
        return 77
    except (ci.UsageError, OSError, ValueError) as exc:
        print(f"indexsync.py: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    sys.exit(main())
