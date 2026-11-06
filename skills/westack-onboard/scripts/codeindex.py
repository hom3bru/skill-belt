#!/usr/bin/env python3
"""westack-onboard repository index. Standard library only: sqlite3 with FTS5 when the Python build has it, otherwise a
pure-Python BM25. It runs no command: it reads the repository's files and its .git folder (HEAD, refs, the index file,
config) and writes only its own cache (the database, a lock and a state file), never inside the repository.

  python codeindex.py build  --repo <path> [--db <file>] [--files <list>]                 index every tracked file
  python codeindex.py update --repo <path> [--db <file>] [--files <list>] [--skip-failed] index what changed
  python codeindex.py search --repo <path> [--db <file>] [--budget conservative|balanced] [--limit N] <query>
  python codeindex.py show   --repo <path> [--db <file>] <path in the repository>          one page and its chunks
  python codeindex.py doctor --repo <path> [--db <file>]                                  OK, WARN or ERR, with reasons
  python codeindex.py def|refs|callers|callees --repo <path> <name>    where a symbol is defined, mentioned, called from, calls
  python codeindex.py context --repo <path> [--budget ...] <name>     its definition, callees and callers within a budget
  python codeindex.py delta --repo <path> --since <commit>            what the index recorded as changed since a watermark
  python codeindex.py policy --repo <path> [--set read-write|read-only|deny|unset]   this repository's trust tier
  python codeindex.py guidance --repo <path> [--file AGENTS.md|CLAUDE.md] [--write]  the search-guidance block, kept only
                                                                      while a ping through the index round-trips

The tier policy lives in %APPDATA%\\westack\\index-policy.json (or $WESTACK_CONFIG_DIR, or ~/.config/westack): deny refuses
everything, read-only refuses build, update and the ping. `policy --set` and `guidance --write` change persistent
configuration and an instruction file: run them only under the user's grant. guidance --write is the one command that
writes inside the repository, and only between the westack:index-guidance markers.

--files takes a saved `git ls-files` output when the .git index cannot be read (index version 4, or no .git folder).
The database lives in %LOCALAPPDATA%\\westack\\index (or $WESTACK_INDEX_DIR, or ~/.cache/westack/index), named from the
repository's normalised remote URL or, without one, its absolute path. Numbers: references/index.json.
Exit codes: 0 ok; 1 failures left unacknowledged (the watermark did not move), doctor ERR, or the guidance ping failed;
2 delta: the commit is not in this index's log; 64 usage; 69 no index yet; 75 another run holds the lock; 77 refused by
the trust tier.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 4
CHUNKER_VERSION = 3
CONFIG = Path(__file__).resolve().parent.parent / "references" / "index.json"
EXIT_OK, EXIT_FAIL, EXIT_UNSURE, EXIT_USAGE, EXIT_NO_INDEX, EXIT_LOCKED, EXIT_REFUSED = 0, 1, 2, 64, 69, 75, 77
POLICY_FORMAT = "westack-index-policy-1"
TIERS = ("read-write", "read-only", "deny")
GUIDE_START = "<!-- westack:index-guidance:start -->"
GUIDE_END = "<!-- westack:index-guidance:end -->"
GUIDE_TEXT = """## Searching this repository

