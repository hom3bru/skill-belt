"""Tests for westack-onboard's opt-in extensions: a local embedding endpoint (a fake one on 127.0.0.1), the tree-sitter
probe, index export and import through a local bare git remote with the secret scan, and the MCP stdio server.
With every extension off, test_codeindex.py and test_graph.py run unchanged. Each extension has a broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-onboard/tests
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from test_codeindex import GIT, HERE, Fixture, broken, ci

SCRIPTS = HERE.parent / "scripts"
SYNONYMS = {"pause": "backoff", "wait": "backoff", "sleep": "backoff"}
DIM = 16


def fake_vector(text):
    v = [0.0] * DIM
    for word in ci.tokens(text):
        v[zlib.crc32(SYNONYMS.get(word, word).encode()) % DIM] += 1.0
    return v


class FakeEmbeddings(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = json.dumps({"embeddings": [fake_vector(t) for t in body["input"]]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


def load_script(name, path=None):
    spec = importlib.util.spec_from_file_location(f"westack_{name}_under_test", path or SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


isync = load_script("indexsync")


class EmbeddingTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = HTTPServer(("127.0.0.1", 0), FakeEmbeddings)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/embed"

    def vsearch(self, query, embedder, module=None):
        m = module or ci
        conn = m.connect(self.db)
        try:
            return m.search(conn, query, m.config(), embedder=embedder)
        finally:
            conn.close()

    def test_the_vector_arm_finds_what_keywords_miss(self):
        e = ci.Embedder(self.url, "fake")
        code, state = self.sync(embedder=e)
        conn = ci.connect(self.db)
        vectors = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        conn.close()
        self.assertEqual((code, state["embeddings"]["embedded"], vectors), (0, chunks, chunks))
        self.assertEqual(self.search("pause"), [], "no keyword matches the synonym")
        found = self.vsearch("pause", e)
        self.assertIn("vector", found["arms"])
        self.assertIn("pkg/retry.py", [r["path"] for r in found["results"]][:2])

    def test_a_down_endpoint_leaves_keyword_search_whole(self):
        e = ci.Embedder("http://127.0.0.1:9/embed", "fake", timeout=2)
        code, state = self.sync(embedder=e)
        self.assertEqual((code, state["embeddings"]["embedded"]), (0, 0))
        self.assertTrue(state["embeddings"]["reason"])
        result = self.vsearch("exponential backoff", e)
        self.assertEqual(result["results"][0]["path"], "pkg/retry.py")
        self.assertIn("vector arm skipped", result["vector"])

    def test_a_remote_endpoint_needs_the_grant(self):
        with self.assertRaises(ci.UsageError):
            ci.Embedder("http://embeddings.example.com/v1/embeddings")
        with self.assertRaises(ci.UsageError):
            ci.Embedder("ftp://127.0.0.1/embed")
        self.assertEqual(ci.Embedder("http://embeddings.example.com/v1/embeddings", allow_remote=True).url,
                         "http://embeddings.example.com/v1/embeddings")

    def test_the_control_without_the_host_check_sends_anywhere(self):
        b = broken("if parsed.hostname.lower() not in LOCAL_HOSTS and not allow_remote:", "if False:",
                   "codeindex_any_host")
        self.assertEqual(b.Embedder("http://embeddings.example.com/x").url, "http://embeddings.example.com/x",
                         "the broken copy accepts a remote endpoint without the grant")

    def test_the_control_without_the_vector_arm_in_the_fusion_finds_nothing(self):
        b = broken("for arm in (chunk_arm, page_arm, vector_arm):", "for arm in (chunk_arm, page_arm):",
                   "codeindex_no_vector_fusion")
        e = b.Embedder(self.url, "fake")
        b.sync(self.repo, self.db, "build", embedder=e)
        self.assertEqual(self.vsearch("pause", e, module=b)["results"], [], "the broken copy drops the vector arm")


TS_FILES = {
    "web/store.js": ("export class WidgetStore {\n  constructor() { this.items = []; }\n"
                     "  add(item) { this.items.push(item); return this; }\n}\n\n"
                     "export const mount = (el, store) => {\n  store.add(el);\n  return renderWidget(el);\n};\n\n"
                     "export function renderWidget(el) {\n  return el;\n}\n"),
    "web/shapes.ts": ("export interface Shape { area(): number; }\n\n"
                      "export function total(shapes: Shape[]): number {\n"
                      "  return shapes.reduce((a, s) => a + s.area(), 0);\n}\n"),
    "cmd/main.go": ("package main\n\ntype Server struct{}\n\nfunc (s *Server) Start() error {\n\treturn s.listen()\n}\n\n"
                    "func (s *Server) listen() error {\n\treturn nil\n}\n\nfunc main() {\n\ts := &Server{}\n\ts.Start()\n}\n"),
    "src/store.rs": ("struct Store { n: u32 }\n\nimpl Store {\n    fn new() -> Self { Store { n: 0 } }\n"
                     "    fn bump(&mut self) { self.n += 1; }\n}\n\nfn run() {\n    let mut s = Store::new();\n"
                     "    s.bump();\n}\n"),
}
HAVE_GRAMMARS = all(ci.ts_parser(e) for e in (".js", ".ts", ".go", ".rs"))


class TreeSitterTests(Fixture):
    def absent(self):
        return [mock.patch.dict(sys.modules, {"tree_sitter": None}), mock.patch.dict(ci._PARSERS, clear=True)]

    def test_absent_tree_sitter_is_skipped_cleanly(self):
        plain = self.sync()[1]
        patches = self.absent()
        for p in patches:
            p.start()
        try:
            probed = self.sync(tree_sitter=True)[1]
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(probed["tree_sitter"], "not installed: definition patterns used")
        self.assertEqual((probed["chunks"], probed["symbols"]), (plain["chunks"], plain["symbols"]))
        self.assertIsNone(plain["tree_sitter"])

    def test_the_control_an_unguarded_import_crashes(self):
        b = broken('    try:\n        import tree_sitter  # noqa: F401\n    except ImportError:\n'
                   '        return "not installed: definition patterns used"\n',
                   "    import tree_sitter  # noqa: F401\n", "codeindex_unguarded_tree_sitter")
        with mock.patch.dict(sys.modules, {"tree_sitter": None}):
            with self.assertRaises(ImportError):
                b.sync(self.repo, self.db, "build", tree_sitter=True)

    @unittest.skipUnless(HAVE_GRAMMARS, "tree-sitter and its JavaScript, TypeScript, Go and Rust grammars are needed")
    def test_tree_sitter_finds_what_patterns_miss(self):
        for path, text in TS_FILES.items():
            self.write(path, text)
        self.commit("four languages")
        plain = self.sync()[1]
        conn = ci.connect(self.db)
        (mount,) = ci.callees(conn, "mount")
        conn.close()
        self.assertIn("add", mount["unresolved"], "definition patterns do not see class methods")
        state = self.sync("update", tree_sitter=True)[1]
        self.assertTrue(state["rewalk"], "switching tree-sitter on re-walks")
        self.assertTrue(state["tree_sitter"].startswith("used for "))
        self.assertGreater(state["symbols"], plain["symbols"])
        conn = ci.connect(self.db)
        try:
            def defs(path):
                return sorted(d["qualname"] for d in ci.definitions_in(conn, path))
            self.assertEqual(defs("web/store.js"), ["WidgetStore", "WidgetStore.add", "WidgetStore.constructor",
                                                     "mount", "renderWidget"])
            self.assertEqual(defs("web/shapes.ts"), ["Shape", "total"])
            self.assertEqual(defs("cmd/main.go"), ["Server", "Server.Start", "Server.listen", "main"])
            self.assertEqual(defs("src/store.rs"), ["Store", "Store.bump", "Store.new", "run"])
            (mount,) = ci.callees(conn, "mount")
            self.assertEqual(sorted((c["name"], c["definitions"][0]["qualname"]) for c in mount["calls"]),
                             [("add", "WidgetStore.add"), ("renderWidget", "renderWidget")])
            (start,) = ci.callees(conn, "Server.Start")
            self.assertEqual([c["definitions"][0]["qualname"] for c in start["calls"]], ["Server.listen"])
            self.assertEqual([(c["path"], c["symbol"]) for c in ci.callers(conn, "Server.Start")], [("cmd/main.go", "main")])
            (run,) = ci.callees(conn, "run")
            self.assertEqual(sorted(c["definitions"][0]["qualname"] for c in run["calls"]), ["Store.bump", "Store.new"])
        finally:
            conn.close()

    @unittest.skipUnless(HAVE_GRAMMARS, "tree-sitter and its grammars are needed")
    def test_the_control_a_copy_that_ignores_the_flag_misses_the_methods(self):
        b = broken("        if ts and ext in TS_GRAMMARS:\n", "        if False:\n", "codeindex_ignores_tree_sitter")
        for path, text in TS_FILES.items():
            self.write(path, text)
        self.commit("four languages")
        b.sync(self.repo, self.db, "build", tree_sitter=True)
        conn = b.connect(self.db)
        try:
            self.assertEqual(b.definitions(conn, "WidgetStore.add"), [], "the broken copy misses the method")
        finally:
            conn.close()


@unittest.skipUnless(GIT, "git is not on PATH")
class ShareTests(Fixture):
    def setUp(self):
        super().setUp()
        self.sync()
        self.share = Path(self.tmp.name, "share")
        self.remote = Path(self.tmp.name, "remote.git")
        subprocess.run([GIT, "init", "-q", "--bare", str(self.remote)], check=True, capture_output=True)

    def run_git(self, cwd, *args):
        return subprocess.run([GIT, "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout

    def test_export_push_pull_import(self):
        subprocess.run([GIT, "clone", "-q", str(self.remote), str(self.share)], check=True, capture_output=True)
        for k, v in (("user.email", "t@example.test"), ("user.name", "Test"), ("core.autocrlf", "false")):
            self.run_git(self.share, "config", k, v)
        code, result = isync.export(ci, self.repo, self.db, self.share / "index")
        self.assertEqual((code, result["pages"]), (0, 6))
        self.run_git(self.share, "add", "-A")
        self.run_git(self.share, "commit", "-q", "-m", "index")
        self.run_git(self.share, "push", "-q", "origin", "HEAD")
        other = Path(self.tmp.name, "other")
        subprocess.run([GIT, "clone", "-q", str(self.remote), str(other)], check=True, capture_output=True)
        fresh = Path(self.tmp.name, "cache", "fresh.sqlite")
        code, result = isync.import_(ci, self.repo, fresh, other / "index")
        self.assertEqual((code, len(result["added"]), result["conflicts_kept_local"]), (0, 6, []))
        self.assertEqual(self.search("exponential backoff", fresh)[0], "pkg/retry.py")
        self.write("pkg/retry.py", FILES_RETRY_CHANGED)
        self.commit("local change")
        ci.sync(self.repo, fresh, "update")
        code, result = isync.import_(ci, self.repo, fresh, other / "index")
        self.assertEqual(result["conflicts_kept_local"], ["pkg/retry.py"], "local wins on a conflict")

    def test_a_planted_key_blocks_the_export(self):
        self.write("pkg/settings.py", "AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n")
        self.commit("oops")
        self.sync("update")
        out = Path(self.tmp.name, "out")
        code, result = isync.export(ci, self.repo, self.db, out)
        self.assertEqual((code, result["status"]), (1, "refused"))
        self.assertEqual(result["findings"], [{"line": 1, "kind": "aws access key", "path": "pkg/settings.py"}])
        self.assertFalse(out.exists(), "nothing was written")
        code, result = isync.export(ci, self.repo, self.db, out, exclude=["pkg/settings.py"])
        self.assertEqual(code, 0)
        self.assertNotIn("AKIA", (out / "chunks.jsonl").read_text(encoding="utf-8"))

    def test_an_export_for_another_repository_is_refused(self):
        out = Path(self.tmp.name, "out")
        isync.export(ci, self.repo, self.db, out)
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        meta["repo_key"] = "github.com/someone/else"
        (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(ci.UsageError):
            isync.import_(ci, self.repo, Path(self.tmp.name, "cache", "x.sqlite"), out)

    def test_the_control_without_the_scan_check_ships_the_key(self):
        source = (SCRIPTS / "indexsync.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("    if findings:\n"), 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "indexsync_no_scan.py")
            path.write_text(source.replace("    if findings:\n", "    if False:\n"), encoding="utf-8")
            b = load_script("indexsync_no_scan", path)
        self.write("pkg/settings.py", "AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n")
        self.commit("oops")
        self.sync("update")
        out = Path(self.tmp.name, "out")
        b.export(ci, self.repo, self.db, out)
        self.assertIn("AKIAABCDEFGHIJKLMNOP", (out / "chunks.jsonl").read_text(encoding="utf-8"),
                      "the broken copy ships the key")


FILES_RETRY_CHANGED = '"""Retry helpers, changed."""\n\n\ndef retry(times=3):\n    return times\n'


class McpTests(Fixture):
    def session(self, *messages):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / "mcpserver.py"), "--repo", str(self.repo),
                               "--db", str(self.db)], input="".join(json.dumps(m) + "\n" for m in messages),
                              capture_output=True, text=True, encoding="utf-8", timeout=60, env=os.environ.copy())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]

    def test_a_stdio_session_lists_and_calls_the_read_verbs(self):
        self.sync()
        replies = self.session(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18",
                                                                           "capabilities": {}, "clientInfo": {"name": "t"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search",
                                                                          "arguments": {"query": "exponential backoff"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "callers", "arguments": {"name": "retry"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "build", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
        self.assertEqual([r["id"] for r in replies], [1, 2, 3, 4, 5, 6], "the notification gets no reply")
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "westack-onboard-index")
        self.assertEqual([t["name"] for t in replies[1]["result"]["tools"]],
                         ["search", "show", "def", "refs", "callers", "callees", "context", "delta", "doctor"])
        found = json.loads(replies[2]["result"]["content"][0]["text"])
        self.assertEqual(found["results"][0]["path"], "pkg/retry.py")
        callers = json.loads(replies[3]["result"]["content"][0]["text"])["callers"]
        self.assertIn("pkg/client.py", [c["path"] for c in callers])
        self.assertTrue(replies[4]["result"]["isError"], "no write verbs")
        self.assertEqual(replies[5]["error"]["code"], -32601)

    def test_the_server_obeys_the_tier(self):
        self.sync()
        ci.set_tier(self.repo, "deny")
        (reply,) = self.session({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                 "params": {"name": "search", "arguments": {"query": "backoff"}}})
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("PolicyRefused", reply["result"]["content"][0]["text"])

    def test_the_control_a_server_without_the_tier_check_answers_a_denied_repository(self):
        source = (SCRIPTS / "mcpserver.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('        ci.enforce(self.repo, "read")\n'), 1)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("codeindex.py",):
                Path(tmp, name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
            Path(tmp, "mcpserver.py").write_text(source.replace('        ci.enforce(self.repo, "read")\n', ""),
                                                 encoding="utf-8")
            refs = Path(tmp).parent / "references"
            b = load_script("mcpserver_no_tier", Path(tmp, "mcpserver.py"))
            b.HERE = SCRIPTS
            self.sync()
            ci.set_tier(self.repo, "deny")
            server = b.Server(self.repo, str(self.db))
            reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "search", "arguments": {"query": "backoff"}}})
        self.assertFalse(reply["result"]["isError"], "the broken server answers for a denied repository")


if __name__ == "__main__":
    unittest.main()