westack-onboard keeps a search index of this repository's tracked files. Before reading widely, search it with the
westack-onboard skill's `codeindex.py search --repo . "<words>"`, then read the files it names; run `codeindex.py doctor
--repo .` when unsure the index is current. westack-onboard manages this block and removes it when the index stops
answering."""
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
MARKDOWN = {".md", ".markdown", ".mdx", ".rst", ".txt"}
CODE = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".cs", ".swift", ".c",
        ".h", ".cc", ".cpp", ".hpp", ".php", ".sh", ".bash", ".ps1", ".psm1", ".scala", ".lua"}
CONFIG_EXT = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml"}
JS = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
C_LIKE = {".java", ".cs", ".kt", ".scala", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".php"}
SHELL = {".sh", ".bash", ".ps1", ".psm1"}
DEF_PATTERNS = [(exts, re.compile(p)) for exts, p in (
    (JS | {".php"}, r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+([A-Za-z_$][\w$]*)"),
    (JS | C_LIKE | {".rb", ".py"}, r"^\s*(?:export\s+)?(?:default\s+)?(?:public\s+|abstract\s+|final\s+)*class\s+([A-Za-z_$][\w$]*)"),
    (JS, r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"),
    (JS, r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_$][\w$]*)"),
    ({".go"}, r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
    ({".go"}, r"^type\s+([A-Za-z_]\w*)"),
    ({".rs"}, r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"),
    ({".rs"}, r"^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+([A-Za-z_]\w*)"),
    ({".rb", ".lua"}, r"^\s*(?:local\s+)?(?:def|function)\s+([A-Za-z_][\w.:]*[!?]?)"),
    (C_LIKE, r"^\s*(?:public|private|protected|internal|static|override|async|virtual|final|\s)*[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\([^;]*$"),
    (SHELL, r"^\s*function\s+([\w-]+)"),
    (SHELL, r"^\s*([A-Za-z_][\w-]*)\s*\(\)\s*\{"),
)]
MD_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


class UsageError(Exception):
    pass


class Locked(Exception):
    pass


class PolicyRefused(Exception):
    pass


def config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read {CONFIG}: {exc}")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tokens(text: str) -> list:
    return TOKEN.findall(text.lower())


def estimate_tokens(text: str, cfg: dict) -> int:
    return max(1, math.ceil(len(text) / cfg["chunking"]["chars_per_token"]))


# ---------------------------------------------------------------- git, read from files only

def git_dir(repo: Path) -> Optional[Path]:
    p = repo / ".git"
    if p.is_file():
        m = re.match(r"gitdir:\s*(.+)", p.read_text(encoding="utf-8").strip())
        if not m:
            return None
        g = Path(m.group(1))
        return g if g.is_absolute() else (repo / g).resolve()
    return p if p.is_dir() else None


def common_dir(gd: Path) -> Path:
    c = gd / "commondir"
    if c.is_file():
        cd = Path(c.read_text(encoding="utf-8").strip())
        return cd if cd.is_absolute() else (gd / cd).resolve()
    return gd


def head_commit(repo: Path) -> Optional[str]:
    gd = git_dir(repo)
    if not gd or not (gd / "HEAD").is_file():
        return None
    head = (gd / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return head or None
    ref = head[4:].strip()
    for base in (gd, common_dir(gd)):
        f = base / ref
        if f.is_file():
            return f.read_text(encoding="utf-8").strip() or None
    packed = common_dir(gd) / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


def remote_url(repo: Path) -> Optional[str]:
    gd = git_dir(repo)
    if not gd:
        return None
    cfg = common_dir(gd) / "config"
    if not cfg.is_file():
        return None
    section, urls = None, {}
    for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        m = re.match(r'^\[\s*remote\s+"([^"]+)"\s*\]$', s)
        if m:
            section = m.group(1)
            continue
        if s.startswith("["):
            section = None
            continue
        m = re.match(r"^url\s*=\s*(.+)$", s)
        if section and m:
            urls.setdefault(section, m.group(1).strip())
    return urls.get("origin") or (next(iter(urls.values())) if urls else None)


def normalise_remote(url: str) -> str:
    """Strip the protocol, userinfo and .git, turn host:path into host/path, lowercase."""
    u = url.strip()
    u = re.sub(r"^[a-z][a-z0-9+.-]*://", "", u, flags=re.I)
    u = re.sub(r"^[^@/]+@", "", u)
    u = re.sub(r"^([^/:]+):(?!\d+/)", r"\1/", u)
    u = re.sub(r"\.git/?$", "", u).rstrip("/")
    return u.lower()


def read_git_index(repo: Path) -> list:
    """Tracked paths from the .git index file (versions 2 and 3), like `git ls-files`: no submodules, no symlinks."""
    gd = git_dir(repo)
    if not gd or not (gd / "index").is_file():
        raise UsageError("no .git index to read: pass --files with a saved `git ls-files` output")
    data = (gd / "index").read_bytes()
    if data[:4] != b"DIRC":
        raise UsageError(".git/index is not a git index file")
    version, count = struct.unpack(">II", data[4:12])
    if version not in (2, 3):
        raise UsageError(f".git/index version {version} is not read here: pass --files with a saved `git ls-files`")
    pos, paths = 12, set()
    for _ in range(count):
        mode = struct.unpack(">I", data[pos + 24:pos + 28])[0]
        flags = struct.unpack(">H", data[pos + 60:pos + 62])[0]
        header = 62 + (2 if (flags & 0x4000) and version >= 3 else 0)
        start = pos + header
        end = data.index(b"\x00", start)
        path = data[start:end].decode("utf-8", errors="surrogateescape")
        pos += (header + (end - start) + 8) & ~7
        if (mode & 0o170000) in (0o160000, 0o120000):
            continue
        paths.add(path)
    return sorted(paths)


def list_files(repo: Path, files_list: Optional[str], cfg: dict) -> tuple:
    if files_list:
        text = Path(files_list).read_text(encoding="utf-8")
        return sorted({l.strip().replace("\\", "/") for l in text.splitlines() if l.strip()}), "saved list"
    if git_dir(repo):
        return read_git_index(repo), "git index"
    skip = set(cfg["skip_dirs"])
    out = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in skip]
        for n in names:
            out.append(Path(root, n).relative_to(repo).as_posix())
    return sorted(out), "folder walk"


# ---------------------------------------------------------------- chunking

def page_kind(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in CODE:
        return "code"
    if ext in MARKDOWN:
        return "doc"
    if ext in CONFIG_EXT:
        return "config"
    return "other"


def chunk(start, end, symbol, kind, lines):
    text = "\n".join(lines[start - 1:end]).strip("\n")
    return {"start": start, "end": end, "symbol": symbol, "kind": kind, "text": text}


def gaps(covered: set, n: int, lines: list, kind="module") -> list:
    out, run = [], []
    for i in range(1, n + 1):
        if i in covered:
            if run:
                out.append(run)
            run = []
        else:
            run.append(i)
    if run:
        out.append(run)
    return [chunk(r[0], r[-1], None, kind, lines) for r in out if any(lines[i - 1].strip() for i in r)]


def call_of(node) -> Optional[tuple]:
    """(name, kind) for a call: f(...) is a "call", obj.m(...) an "attr" call."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id, "call"
    if isinstance(f, ast.Attribute):
        return f.attr, "attr"
    return None


def call_names(nodes) -> set:
    """Calls anywhere under the nodes, as (name, kind); decorators count, with or without arguments."""
    names = set()
    for top in nodes:
        for n in ast.walk(top):
            if isinstance(n, ast.Call) and call_of(n):
                names.add(call_of(n))
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not top:
                for d in n.decorator_list:
                    if isinstance(d, ast.Name):
                        names.add((d.id, "call"))
        for d in getattr(top, "decorator_list", []):
            if isinstance(d, ast.Name):
                names.add((d.id, "call"))
    return names


def python_chunks(text: str, lines: list) -> list:
    tree = ast.parse(text)
    out, covered = [], set()

    def first_line(node):
        return min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])

    def with_graph(c, refs, define=None):
        c["refs"] = sorted(refs)
        c["def"] = define
        return c

    module_calls = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            s, e = first_line(node), node.end_lineno
            out.append(with_graph(chunk(s, e, node.name, "function", lines), call_names([node]), node.name))
            covered.update(range(s, e + 1))
        elif isinstance(node, ast.ClassDef):
            s, e = first_line(node), node.end_lineno
            covered.update(range(s, e + 1))
            methods = [b for b in node.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))]
            inner = set()
            for m in methods:
                ms, me = first_line(m), m.end_lineno
                q = f"{node.name}.{m.name}"
                out.append(with_graph(chunk(ms, me, q, "method", lines), call_names([m]), q))
                inner.update(range(ms, me + 1))
            rest = [i for i in range(s, e + 1) if i not in inner]
            body = "\n".join(lines[i - 1] for i in rest).strip("\n")
            others = [b for b in node.body if b not in methods]
            out.append(with_graph({"start": s, "end": e, "symbol": node.name, "kind": "class", "text": body},
                                  call_names(others), node.name))
        else:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and call_of(n):
                    module_calls.append((n.lineno, call_of(n)))
    for g in gaps(covered, len(lines), lines):
        out.append(with_graph(g, {ref for ln, ref in module_calls if g["start"] <= ln <= g["end"]}))
    return out


NOT_CALLS = {"if", "for", "while", "switch", "catch", "return", "function", "typeof", "sizeof", "elif", "and", "or",
             "not", "in", "with", "await", "yield", "super", "this", "fn", "func", "def", "class", "new", "throw",
             "foreach", "using", "lock", "match", "case", "when", "else"}
CALL = re.compile(r"(\.?)\b([A-Za-z_$][\w$]*)\s*\(")


def markdown_chunks(lines: list) -> list:
    heads, fence = [], None
    for i, line in enumerate(lines, 1):
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            fence = None if fence and m.group(1)[0] == fence else (fence or m.group(1)[0])
            continue
        if not fence:
            h = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if h:
                heads.append((i, h.group(2)))
    out = []
    if not heads or heads[0][0] > 1:
        end = heads[0][0] - 1 if heads else len(lines)
        if any(l.strip() for l in lines[:end]):
            out.append(chunk(1, end, None, "preamble", lines))
    for k, (i, title) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        out.append(chunk(i, end, title, "section", lines))
    return out


def regex_chunks(lines: list, ext: str) -> list:
    patterns = [p for exts, p in DEF_PATTERNS if ext in exts]
    starts = []
    for i, line in enumerate(lines, 1):
        for p in patterns:
            m = p.match(line)
            if m:
                starts.append((i, m.group(1)))
                break
    if not starts:
        return []
    def refs(first, last, skip_first):
        body = "\n".join(lines[first:last] if skip_first else lines[first - 1:last])
        return sorted({(name, "attr" if dot else "call") for dot, name in CALL.findall(body) if name not in NOT_CALLS})

    out = []
    if starts[0][0] > 1 and any(l.strip() for l in lines[:starts[0][0] - 1]):
        c = chunk(1, starts[0][0] - 1, None, "module", lines)
        out.append(dict(c, refs=refs(1, starts[0][0] - 1, False), **{"def": None}))
    for k, (i, name) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(lines)
        out.append(dict(chunk(i, end, name, "definition", lines), refs=refs(i, end, True), **{"def": name}))
    return out


def window_chunks(lines: list, cfg: dict) -> list:
    words = [(w, i) for i, line in enumerate(lines, 1) for w in line.split()]
    size, overlap = cfg["chunking"]["window_words"], cfg["chunking"]["overlap_words"]
    out, start = [], 0
    while start < len(words):
        part = words[start:start + size]
        out.append({"start": part[0][1], "end": part[-1][1], "symbol": None, "kind": "window",
                    "text": " ".join(w for w, _ in part)})
        if start + size >= len(words):
            break
        start += size - overlap
    return out


def cap(chunks: list, cfg: dict) -> list:
    limit = cfg["chunking"]["max_tokens"] * cfg["chunking"]["chars_per_token"]
    out = []
    for c in chunks:
        if len(c["text"]) <= limit:
            out.append(c)
            continue
        part, n, first = [], 1, c["start"]
        lines = c["text"].split("\n")
        for k, line in enumerate(lines):
            if part and sum(len(x) + 1 for x in part) + len(line) > limit:
                out.append(dict(c, text="\n".join(part), start=first, end=first + len(part) - 1,
                                symbol=f"{c['symbol'] or c['kind']} (part {n})", **{"def": c.get("def") if n == 1 else None}))
                first, part, n = first + len(part), [], n + 1
            part.append(line[:limit])
        if part:
            out.append(dict(c, text="\n".join(part), start=first, end=first + len(part) - 1,
                            symbol=f"{c['symbol'] or c['kind']} (part {n})", **{"def": c.get("def") if n == 1 else None}))
    return out


def chunk_page(path: str, text: str, cfg: dict, ts: bool = False) -> list:
    lines = text.splitlines()
    ext = Path(path).suffix.lower()
    chunks = []
    if ext == ".py":
        try:
            chunks = python_chunks(text, lines)
        except SyntaxError:
            chunks = []
    elif ext in MARKDOWN:
        chunks = markdown_chunks(lines)
    elif ext in CODE:
        if ts and ext in TS_GRAMMARS:
            chunks = ts_chunks(text, lines, ext) or []
        if not chunks:
            chunks = regex_chunks(lines, ext)
    if not chunks:
        chunks = window_chunks(lines, cfg)
    chunks = [c for c in cap(chunks, cfg) if c["text"].strip()]
    chunks.sort(key=lambda c: (c["start"], c["end"]))
    return chunks


def page_title(path: str, text: str) -> str:
    if Path(path).suffix.lower() in MARKDOWN:
        for line in text.splitlines():
            m = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
            if m:
                return m.group(1)
    return Path(path).name


def page_links(path: str, text: str) -> list:
    if Path(path).suffix.lower() not in MARKDOWN:
        return []
    base = Path(path).parent
    out = set()
    for target in MD_LINK.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            continue
        out.add(os.path.normpath((base / target).as_posix()).replace("\\", "/"))
    return sorted(out)


# ---------------------------------------------------------------- storage

def fts5_available() -> bool:
    if os.environ.get("WESTACK_INDEX_NO_FTS"):
        return False
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.Error:
        return False


def repo_key(repo: Path) -> str:
    """The normalised remote URL, or the absolute path in lower case when there is no remote."""
    url = remote_url(repo)
    return normalise_remote(url) if url else str(repo.resolve()).lower()


# ---------------------------------------------------------------- trust tiers

def config_dir() -> Path:
    base = os.environ.get("WESTACK_CONFIG_DIR")
    if base:
        return Path(base)
    appdata = os.environ.get("APPDATA")
    return Path(appdata, "westack") if appdata else Path.home() / ".config" / "westack"


def policy_path() -> Path:
    return config_dir() / "index-policy.json"


def load_policy() -> dict:
    """Tiers by repository key. A file that is not valid JSON in the policy format is moved aside; while a moved-aside
    file exists and no new policy has been written, every repository is read-only (fail closed)."""
    p = policy_path()
    quarantined = sorted(str(q) for q in p.parent.glob(p.name + ".corrupt-*")) if p.parent.is_dir() else []
    if not p.exists():
        return {"tiers": {}, "quarantined": quarantined, "fail_closed": bool(quarantined), "moved": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        valid = (data.get("format") == POLICY_FORMAT and isinstance(data.get("remotes"), dict)
                 and all(v in TIERS for v in data["remotes"].values()))
    except (OSError, ValueError, AttributeError):
        valid = False
    if not valid:
        target = p.with_name(f"{p.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}")
        os.replace(p, target)
        return {"tiers": {}, "quarantined": quarantined + [str(target)], "fail_closed": True, "moved": str(target)}
    return {"tiers": {k.lower(): v for k, v in data["remotes"].items()}, "quarantined": quarantined,
            "fail_closed": False, "moved": None}


def tier_for(repo: Path) -> dict:
    policy, key = load_policy(), repo_key(repo)
    if policy["fail_closed"]:
        return {"key": key, "tier": "read-only", "policy": str(policy_path()), "quarantined": policy["quarantined"],
                "reason": "the policy file was not valid and was moved aside; every repository is read-only until "
                          "it is restored or a new policy is written"}
    tier = policy["tiers"].get(key, "unset")
    return {"key": key, "tier": tier, "policy": str(policy_path()), "quarantined": policy["quarantined"],
            "reason": f"the policy sets {tier}" if tier != "unset" else "no tier set for this repository"}


def enforce(repo: Path, action: str) -> dict:
    """deny refuses everything; read-only refuses build, update and the guidance ping; read-write and unset allow."""
    t = tier_for(repo)
    if t["tier"] == "deny" or (t["tier"] == "read-only" and action in ("build", "update", "ping")):
        raise PolicyRefused(f"{t['key']} is {t['tier']}: no {action} ({t['reason']}; {t['policy']})")
    return t


def set_tier(repo: Path, tier: str) -> dict:
    """Persistent configuration: the caller has the user's grant. 'unset' removes the entry."""
    if tier not in TIERS + ("unset",):
        raise UsageError(f"tier must be one of {', '.join(TIERS + ('unset',))}")
    p, key = policy_path(), repo_key(repo)
    policy = load_policy()
    tiers = dict(policy["tiers"])
    if tier == "unset":
        tiers.pop(key, None)
    else:
        tiers[key] = tier
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"format": POLICY_FORMAT, "remotes": dict(sorted(tiers.items()))}, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    return tier_for(repo)


def default_db(repo: Path) -> Path:
    key = repo_key(repo)
    base = os.environ.get("WESTACK_INDEX_DIR")
    if not base:
        local = os.environ.get("LOCALAPPDATA")
        base = str(Path(local, "westack", "index")) if local else str(Path.home() / ".cache" / "westack" / "index")
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[-40:] or "repo"
    return Path(base) / f"{slug}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}.sqlite"


def resolve_db(repo: Path, db: Optional[str]) -> Path:
    path = Path(db).resolve() if db else default_db(repo)
    try:
        path.relative_to(repo.resolve())
        raise UsageError(f"the index belongs outside the repository, not at {path}")
    except ValueError:
        return path


def connect(path: Path, fts: Optional[bool] = None, create: bool = False) -> sqlite3.Connection:
    if not create and not path.exists():
        raise FileNotFoundError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    if create:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY CHECK (id = 1), repo TEXT, remote_key TEXT,
                last_commit TEXT, chunker_version INTEGER, fts INTEGER, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, title TEXT, kind TEXT,
                sha256 TEXT, size INTEGER, mtime_ns INTEGER, deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
                renamed_from TEXT, indexed_at TEXT);
            CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, page_id INTEGER NOT NULL, ord INTEGER, symbol TEXT,
                kind TEXT, start_line INTEGER, end_line INTEGER, body TEXT, tokens INTEGER);
            CREATE INDEX IF NOT EXISTS chunks_page ON chunks(page_id);
            CREATE TABLE IF NOT EXISTS links(src INTEGER NOT NULL, dst_path TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS links_dst ON links(dst_path);
            CREATE TABLE IF NOT EXISTS failures(path TEXT PRIMARY KEY, reason TEXT, acknowledged INTEGER NOT NULL DEFAULT 0,
                seen_at TEXT);
            CREATE TABLE IF NOT EXISTS skipped(path TEXT PRIMARY KEY, reason TEXT);
            CREATE TABLE IF NOT EXISTS symbols(id INTEGER PRIMARY KEY, page_id INTEGER NOT NULL, chunk_id INTEGER NOT NULL,
                name TEXT NOT NULL, qualname TEXT NOT NULL, kind TEXT, start_line INTEGER, end_line INTEGER);
            CREATE INDEX IF NOT EXISTS symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS symbols_qualname ON symbols(qualname);
            CREATE TABLE IF NOT EXISTS refs(chunk_id INTEGER NOT NULL, page_id INTEGER NOT NULL, name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'call');
            CREATE INDEX IF NOT EXISTS refs_name ON refs(name);
            CREATE INDEX IF NOT EXISTS refs_chunk ON refs(chunk_id);
            CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, mode TEXT, head TEXT, started TEXT, finished TEXT,
                advanced INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS vectors(chunk_id INTEGER PRIMARY KEY, page_id INTEGER NOT NULL, model TEXT,
                dim INTEGER, vec BLOB);
            CREATE TABLE IF NOT EXISTS changes(run_id INTEGER NOT NULL, path TEXT NOT NULL, change TEXT NOT NULL,
                old_path TEXT);
        """)
        if fts:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(title, symbol, body)")
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(title)")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.execute("INSERT OR IGNORE INTO sources(id, fts) VALUES (1, ?)", (1 if fts else 0,))
        conn.commit()
    return conn


def stored_schema(db: Path) -> Optional[int]:
    """The schema version an existing index was written with, or None for a new one."""
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0
    except (sqlite3.Error, ValueError):
        return 0


def source_row(conn) -> sqlite3.Row:
    return conn.execute("SELECT * FROM sources WHERE id = 1").fetchone()


def title_text(path: str, title: str) -> str:
    return " ".join([path.replace("/", " ").replace("_", " ").replace("-", " ").replace(".", " "), title or ""])


def clear_page(conn, page_id: int, fts: bool):
    if fts:
        conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE page_id = ?)", (page_id,))
        conn.execute("DELETE FROM pages_fts WHERE rowid = ?", (page_id,))
    conn.execute("DELETE FROM chunks WHERE page_id = ?", (page_id,))
    conn.execute("DELETE FROM links WHERE src = ?", (page_id,))
    conn.execute("DELETE FROM symbols WHERE page_id = ?", (page_id,))
    conn.execute("DELETE FROM refs WHERE page_id = ?", (page_id,))
    conn.execute("DELETE FROM vectors WHERE page_id = ?", (page_id,))


def store_page(conn, path: str, text: str, digest: str, st, cfg: dict, fts: bool, renamed_from=None,
               ts: bool = False) -> int:
    title = page_title(path, text)
    row = conn.execute("SELECT id FROM pages WHERE path = ?", (path,)).fetchone()
    values = (title, page_kind(path), digest, st.st_size, st.st_mtime_ns, now())
    if row:
        page_id = row["id"]
        clear_page(conn, page_id, fts)
        conn.execute("UPDATE pages SET title=?, kind=?, sha256=?, size=?, mtime_ns=?, indexed_at=?, deleted=0, "
                     "deleted_at=NULL, renamed_from=COALESCE(?, renamed_from) WHERE id=?",
                     values + (renamed_from, page_id))
    else:
        page_id = conn.execute("INSERT INTO pages(path, title, kind, sha256, size, mtime_ns, indexed_at, renamed_from) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (path,) + values + (renamed_from,)).lastrowid
    ttext = title_text(path, title)
    for ordinal, c in enumerate(chunk_page(path, text, cfg, ts) if ts else chunk_page(path, text, cfg)):
        cid = conn.execute("INSERT INTO chunks(page_id, ord, symbol, kind, start_line, end_line, body, tokens) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (page_id, ordinal, c["symbol"], c["kind"], c["start"], c["end"], c["text"],
                            estimate_tokens(c["text"], cfg))).lastrowid
        if fts:
            conn.execute("INSERT INTO chunks_fts(rowid, title, symbol, body) VALUES (?, ?, ?, ?)",
                         (cid, ttext, c["symbol"] or "", c["text"]))
        if c.get("def"):
            conn.execute("INSERT INTO symbols(page_id, chunk_id, name, qualname, kind, start_line, end_line) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (page_id, cid, c["def"].split(".")[-1], c["def"], c["kind"],
                                                          c["start"], c["end"]))
        conn.executemany("INSERT INTO refs(chunk_id, page_id, name, kind) VALUES (?, ?, ?, ?)",
                         [(cid, page_id, name, kind) for name, kind in c.get("refs", [])])
    if fts:
        conn.execute("INSERT INTO pages_fts(rowid, title) VALUES (?, ?)", (page_id, ttext))
    for dst in page_links(path, text):
        conn.execute("INSERT INTO links(src, dst_path) VALUES (?, ?)", (page_id, dst))
    return page_id


# ---------------------------------------------------------------- opt-in extensions: local embeddings, tree-sitter

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Embedder:
    """A local embedding endpoint (Ollama's /api/embed or an OpenAI-style /v1/embeddings): off unless --embed is
    given. A host other than this machine needs the user's grant (--allow-remote-embed): chunks would leave it."""

    def __init__(self, url: str, model: Optional[str] = None, allow_remote: bool = False, timeout: float = 30):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise UsageError(f"--embed needs an http(s) URL, not {url!r}")
        if parsed.hostname.lower() not in LOCAL_HOSTS and not allow_remote:
            raise UsageError(f"{parsed.hostname} is not this machine: sending code to it needs the user's grant "
                             "(--allow-remote-embed)")
        self.url, self.model, self.timeout = url, model or "", timeout

    def embed(self, texts: list) -> list:
        import urllib.request
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        vectors = data.get("embeddings") or [d.get("embedding") for d in data.get("data", [])]
        if len(vectors) != len(texts) or not all(isinstance(v, list) and v for v in vectors):
            raise ValueError(f"the endpoint returned {len(vectors)} vectors for {len(texts)} texts")
        return vectors


def pack_vector(v: list) -> bytes:
    from array import array
    return array("f", v).tobytes()


def unpack_vector(b: bytes) -> list:
    from array import array
    a = array("f")
    a.frombytes(b)
    return list(a)


def cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed_pages(conn, embedder: "Embedder", page_ids: list, batch: int = 32) -> dict:
    """Vectors for the chunks of the given pages; a failure leaves those chunks without vectors and is reported."""
    rows = [r for pid in page_ids for r in conn.execute("SELECT id, page_id, body FROM chunks WHERE page_id = ?", (pid,))]
    done, failed, reason = 0, 0, None
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        try:
            vectors = embedder.embed([r["body"] for r in part])
        except Exception as exc:  # the endpoint is optional: keyword search stays whole
            failed += len(part)
            reason = f"{type(exc).__name__}: {exc}"
            continue
        conn.executemany("INSERT OR REPLACE INTO vectors(chunk_id, page_id, model, dim, vec) VALUES (?, ?, ?, ?, ?)",
                         [(r["id"], r["page_id"], embedder.model, len(v), pack_vector(v)) for r, v in zip(part, vectors)])
        done += len(part)
    conn.commit()
    return {"embedded": done, "not_embedded": failed, "reason": reason}


TS_GRAMMARS = {".js": ("tree_sitter_javascript", "language", "js"), ".mjs": ("tree_sitter_javascript", "language", "js"),
               ".cjs": ("tree_sitter_javascript", "language", "js"), ".jsx": ("tree_sitter_javascript", "language", "js"),
               ".ts": ("tree_sitter_typescript", "language_typescript", "js"),
               ".tsx": ("tree_sitter_typescript", "language_tsx", "js"),
               ".go": ("tree_sitter_go", "language", "go"), ".rs": ("tree_sitter_rust", "language", "rust")}
_PARSERS = {}


def ts_parser(ext: str):
    """A tree-sitter parser for the extension, or None when tree-sitter or its grammar is not installed."""
    if ext not in _PARSERS:
        try:
            import importlib
            import tree_sitter
            mod, fn, _ = TS_GRAMMARS[ext]
            _PARSERS[ext] = tree_sitter.Parser(tree_sitter.Language(getattr(importlib.import_module(mod), fn)()))
        except (ImportError, KeyError, AttributeError, TypeError, ValueError):
            _PARSERS[ext] = None
    return _PARSERS[ext]


def tree_sitter_probe() -> str:
    try:
        import tree_sitter  # noqa: F401
    except ImportError:
        return "not installed: definition patterns used"
    ready = sorted({TS_GRAMMARS[e][0].replace("tree_sitter_", "") for e in TS_GRAMMARS if ts_parser(e)})
    return f"used for {', '.join(ready)}" if ready else "installed without the grammars: definition patterns used"


def ts_chunks(text: str, lines: list, ext: str) -> Optional[list]:
    """Definitions and calls from a tree-sitter parse (JavaScript, TypeScript, Go, Rust); None to fall back."""
    parser = ts_parser(ext)
    if not parser:
        return None
    family = TS_GRAMMARS[ext][2]
    src = text.encode("utf-8")
    root = parser.parse(src).root_node

    def txt(n):
        return src[n.start_byte:n.end_byte].decode("utf-8", errors="replace") if n else None

    def name_of(n):
        return txt(n.child_by_field_name("name"))

    def call_of_node(n):
        if n.type not in ("call_expression", "method_call_expression", "new_expression"):
            return None
        f = n.child_by_field_name("function") or n.child_by_field_name("constructor")
        if n.type == "method_call_expression":
            return (txt(n.child_by_field_name("method")), "attr")
        if f is None:
            return None
        if f.type in ("identifier", "type_identifier"):
            return (txt(f), "call")
        if f.type == "member_expression":
            return (txt(f.child_by_field_name("property")), "attr")
        if f.type == "selector_expression":
            return (txt(f.child_by_field_name("field")), "attr")
        if f.type == "field_expression":
            return (txt(f.child_by_field_name("field")), "attr")
        if f.type == "scoped_identifier":
            return (txt(f.child_by_field_name("name")), "attr")
        return None

    def calls_in(nodes, skip=()):
        found, stack = set(), list(nodes)
        while stack:
            n = stack.pop()
            if any(n.start_byte >= s.start_byte and n.end_byte <= s.end_byte for s in skip):
                continue
            c = call_of_node(n)
            if c and c[0]:
                found.add(c)
            stack.extend(n.children)
        return found

    out, covered = [], set()

    def span(n):
        return n.start_point[0] + 1, n.end_point[0] + 1

    def add(outer, symbol, kind, define, refs_nodes=None, skip=()):
        s, e = span(outer)
        out.append(dict(chunk(s, e, symbol, kind, lines), refs=sorted(calls_in(refs_nodes or [outer], skip)),
                        **{"def": define}))
        covered.update(range(s, e + 1))

    def container(outer, cls, members, kind_of, define=True):
        s, e = span(outer)
        inner, skip = set(), []
        for m in members:
            q = f"{cls}.{name_of(m)}"
            ms, me = span(m)
            out.append(dict(chunk(ms, me, q, "method", lines), refs=sorted(calls_in([m])), **{"def": q}))
            inner.update(range(ms, me + 1))
            skip.append(m)
        rest = [i for i in range(s, e + 1) if i not in inner]
        out.append({"start": s, "end": e, "symbol": cls, "kind": kind_of, "def": cls if define else None,
                    "text": "\n".join(lines[i - 1] for i in rest).strip("\n"), "refs": sorted(calls_in([outer], skip))})
        covered.update(range(s, e + 1))

    for outer in root.children:
        node = outer
        if node.type == "export_statement":
            node = node.child_by_field_name("declaration") or next((c for c in node.named_children), node)
        t = node.type
        if family == "js":
            if t in ("function_declaration", "generator_function_declaration"):
                add(outer, name_of(node), "function", name_of(node))
            elif t in ("class_declaration", "abstract_class_declaration"):
                body = node.child_by_field_name("body")
                members = [m for m in (body.named_children if body else []) if m.type == "method_definition"]
                container(outer, name_of(node), members, "class")
            elif t in ("lexical_declaration", "variable_declaration"):
                for d in node.named_children:
                    v = d.child_by_field_name("value") if d.type == "variable_declarator" else None
                    if v is not None and v.type in ("arrow_function", "function_expression", "function"):
                        add(outer, name_of(d), "function", name_of(d))
                        break
            elif t in ("interface_declaration", "type_alias_declaration", "enum_declaration"):
                add(outer, name_of(node), "definition", name_of(node))
        elif family == "go":
            if t == "function_declaration":
                add(outer, name_of(node), "function", name_of(node))
            elif t == "method_declaration":
                recv = node.child_by_field_name("receiver")
                owner = re.findall(r"[A-Za-z_]\w*", txt(recv) or "")
                q = f"{owner[-1]}.{name_of(node)}" if owner else name_of(node)
                add(outer, q, "method", q)
            elif t == "type_declaration":
                specs = [c for c in node.named_children if c.type == "type_spec"]
                if specs:
                    add(outer, name_of(specs[0]), "class", name_of(specs[0]))
        elif family == "rust":
            if t == "function_item":
                add(outer, name_of(node), "function", name_of(node))
            elif t in ("struct_item", "enum_item", "trait_item"):
                add(outer, name_of(node), "class", name_of(node))
            elif t == "impl_item":
                owner = txt(node.child_by_field_name("type"))
                body = node.child_by_field_name("body")
                members = [m for m in (body.named_children if body else []) if m.type == "function_item"]
                container(outer, owner, members, "impl", define=False)
    module_calls = []
    stack = [root]
    while stack:
        n = stack.pop()
        c = call_of_node(n)
        if c and c[0] and (n.start_point[0] + 1) not in covered:
            module_calls.append((n.start_point[0] + 1, c))
        stack.extend(n.children)
    for g in gaps(covered, len(lines), lines):
        out.append(dict(g, refs=sorted({c for ln, c in module_calls if g["start"] <= ln <= g["end"]}), **{"def": None}))
    return out


# ---------------------------------------------------------------- lock and state

def acquire_lock(db: Path, cfg: dict) -> dict:
    lock = Path(str(db) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}-{time.time_ns()}"
    body = json.dumps({"pid": os.getpid(), "token": token, "started": now()})
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        return {"path": lock, "token": token, "took_over": False}
    except FileExistsError:
        age = time.time() - lock.stat().st_mtime
        if age <= cfg["lock_stale_seconds"]:
            raise Locked(f"{lock} is held by another run ({int(age)} s old; stale after {cfg['lock_stale_seconds']} s)")
        tmp = Path(str(lock) + f".{token}.tmp")
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, lock)
        return {"path": lock, "token": token, "took_over": True, "stale_age_s": int(age)}


def release_lock(held: dict):
    try:
        if json.loads(held["path"].read_text(encoding="utf-8")).get("token") == held["token"]:
            held["path"].unlink()
    except (OSError, ValueError):
        pass


def write_state(db: Path, state: dict):
    target = Path(str(db) + ".state.json")
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, target)


def read_state(db: Path) -> Optional[dict]:
    try:
        return json.loads(Path(str(db) + ".state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- build and update

def sync(repo: Path, db: Path, mode: str, files_list: Optional[str] = None, skip_failed: bool = False,
         cfg: Optional[dict] = None, embedder: Optional["Embedder"] = None, tree_sitter: bool = False) -> tuple:
    cfg = cfg or config()
    repo = repo.resolve()
    tier = enforce(repo, mode)
    held = acquire_lock(db, cfg)
    try:
        if mode == "build" and db.exists():
            db.unlink()
        old_schema = stored_schema(db)
        if old_schema not in (None, SCHEMA_VERSION):
            old = sqlite3.connect(str(db))
            try:
                old.execute("DROP TABLE IF EXISTS refs")
                old.execute("DROP TABLE IF EXISTS symbols")
                old.commit()
            finally:
                old.close()
        fts = fts5_available()
        conn = connect(db, fts=fts, create=True)
        src = source_row(conn)
        fts = bool(src["fts"])
        if fts and not fts5_available():
            raise UsageError("this index was built with FTS5, which this Python lacks: run build again")
        listed_paths, listed_by = list_files(repo, files_list, cfg)
        paths = [p for p in listed_paths if (repo / p).is_file()]
        head = head_commit(repo)
        run_id = conn.execute("INSERT INTO runs(mode, head, started) VALUES (?, ?, ?)", (mode, head, now())).lastrowid
        conn.commit()
        rewalk = mode == "build" or src["chunker_version"] != CHUNKER_VERSION or old_schema not in (None, SCHEMA_VERSION)
        ts_row = conn.execute("SELECT value FROM meta WHERE key = 'tree_sitter'").fetchone()
        rewalk = rewalk or (ts_row[0] if ts_row else "0") != ("1" if tree_sitter else "0")
        report = {"indexed": [], "unchanged": 0, "deleted": [], "renamed": [], "skipped": [], "failures": []}
        existing = {r["path"]: r for r in conn.execute("SELECT * FROM pages")}
        listed = set(paths)
        gone = {p: r for p, r in existing.items() if p not in listed and not r["deleted"]}
        by_hash = {}
        for p, r in gone.items():
            by_hash.setdefault(r["sha256"], []).append(p)
        for path in paths:
            full = repo / path
            try:
                st = full.stat()
                if st.st_size > cfg["max_file_bytes"]:
                    report["skipped"].append((path, "over the size cap"))
                    continue
                row = existing.get(path)
                if (row and not row["deleted"] and not rewalk and row["size"] == st.st_size
                        and row["mtime_ns"] == st.st_mtime_ns):
                    report["unchanged"] += 1
                    continue
                data = full.read_bytes()
                if b"\x00" in data[:8192]:
                    report["skipped"].append((path, "binary"))
                    continue
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    report["skipped"].append((path, "not UTF-8 text"))
                    continue
                digest = hashlib.sha256(data).hexdigest()
                if row and not row["deleted"] and not rewalk and row["sha256"] == digest:
                    conn.execute("UPDATE pages SET mtime_ns = ?, size = ? WHERE id = ?",
                                 (st.st_mtime_ns, st.st_size, row["id"]))
                    conn.commit()
                    report["unchanged"] += 1
                    continue
                renamed_from = None
                if path not in existing and by_hash.get(digest):
                    renamed_from = by_hash[digest][0]
                    conn.execute("UPDATE pages SET path = ? WHERE id = ?", (path, gone[renamed_from]["id"]))
                store_page(conn, path, text, digest, st, cfg, fts, renamed_from, tree_sitter)
                if renamed_from:
                    change = "renamed"
                elif not row or row["deleted"]:
                    change = "added"
                else:
                    change = "rechunked" if row["sha256"] == digest else "modified"
                conn.execute("INSERT INTO changes(run_id, path, change, old_path) VALUES (?, ?, ?, ?)",
                             (run_id, path, change, renamed_from))
                conn.execute("DELETE FROM failures WHERE path = ?", (path,))
                conn.commit()
                if renamed_from:
                    by_hash[digest].pop(0)
                    gone.pop(renamed_from)
                    report["renamed"].append({"from": renamed_from, "to": path})
                else:
                    report["indexed"].append(path)
            except Exception as exc:  # one file's failure never stops the run; it holds the watermark instead
                conn.rollback()
                conn.execute("INSERT INTO failures(path, reason, acknowledged, seen_at) VALUES (?, ?, 0, ?) "
                             "ON CONFLICT(path) DO UPDATE SET reason=excluded.reason, seen_at=excluded.seen_at",
                             (path, f"{type(exc).__name__}: {exc}", now()))
                conn.commit()
                report["failures"].append({"path": path, "reason": f"{type(exc).__name__}: {exc}"})
        for path, r in gone.items():
            clear_page(conn, r["id"], fts)
            conn.execute("UPDATE pages SET deleted = 1, deleted_at = ? WHERE id = ?", (now(), r["id"]))
            conn.execute("INSERT INTO changes(run_id, path, change) VALUES (?, ?, 'deleted')", (run_id, path))
            report["deleted"].append(path)
        conn.execute("DELETE FROM skipped")
        conn.executemany("INSERT OR REPLACE INTO skipped VALUES (?, ?)", report["skipped"])
        conn.execute("DELETE FROM failures WHERE path NOT IN (SELECT value FROM json_each(?))", (json.dumps(paths),))
        if skip_failed:
            conn.execute("UPDATE failures SET acknowledged = 1")
        open_failures = [r["path"] for r in conn.execute("SELECT path FROM failures WHERE acknowledged = 0")]
        advanced = not open_failures
        if advanced:
            conn.execute("UPDATE sources SET last_commit = ?, chunker_version = ?, repo = ?, remote_key = ?, "
                         "updated_at = ? WHERE id = 1",
                         (head, CHUNKER_VERSION, str(repo),
                          normalise_remote(remote_url(repo)) if remote_url(repo) else None, now()))
        conn.execute("UPDATE runs SET finished = ?, advanced = ? WHERE id = ?", (now(), 1 if advanced else 0, run_id))
        if advanced:
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('tree_sitter', ?)", ("1" if tree_sitter else "0",))
        conn.commit()
        embedding = None
        if embedder:
            missing = [r[0] for r in conn.execute(
                "SELECT DISTINCT c.page_id FROM chunks c JOIN pages p ON p.id = c.page_id LEFT JOIN vectors v "
                "ON v.chunk_id = c.id AND v.model = ? WHERE p.deleted = 0 AND v.chunk_id IS NULL", (embedder.model,))]
            embedding = dict(embed_pages(conn, embedder, missing), endpoint=embedder.url, model=embedder.model)
        totals = conn.execute("SELECT (SELECT COUNT(*) FROM pages WHERE deleted = 0) AS pages, "
                              "(SELECT COUNT(*) FROM chunks) AS chunks, (SELECT COUNT(*) FROM symbols) AS symbols"
                              ).fetchone()
        src = source_row(conn)
        conn.close()
        status = "OK" if advanced and not report["failures"] else ("WARN" if advanced else "ERR")
        state = {"format": "westack-index-state-1", "mode": mode, "status": status, "finished": now(),
                 "listed_by": listed_by, "head": head, "watermark": src["last_commit"],
                 "watermark_advanced": advanced, "chunker_version": CHUNKER_VERSION, "rewalk": rewalk,
                 "fts": fts, "pages": totals["pages"], "chunks": totals["chunks"], "symbols": totals["symbols"],
                 "run": run_id, "indexed": len(report["indexed"]), "unchanged": report["unchanged"],
                 "deleted": report["deleted"], "renamed": report["renamed"], "skipped": len(report["skipped"]),
                 "failures": report["failures"], "unacknowledged": open_failures,
                 "lock_takeover": held["took_over"], "tier": tier["tier"], "embeddings": embedding,
                 "tree_sitter": tree_sitter_probe() if tree_sitter else None}
        write_state(db, state)
        return (EXIT_OK if advanced else EXIT_FAIL), dict(state, db=str(db))
    finally:
        release_lock(held)


# ---------------------------------------------------------------- search

def fts_query(terms: list) -> str:
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


def bm25_rank(docs: dict, terms: list, weights: list) -> list:
    """Pure-Python weighted BM25 over docs {id: [field token lists]}: ids, best first."""
    k1, b = 1.2, 0.75
    n = len(docs)
    if not n:
        return []
    fields = len(weights)
    avg = [sum(len(d[f]) for d in docs.values()) / n or 1 for f in range(fields)]
    df = [{t: sum(1 for d in docs.values() if t in set(d[f])) for t in terms} for f in range(fields)]
    scores = {}
    for i, d in docs.items():
        s = 0.0
        for f in range(fields):
            if not weights[f]:
                continue
            length = len(d[f])
            for t in terms:
                tf = d[f].count(t)
                if not tf:
                    continue
                idf = max(math.log((n - df[f][t] + 0.5) / (df[f][t] + 0.5)), 1e-6)
                s += weights[f] * idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg[f]))
        if s > 0:
            scores[i] = s
    return sorted(scores, key=lambda i: (-scores[i], i))


def vector_ranking(conn, query: str, embedder: "Embedder", pool: int) -> list:
    """Chunk ids by cosine similarity to the query's vector, among chunks embedded with the same model."""
    qv = embedder.embed([query])[0]
    sims = []
    for r in conn.execute("SELECT v.chunk_id, v.vec FROM vectors v JOIN pages p ON p.id = v.page_id "
                          "WHERE p.deleted = 0 AND v.model = ?", (embedder.model,)):
        sims.append((cosine(qv, unpack_vector(r["vec"])), r["chunk_id"]))
    sims.sort(key=lambda x: (-x[0], x[1]))
    return [cid for s, cid in sims[:pool] if s > 0]


def search(conn, query: str, cfg: dict, budget: str = "conservative", limit: int = 10,
           embedder: Optional["Embedder"] = None) -> dict:
    terms = list(dict.fromkeys(tokens(query)))
    if not terms:
        return {"query": query, "results": [], "tokens_used": 0}
    fts = bool(source_row(conn)["fts"])
    w = cfg["weights"]
    pool = cfg["pool"]
    if fts:
        crows = conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts, ?, ?, ?) "
                             "LIMIT ?", (fts_query(terms), w["title"], w["symbol"], w["body"], pool)).fetchall()
        chunk_ids = [r[0] for r in crows]
        prows = conn.execute("SELECT rowid FROM pages_fts WHERE pages_fts MATCH ? ORDER BY bm25(pages_fts) LIMIT ?",
                             (fts_query(terms), pool)).fetchall()
        page_arm = [r[0] for r in prows]
    else:
        docs, titles = {}, {}
        for r in conn.execute("SELECT c.id, c.symbol, c.body, p.id AS pid, p.path, p.title FROM chunks c "
                              "JOIN pages p ON p.id = c.page_id WHERE p.deleted = 0"):
            tt = tokens(title_text(r["path"], r["title"]))
            docs[r["id"]] = [tt, tokens(r["symbol"] or ""), tokens(r["body"])]
            titles[r["pid"]] = [tt]
        chunk_ids = bm25_rank(docs, terms, [w["title"], w["symbol"], w["body"]])[:pool]
        page_arm = bm25_rank(titles, terms, [1.0])[:pool]
    best, arms_used, vector_note = {}, ["keyword", "title"], None

    def pages_of(ids):
        arm = []
        for cid in ids:
            r = conn.execute("SELECT c.*, p.path, p.title, p.mtime_ns FROM chunks c JOIN pages p ON p.id = c.page_id "
                             "WHERE c.id = ? AND p.deleted = 0", (cid,)).fetchone()
            if not r:
                continue
            if all(x["id"] != r["id"] for x in best.get(r["page_id"], [])):
                best.setdefault(r["page_id"], []).append(r)
            if r["page_id"] not in arm:
                arm.append(r["page_id"])
        return arm

    chunk_arm = pages_of(chunk_ids)
    vector_arm = []
    if embedder:
        try:
            vector_arm = pages_of(vector_ranking(conn, query, embedder, pool))
            arms_used.append("vector")
        except Exception as exc:  # the vector arm is optional: keyword search still answers
            vector_note = f"vector arm skipped: {type(exc).__name__}: {exc}"
    k = cfg["rrf_k"]
    fused = {}
    for arm in (chunk_arm, page_arm, vector_arm):
        for rank, pid in enumerate(arm, 1):
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (k + rank)
    if not fused:
        return {"query": query, "results": [], "tokens_used": 0, "fts": fts, "arms": arms_used, "vector": vector_note}
    newest = conn.execute("SELECT MAX(mtime_ns) FROM pages WHERE deleted = 0").fetchone()[0] or 0
    bo = cfg["boosts"]
    scored = []
    for pid, s in fused.items():
        p = conn.execute("SELECT path, title, mtime_ns FROM pages WHERE id = ? AND deleted = 0", (pid,)).fetchone()
        if not p:
            continue
        why = []
        if set(terms) <= set(tokens(title_text(p["path"], p["title"]))):
            s *= bo["title"]
            why.append("title")
        if newest - (p["mtime_ns"] or 0) <= bo["recency_days"] * 86400 * 10**9:
            s *= bo["recency"]
            why.append("recent")
        backlinks = conn.execute("SELECT COUNT(DISTINCT src) FROM links WHERE dst_path = ?", (p["path"],)).fetchone()[0]
        if backlinks:
            s *= 1 + bo["backlink_step"] * min(backlinks, bo["backlink_cap"])
            why.append(f"backlinks {backlinks}")
        scored.append((s, p["path"], pid, why))
    scored.sort(key=lambda x: (-x[0], x[1]))
    allowance, used, results = cfg["budgets"][budget], 0, []
    for s, path, pid, why in scored[:limit]:
        entry = {"path": path, "score": round(s, 6), "boosts": why, "chunks": []}
        for r in best.get(pid, [])[:cfg["chunks_per_page"]]:
            if used + r["tokens"] > allowance:
                entry["truncated"] = True
                break
            used += r["tokens"]
            entry["chunks"].append({"symbol": r["symbol"], "kind": r["kind"], "lines": [r["start_line"], r["end_line"]],
                                    "text": r["body"]})
        results.append(entry)
    return {"query": query, "fts": fts, "budget": budget, "tokens_used": used, "arms": arms_used, "vector": vector_note,
            "results": results}


# ---------------------------------------------------------------- show and doctor

def show(conn, path: str) -> Optional[dict]:
    p = conn.execute("SELECT * FROM pages WHERE path = ?", (path,)).fetchone()
    if not p:
        return None
    chunks = [{"ord": r["ord"], "symbol": r["symbol"], "kind": r["kind"], "lines": [r["start_line"], r["end_line"]],
               "tokens": r["tokens"]} for r in conn.execute("SELECT * FROM chunks WHERE page_id = ? ORDER BY ord",
                                                            (p["id"],))]
    backlinks = [r[0] for r in conn.execute("SELECT DISTINCT q.path FROM links l JOIN pages q ON q.id = l.src "
                                            "WHERE l.dst_path = ? AND q.deleted = 0", (path,))]
    return {"path": p["path"], "title": p["title"], "kind": p["kind"], "sha256": p["sha256"], "deleted": bool(p["deleted"]),
            "renamed_from": p["renamed_from"], "chunks": chunks, "backlinks": backlinks}


# ---------------------------------------------------------------- call graph, context pack, delta

GRAPH_NOTE = "name-based matches from the index at its watermark: leads, graded present only once you read them"


def where(r) -> dict:
    return {"path": r["path"], "symbol": r["symbol"], "kind": r["kind"], "lines": [r["start_line"], r["end_line"]],
            "chunk": r["id"]}


def chunk_row(conn, cid: int):
    return conn.execute("SELECT c.*, p.path FROM chunks c JOIN pages p ON p.id = c.page_id WHERE c.id = ?",
                        (cid,)).fetchone()


def definitions(conn, name: str, path: Optional[str] = None) -> list:
    rows = conn.execute("SELECT s.*, p.path FROM symbols s JOIN pages p ON p.id = s.page_id WHERE p.deleted = 0 "
                        "AND (s.qualname = ? OR s.name = ?) ORDER BY p.path, s.start_line", (name, name)).fetchall()
    exact = [r for r in rows if r["qualname"] == name]
    rows = exact if "." in name and exact else rows
    if path:
        rows = [r for r in rows if r["path"] == path.replace("\\", "/")]
    return [{"path": r["path"], "qualname": r["qualname"], "kind": r["kind"], "lines": [r["start_line"], r["end_line"]],
             "chunk": r["chunk_id"]} for r in rows]


def module_stem(path: str) -> str:
    p = Path(path)
    return p.parent.name if p.stem == "__init__" else p.stem


def fits(kind: str, target: dict) -> bool:
    """obj.m(...) can reach only a method; a bare f(...) only a function, a class or another definition."""
    is_method = target["kind"] == "method"
    return is_method if kind == "attr" else not is_method


def definitions_in(conn, path: str) -> list:
    """Every definition recorded for one file."""
    return [{"qualname": r["qualname"], "kind": r["kind"], "lines": [r["start_line"], r["end_line"]]}
            for r in conn.execute("SELECT s.* FROM symbols s JOIN pages p ON p.id = s.page_id WHERE p.path = ? "
                                  "AND p.deleted = 0 ORDER BY s.start_line", (path,))]


def callers(conn, name: str, path: Optional[str] = None) -> list:
    """Chunks that call the name, each linked to its definitions by "same file", "names the module" or "by name".
    With a path, only the first two are kept."""
    bare = name.split(".")[-1]
    defs = definitions(conn, name, path)
    own = {d["chunk"] for d in defs}
    stems = {module_stem(d["path"]) for d in defs}
    def_paths = {d["path"] for d in defs}
    method = any(d["kind"] == "method" for d in defs)
    rows = conn.execute("SELECT DISTINCT c.*, p.path, r.kind AS ref_kind FROM refs r JOIN chunks c ON c.id = r.chunk_id "
                        "JOIN pages p ON p.id = r.page_id WHERE p.deleted = 0 AND r.name = ? "
                        "ORDER BY p.path, c.start_line", (bare,)).fetchall()
    texts, out, seen = {}, [], set()

    def names_module(page_id) -> bool:
        if page_id not in texts:
            texts[page_id] = "\n".join(b for (b,) in conn.execute("SELECT body FROM chunks WHERE page_id = ?", (page_id,)))
        return any(re.search(rf"\b{re.escape(s)}\b", texts[page_id]) for s in stems)

    for r in rows:
        if r["id"] in seen:
            continue
        same = r["path"] in def_paths
        if defs and not any(fits(r["ref_kind"], d) for d in defs):
            # obj.f(...) still reaches a function when obj is its module: module.f(...)
            if not (r["ref_kind"] == "attr" and not method and (same or names_module(r["page_id"]))):
                continue
        linked = "same file" if same else "names the module" if names_module(r["page_id"]) else "by name"
        if path and linked == "by name":
            continue
        seen.add(r["id"])
        out.append(dict(where(r), self=r["id"] in own, linked=linked))
    return out


def callees(conn, name: str, path: Optional[str] = None) -> list:
    """What each definition calls: obj.m(...) resolves to methods only, f(...) to the rest; a definition in the same
    file wins, otherwise every definition of that name."""
    out = []
    for d in definitions(conn, name, path):
        calls, unresolved = [], []
        for called, kind in conn.execute("SELECT DISTINCT name, kind FROM refs WHERE chunk_id = ? ORDER BY name, kind",
                                         (d["chunk"],)):
            targets = [t for t in definitions(conn, called) if fits(kind, t)]
            same = [t for t in targets if t["path"] == d["path"]]
            if targets:
                calls.append({"name": called, "resolved": "same file" if same else "by name",
                              "definitions": same or targets})
            else:
                unresolved.append(called)
        out.append({"from": d, "calls": calls, "unresolved": unresolved})
    return out


def references(conn, name: str, limit: int = 50, path: Optional[str] = None) -> list:
    """Chunks that mention the identifier as a whole word, other than its own definitions."""
    bare = name.split(".")[-1]
    word = re.compile(r"(?<![\w$])" + re.escape(bare) + r"(?![\w$])")
    own = {d["chunk"] for d in definitions(conn, name, path)}
    if source_row(conn)["fts"] and tokens(bare):
        ids = [r[0] for r in conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?",
                                          ('body:"' + " ".join(tokens(bare)) + '"',))]
    else:
        ids = [r[0] for r in conn.execute("SELECT id FROM chunks")]
    out = []
    for cid in sorted(ids):
        r = conn.execute("SELECT c.*, p.path FROM chunks c JOIN pages p ON p.id = c.page_id WHERE c.id = ? "
                         "AND p.deleted = 0", (cid,)).fetchone()
        if not r or r["id"] in own:
            continue
        for k, line in enumerate(r["body"].split("\n")):
            if word.search(line):
                out.append(dict(where(r), line=r["start_line"] + k, text=line.strip()))
                break
    out.sort(key=lambda x: (x["path"], x["line"]))
    return out[:limit]


def context_pack(conn, name: str, cfg: dict, budget: str = "conservative", path: Optional[str] = None) -> dict:
    """The definition first, then what it calls, then its callers, until the token budget is spent."""
    allowance = cfg["budgets"][budget]
    order, seen = [], set()
    for d in definitions(conn, name, path):
        order.append(("definition", d["chunk"]))
    for c in callees(conn, name, path):
        for call in c["calls"]:
            for t in call["definitions"]:
                order.append(("callee", t["chunk"]))
    for c in callers(conn, name, path):
        if not c["self"]:
            order.append(("caller", c["chunk"]))
    used, pack, left_out = 0, [], []
    for role, cid in order:
        if cid in seen:
            continue
        seen.add(cid)
        r = chunk_row(conn, cid)
        entry = dict(where(r), role=role)
        if used + r["tokens"] > allowance:
            left_out.append(dict(entry, tokens=r["tokens"]))
            continue
        used += r["tokens"]
        pack.append(dict(entry, text=r["body"]))
    return {"symbol": name, "budget": budget, "allowance": allowance, "tokens_used": used, "pack": pack,
            "left_out": left_out, "note": GRAPH_NOTE}


def delta(conn, since: str) -> Optional[dict]:
    """Changes recorded after the last advanced run at `since` (a commit, or a prefix of seven or more characters)."""
    if len(since) < 7:
        return None
    base = conn.execute("SELECT MAX(id) FROM runs WHERE advanced = 1 AND head LIKE ?", (since + "%",)).fetchone()[0]
    if not base:
        return None
    final = {}
    events = conn.execute("SELECT c.path, c.change, c.old_path FROM changes c WHERE c.run_id > ? AND "
                          "c.change != 'rechunked' ORDER BY c.run_id, c.rowid", (base,)).fetchall()
    for e in events:
        path, change, prev = e["path"], e["change"], final.get(e["path"])
        if change == "renamed":
            origin = final.pop(e["old_path"], None)
            if origin and origin["change"] == "added":
                final[path] = {"change": "added"}
            else:
                final[path] = {"change": "renamed", "from": (origin or {}).get("from", e["old_path"]),
                               "modified": bool(origin and origin.get("modified"))}
        elif change == "deleted":
            if prev and prev["change"] == "added":
                final.pop(path)
            else:
                final[path] = {"change": "deleted"}
        elif change == "modified":
            if prev and prev["change"] in ("added", "renamed"):
                prev["modified"] = prev["change"] == "renamed" or prev.get("modified", False)
            else:
                final[path] = {"change": "modified"}
        else:
            final[path] = {"change": "modified" if prev and prev["change"] == "deleted" else "added"}
    latest = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return {"since": since, "until": source_row(conn)["last_commit"], "latest_run_advanced": bool(latest["advanced"]),
            "events": len(events), "changes": [dict({"path": p}, **v) for p, v in sorted(final.items())]}


def ping(repo: Path, db: Path, cfg: dict) -> dict:
    """The capability round-trip: index a throwaway page in the index (never in the repository), find it by search
    within three tries, delete it and confirm it is gone."""
    steps = {"indexed": False, "found": False, "tries": 0, "deleted": False, "reason": None}
    try:
        enforce(repo, "ping")
    except PolicyRefused as exc:
        return dict(steps, passed=False, reason=str(exc))
    if not db.exists():
        return dict(steps, passed=False, reason=f"no index at {db}: run build")
    conn = connect(db)
    token = "westackping" + hashlib.sha256(f"{os.getpid()}-{time.time_ns()}".encode()).hexdigest()[:12]
    path = f".westack-ping/{token}.md"
    text = f"# {token}\n\n{token}\n"
    page_id = None
    try:
        fts = bool(source_row(conn)["fts"])
        st = type("Stat", (), {"st_size": len(text), "st_mtime_ns": time.time_ns()})()
        page_id = store_page(conn, path, text, hashlib.sha256(text.encode()).hexdigest(), st, cfg, fts)
        conn.commit()
        steps["indexed"] = True
        for attempt in range(1, 4):
            steps["tries"] = attempt
            hits = [r["path"] for r in search(conn, token, cfg, limit=3)["results"]]
            if hits[:1] == [path]:
                steps["found"] = True
                break
            time.sleep(0.2)
    except Exception as exc:
        steps["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            row = conn.execute("SELECT id FROM pages WHERE path = ?", (path,)).fetchone()
            if row:
                clear_page(conn, row["id"], bool(source_row(conn)["fts"]))
                conn.execute("DELETE FROM pages WHERE id = ?", (row["id"],))
                conn.commit()
            steps["deleted"] = (not conn.execute("SELECT 1 FROM pages WHERE path = ?", (path,)).fetchone()
                                and not search(conn, token, cfg, limit=3)["results"])
        finally:
            conn.close()
    passed = steps["indexed"] and steps["found"] and steps["deleted"]
    if not passed and not steps["reason"]:
        steps["reason"] = "the round-trip did not complete: " + ", ".join(k for k in ("indexed", "found", "deleted")
                                                                           if not steps[k])
    return dict(steps, passed=passed)


def guidance_block() -> str:
    return f"{GUIDE_START}\n{GUIDE_TEXT}\n{GUIDE_END}"


def guidance(repo: Path, db: Path, cfg: dict, file: str, write: bool = False) -> dict:
    """Keep the search-guidance block in AGENTS.md or CLAUDE.md true: present only while the ping passes."""
    if Path(file).name not in ("AGENTS.md", "CLAUDE.md") or Path(file).is_absolute() or ".." in Path(file).parts:
        raise UsageError("the guidance block goes only in the repository's AGENTS.md or CLAUDE.md")
    target = repo / file
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    m = re.search(re.escape(GUIDE_START) + r".*?" + re.escape(GUIDE_END) + r"\n?", text, re.S)
    result = ping(repo, db, cfg)
    if result["passed"]:
        if m and m.group(0).rstrip("\n") == guidance_block():
            action, new = "unchanged", text
        elif m:
            action, new = "update", text[:m.start()] + guidance_block() + "\n" + text[m.end():]
        else:
            action, new = "write", (text.rstrip("\n") + "\n\n" if text.strip() else "") + guidance_block() + "\n"
    elif m:
        before, after = text[:m.start()].rstrip("\n"), text[m.end():].lstrip("\n")
        joint = "\n\n" if before and after else "\n" if before else ""
        action, new = "remove", before + joint + after
    else:
        action, new = "none", text
    if write and new != text:
        target.write_text(new, encoding="utf-8")
    return {"file": file, "ping": result, "action": action, "written": bool(write and new != text),
            "note": None if write else "dry run: pass --write, under the user's grant to edit instruction files"}


def doctor(repo: Path, db: Path, cfg: dict) -> dict:
    checks = []

    def add(level, name, detail):
        checks.append({"level": level, "check": name, "detail": detail})

    t = tier_for(repo)
    if t["quarantined"]:
        add("WARN", "policy", f"moved-aside policy files: {', '.join(t['quarantined'])}")
    add("WARN" if t["tier"] in ("deny", "read-only") else "OK", "tier", f"{t['key']}: {t['tier']} ({t['reason']})")

    if not db.exists():
        add("ERR", "index", f"no index at {db}: run build")
        return {"verdict": "ERR", "db": str(db), "checks": checks}
    try:
        conn = connect(db)
        src = source_row(conn)
        version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.Error as exc:
        add("ERR", "database", f"cannot read: {exc}")
        return {"verdict": "ERR", "db": str(db), "checks": checks}
    if not version or int(version[0]) != SCHEMA_VERSION:
        add("ERR", "schema", f"schema {version[0] if version else None}, expected {SCHEMA_VERSION}: run update "
                             "(it migrates and re-walks) or build")
        conn.close()
        return {"verdict": "ERR", "db": str(db), "checks": checks}
    if src["fts"] and not fts5_available():
        add("ERR", "fts5", "built with FTS5, which this Python lacks: run build")
    else:
        add("OK", "search", "FTS5" if src["fts"] else "pure-Python BM25 (no FTS5 in this Python)")
    if src["chunker_version"] != CHUNKER_VERSION:
        add("WARN", "chunker", f"chunker {src['chunker_version']}, current {CHUNKER_VERSION}: the next update re-walks")
    head = head_commit(repo)
    if head and src["last_commit"] != head:
        add("WARN", "watermark", f"index at {src['last_commit']}, HEAD at {head}: run update")
    elif head:
        add("OK", "watermark", f"at HEAD {head[:12]}")
    open_failures = conn.execute("SELECT path, reason FROM failures WHERE acknowledged = 0").fetchall()
    if open_failures:
        add("WARN", "failures", [f"{r['path']}: {r['reason']}" for r in open_failures])
    lock = Path(str(db) + ".lock")
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        add("WARN", "lock", f"held for {int(age)} s" + (" (stale: the next run takes it over)"
                                                         if age > cfg["lock_stale_seconds"] else ""))
    counts = conn.execute("SELECT (SELECT COUNT(*) FROM pages WHERE deleted = 0), (SELECT COUNT(*) FROM chunks), "
                          "(SELECT COUNT(*) FROM skipped), (SELECT COUNT(*) FROM symbols)").fetchone()
    add("OK", "contents", {"pages": counts[0], "chunks": counts[1], "skipped": counts[2], "symbols": counts[3]})
    state = read_state(db)
    if state and state.get("status") != "OK":
        add("WARN", "last run", f"{state.get('mode')} finished {state.get('finished')} with {state.get('status')}")
    conn.close()
    levels = {c["level"] for c in checks}
    verdict = "ERR" if "ERR" in levels else "WARN" if "WARN" in levels else "OK"
    return {"verdict": verdict, "db": str(db), "checks": checks}


# ---------------------------------------------------------------- command line

def main(argv: Optional[list] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="codeindex.py", description="westack-onboard repository index")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("build", "update", "search", "show", "doctor", "def", "refs", "callers", "callees", "context", "delta",
                 "policy", "guidance"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--db")
        if name == "policy":
            p.add_argument("--set", dest="set_tier", choices=TIERS + ("unset",))
        if name == "guidance":
            p.add_argument("--file", default="AGENTS.md")
            p.add_argument("--write", action="store_true")
        if name in ("def", "refs", "callers", "callees", "context"):
            p.add_argument("name")
            p.add_argument("--in", dest="within", help="only the definition in this repository path")
        if name == "context":
            p.add_argument("--budget", choices=("conservative", "balanced"), default="conservative")
        if name == "delta":
            p.add_argument("--since", required=True)
        if name in ("build", "update", "search"):
            p.add_argument("--embed", metavar="URL", help="opt-in: a local embedding endpoint for the vector arm")
            p.add_argument("--embed-model", default="")
            p.add_argument("--allow-remote-embed", action="store_true",
                           help="the user's grant to send code to a non-localhost endpoint")
        if name in ("build", "update"):
            p.add_argument("--tree-sitter", action="store_true", help="opt-in: probe for tree-sitter")
            p.add_argument("--files")
        if name == "update":
            p.add_argument("--skip-failed", action="store_true")
        if name == "search":
            p.add_argument("--budget", choices=("conservative", "balanced"), default="conservative")
            p.add_argument("--limit", type=int, default=10)
            p.add_argument("query", nargs="+")
        if name == "show":
            p.add_argument("path")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_OK if exc.code == 0 else EXIT_USAGE
    try:
        cfg = config()
        repo = Path(args.repo)
        if not repo.is_dir():
            raise UsageError(f"not a folder: {repo}")
        db = resolve_db(repo, args.db)
        if args.cmd == "policy":
            print(json.dumps(set_tier(repo, args.set_tier) if args.set_tier else tier_for(repo), indent=2))
            return EXIT_OK
        if args.cmd == "guidance":
            result = guidance(repo, db, cfg, args.file, args.write)
            print(json.dumps(result, indent=2))
            return EXIT_OK if result["ping"]["passed"] else EXIT_FAIL
        embedder = (Embedder(args.embed, args.embed_model, args.allow_remote_embed)
                    if getattr(args, "embed", None) else None)
        if args.cmd in ("build", "update"):
            code, state = sync(repo, db, args.cmd, args.files, getattr(args, "skip_failed", False), cfg, embedder,
                               args.tree_sitter)
            print(json.dumps(state, indent=2))
            return code
        if args.cmd == "doctor":
            result = doctor(repo, db, cfg)
            print(json.dumps(result, indent=2))
            return EXIT_FAIL if result["verdict"] == "ERR" else EXIT_OK
        enforce(repo, "read")
        try:
            conn = connect(db)
        except FileNotFoundError:
            print(f"codeindex.py: no index at {db}: run build first", file=sys.stderr)
            return EXIT_NO_INDEX
        try:
            return query(conn, args, cfg, embedder)
        finally:
            conn.close()
    except PolicyRefused as exc:
        print(f"codeindex.py: refused by policy: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Locked as exc:
        print(f"codeindex.py: {exc}", file=sys.stderr)
        return EXIT_LOCKED
    except UsageError as exc:
        print(f"codeindex.py: {exc}", file=sys.stderr)
        return EXIT_USAGE


def query(conn, args, cfg, embedder=None) -> int:
    """The read commands, on an open index."""
    if args.cmd == "search":
        print(json.dumps(search(conn, " ".join(args.query), cfg, args.budget, args.limit, embedder), indent=2))
        return EXIT_OK
    graph = {"def": lambda: {"definitions": definitions(conn, args.name, args.within)},
             "refs": lambda: {"references": references(conn, args.name, path=args.within)},
             "callers": lambda: {"callers": callers(conn, args.name, args.within)},
             "callees": lambda: {"callees": callees(conn, args.name, args.within)},
             "context": lambda: context_pack(conn, args.name, cfg, args.budget, args.within)}
    if args.cmd in graph:
        result = graph[args.cmd]()
        result.setdefault("note", GRAPH_NOTE)
        result["watermark"] = source_row(conn)["last_commit"]
        print(json.dumps(dict({"name": args.name}, **result), indent=2))
        return EXIT_OK
    if args.cmd == "delta":
        result = delta(conn, args.since)
        if result is None:
            print(f"codeindex.py: no advanced run at {args.since} in this index's log (a build starts the log "
                  "afresh; give seven or more characters)", file=sys.stderr)
            return EXIT_UNSURE
        print(json.dumps(result, indent=2))
        return EXIT_OK
    result = show(conn, args.path.replace("\\", "/"))
    if result is None:
        print(f"codeindex.py: {args.path} is not in the index", file=sys.stderr)
        return EXIT_NO_INDEX
    print(json.dumps(result, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
