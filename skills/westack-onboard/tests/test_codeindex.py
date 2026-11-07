"""Tests for westack-onboard's scripts/codeindex.py on temporary git repositories. Local files only; the tests (not
the helper) run git to build the fixtures.

Run from the repo root:  python -B -m unittest discover -s skills/westack-onboard/tests

Each sync mechanism has an in-suite broken-copy control: a copy of the script with that rule disconnected, which
must miss what the real script does.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "codeindex.py"
GIT = shutil.which("git")


def load(path=SCRIPT, name="westack_codeindex_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = load()


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        module = load(path, name)
    module.CONFIG = ci.CONFIG
    return module


FILES = {
    "README.md": "# Example service\n\nA small service. See [the guide](docs/guide.md).\n",
    "docs/guide.md": "# Guide\n\nIntro text.\n\n## Retries\n\nCalls use [retry](../pkg/retry.py) with exponential backoff.\n\n"
                     "```python\n# not a heading\n```\n\n## Deploying\n\nShip it carefully.\n",
    "pkg/__init__.py": "",
    "pkg/retry.py": '"""Retry helpers."""\nimport time\n\n\ndef retry(times=3):\n    """Retry a call on failure."""\n'
                    "    def wrap(fn):\n        return fn\n    return wrap\n\n\nclass Backoff:\n"
                    '    """Exponential backoff schedule."""\n\n    def __init__(self, base=0.1):\n        self.base = base\n\n'
                    "    def delay(self, attempt):\n        return self.base * 2 ** attempt\n",
    "pkg/client.py": "from pkg.retry import retry\n\n\n@retry(times=5)\ndef fetch(url):\n    return url\n",
    "web/app.js": "export function renderWidget(el) {\n  return el;\n}\n\nexport class WidgetStore {\n  constructor() {}\n}\n",
}


@unittest.skipUnless(GIT, "git is not on PATH")
class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name, "repo")
        self.repo.mkdir()
        self.db = Path(self.tmp.name, "cache", "index.sqlite")
        self.config = Path(self.tmp.name, "config")
        env = mock.patch.dict(os.environ, {"WESTACK_CONFIG_DIR": str(self.config)})
        env.start()
        self.addCleanup(env.stop)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.test")
        self.git("config", "user.name", "Test")
        self.git("config", "core.autocrlf", "false")
        for path, text in FILES.items():
            self.write(path, text)
        self.commit("first")

    def git(self, *args):
        return subprocess.run([GIT, "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def write(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD").strip()

    def sync(self, mode="build", module=None, **kw):
        return (module or ci).sync(self.repo, self.db, mode, **kw)

    def search(self, query, db=None, module=None):
        m = module or ci
        conn = m.connect(db or self.db)
        try:
            return [r["path"] for r in m.search(conn, query, m.config())["results"]]
        finally:
            conn.close()

    def page(self, path):
        conn = ci.connect(self.db)
        try:
            return conn.execute("SELECT * FROM pages WHERE path = ?", (path,)).fetchone()
        finally:
            conn.close()


class GitReadTests(Fixture):
    def test_the_git_index_matches_ls_files(self):
        listed = sorted(l for l in self.git("ls-files").splitlines() if l)
        self.assertEqual(ci.read_git_index(self.repo), listed)

    def test_the_control_an_index_reader_without_padding_misreads_the_file_list(self):
        b = broken("pos += (header + (end - start) + 8) & ~7", "pos += header + (end - start) + 1", "codeindex_no_pad")
        listed = sorted(l for l in self.git("ls-files").splitlines() if l)
        try:
            got = b.read_git_index(self.repo)
        except Exception:
            got = None
        self.assertNotEqual(got, listed, "the broken reader misses what the real one reads")

    def test_head_and_remote_are_read_from_files(self):
        self.assertEqual(ci.head_commit(self.repo), self.git("rev-parse", "HEAD").strip())
        self.git("remote", "add", "origin", "git@GitHub.com:Org/Repo.git")
        self.assertEqual(ci.normalise_remote(ci.remote_url(self.repo)), "github.com/org/repo")


class SyncTests(Fixture):
    def test_first_build(self):
        code, state = self.sync()
        self.assertEqual((code, state["status"], state["pages"], state["watermark_advanced"]), (0, "OK", 6, True))
        self.assertEqual(state["watermark"], self.git("rev-parse", "HEAD").strip())
        conn = ci.connect(self.db)
        shown = ci.show(conn, "pkg/retry.py")
        conn.close()
        self.assertEqual([c["symbol"] for c in shown["chunks"]], [None, "retry", "Backoff", "Backoff.__init__", "Backoff.delay"])
        self.assertEqual(self.search("exponential backoff")[0], "pkg/retry.py")
        self.assertEqual(self.search("WidgetStore")[0], "web/app.js")

    def test_incremental_update(self):
        self.sync()
        self.write("pkg/client.py", FILES["pkg/client.py"] + "\n\ndef upload(blob):\n    return blob\n")
        head = self.commit("upload")
        code, state = self.sync("update")
        self.assertEqual((code, state["indexed"], state["unchanged"], state["watermark"]), (0, 1, 5, head))
        self.assertEqual(self.search("upload")[0], "pkg/client.py")

    def test_the_control_a_copy_that_always_rewalks_reindexes_everything(self):
        b = broken('rewalk = mode == "build" or src["chunker_version"] != CHUNKER_VERSION', "rewalk = True",
                   "codeindex_always_rewalk")
        self.sync(module=b)
        self.write("pkg/client.py", FILES["pkg/client.py"] + "\n# one change\n")
        self.commit("one change")
        state = self.sync("update", module=b)[1]
        self.assertEqual(state["indexed"], 6, "the broken copy re-indexes what the real update leaves alone")

    def test_rename_keeps_the_page(self):
        self.sync()
        before = self.page("pkg/client.py")["id"]
        self.git("mv", "pkg/client.py", "pkg/api_client.py")
        self.commit("rename")
        code, state = self.sync("update")
        self.assertEqual(state["renamed"], [{"from": "pkg/client.py", "to": "pkg/api_client.py"}])
        self.assertEqual((state["deleted"], state["indexed"]), ([], 0))
        self.assertEqual(self.page("pkg/api_client.py")["id"], before)
        self.assertIsNone(self.page("pkg/client.py"))
        self.assertIn("pkg/api_client.py", self.search("fetch url"))

    def test_the_control_without_rename_detection_reports_a_delete_and_a_new_page(self):
        b = broken("if path not in existing and by_hash.get(digest):", "if False:", "codeindex_no_rename")
        self.sync(module=b)
        self.git("mv", "pkg/client.py", "pkg/api_client.py")
        self.commit("rename")
        code, state = self.sync("update", module=b)
        self.assertEqual((state["renamed"], state["deleted"]), ([], ["pkg/client.py"]),
                         "the broken copy misses the rename the real script reports")

    def test_delete_is_soft_and_leaves_search(self):
        self.sync()
        self.git("rm", "-q", "web/app.js")
        self.commit("drop js")
        code, state = self.sync("update")
        self.assertEqual(state["deleted"], ["web/app.js"])
        self.assertEqual(self.page("web/app.js")["deleted"], 1)
        self.assertEqual(self.search("WidgetStore"), [])

    def test_the_control_a_delete_that_keeps_search_rows_still_finds_the_file(self):
        b = broken('        for path, r in gone.items():\n            clear_page(conn, r["id"], fts)\n',
                   "        for path, r in gone.items():\n", "codeindex_dirty_delete")
        self.sync(module=b)
        self.git("rm", "-q", "web/app.js")
        self.commit("drop js")
        self.sync("update", module=b)
        conn = b.connect(self.db)
        hits = conn.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'WidgetStore'").fetchone()[0]
        conn.close()
        self.assertGreater(hits, 0, "the broken copy leaves the deleted file searchable")

    def test_a_partial_failure_holds_the_watermark(self):
        first = self.sync()[1]["watermark"]
        self.write("pkg/client.py", FILES["pkg/client.py"] + "\n# changed\n")
        self.write("pkg/retry.py", FILES["pkg/retry.py"] + "\n\ndef jitter():\n    return 0\n")
        second = self.commit("two changes")
        real = ci.chunk_page

        def flaky(path, text, cfg):
            if path == "pkg/client.py":
                raise RuntimeError("planted chunker failure")
            return real(path, text, cfg)

        with mock.patch.object(ci, "chunk_page", flaky):
            code, state = self.sync("update")
            self.assertEqual((code, state["status"], state["watermark"]), (1, "ERR", first))
            self.assertEqual([f["path"] for f in state["failures"]], ["pkg/client.py"])
            self.assertEqual(self.search("jitter")[0], "pkg/retry.py", "the other file was still indexed")
            code, state = self.sync("update", skip_failed=True)
            self.assertEqual((code, state["watermark"]), (0, second))

    def test_the_control_a_copy_that_always_advances_moves_past_the_failure(self):
        b = broken("        advanced = not open_failures\n", "        advanced = True\n", "codeindex_always_advance")
        first = self.sync(module=b)[1]["watermark"]
        self.write("pkg/client.py", FILES["pkg/client.py"] + "\n# changed\n")
        second = self.commit("change")
        real = b.chunk_page
        with mock.patch.object(b, "chunk_page", lambda p, t, c: (_ for _ in ()).throw(RuntimeError("x"))
                               if p == "pkg/client.py" else real(p, t, c)):
            state = self.sync("update", module=b)[1]
        self.assertNotEqual(first, second)
        self.assertEqual(state["watermark"], second, "the broken copy advances past an unacknowledged failure")

    def test_a_chunker_version_bump_rewalks(self):
        self.sync()
        with mock.patch.object(ci, "CHUNKER_VERSION", ci.CHUNKER_VERSION + 1):
            code, state = self.sync("update")
        self.assertEqual((state["rewalk"], state["indexed"], state["unchanged"]), (True, 6, 0))

    def test_the_control_ignoring_the_chunker_version_rewalks_nothing(self):
        b = broken('rewalk = mode == "build" or src["chunker_version"] != CHUNKER_VERSION', 'rewalk = mode == "build"',
                   "codeindex_no_rewalk")
        self.sync(module=b)
        with mock.patch.object(b, "CHUNKER_VERSION", b.CHUNKER_VERSION + 1):
            state = self.sync("update", module=b)[1]
        self.assertEqual(state["indexed"], 0, "the broken copy misses the re-walk")

    def test_lock_takeover_after_five_minutes(self):
        lock = Path(str(self.db) + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('{"pid": 1, "token": "old"}', encoding="utf-8")
        old = time.time() - 600
        os.utime(lock, (old, old))
        code, state = self.sync()
        self.assertEqual((code, state["lock_takeover"]), (0, True))
        self.assertFalse(lock.exists(), "the lock is released after the run")
        lock.write_text('{"pid": 1, "token": "fresh"}', encoding="utf-8")
        with self.assertRaises(ci.Locked):
            self.sync("update")

    def test_the_control_without_the_stale_check_never_takes_over(self):
        b = broken('if age <= cfg["lock_stale_seconds"]:', "if True:", "codeindex_no_takeover")
        lock = Path(str(self.db) + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("{}", encoding="utf-8")
        old = time.time() - 600
        os.utime(lock, (old, old))
        with self.assertRaises(b.Locked):
            self.sync(module=b)

    def test_fts5_absent_fallback_ranks_the_same_way(self):
        self.sync()
        plain = Path(self.tmp.name, "cache", "plain.sqlite")
        with mock.patch.dict(os.environ, {"WESTACK_INDEX_NO_FTS": "1"}):
            code, state = ci.sync(self.repo, plain, "build")
            self.assertFalse(state["fts"])
            for query in ("exponential backoff", "WidgetStore", "deploying guide", "fetch url"):
                with self.subTest(query=query):
                    self.assertEqual(self.search(query, plain)[0], self.search(query)[0])

    def test_the_control_a_fallback_without_weights_finds_nothing(self):
        b = broken("s += weights[f] * idf", "s += 0 * idf", "codeindex_flat_fallback")
        plain = Path(self.tmp.name, "cache", "plain.sqlite")
        with mock.patch.dict(os.environ, {"WESTACK_INDEX_NO_FTS": "1"}):
            b.sync(self.repo, plain, "build")
            self.assertEqual(self.search("exponential backoff", plain, module=b), [],
                             "the broken fallback misses what the real one finds")

    def test_the_state_file_is_written_whole(self):
        self.sync()
        state = json.loads(Path(str(self.db) + ".state.json").read_text(encoding="utf-8"))
        self.assertEqual((state["format"], state["status"]), ("westack-index-state-1", "OK"))
        self.assertEqual(list(self.db.parent.glob("*.tmp")), [], "no temporary file is left behind")

    def test_backlinks_and_the_title_boost(self):
        self.sync()
        conn = ci.connect(self.db)
        result = ci.search(conn, "guide", ci.config())
        conn.close()
        top = result["results"][0]
        self.assertEqual(top["path"], "docs/guide.md")
        self.assertIn("title", top["boosts"])
        self.assertIn("backlinks 1", top["boosts"])


class CliTests(Fixture):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ci.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_commands_and_exit_codes(self):
        base = ["--repo", str(self.repo), "--db", str(self.db)]
        self.assertEqual(self.run_cli("search", *base, "anything")[0], 69)
        self.assertEqual(self.run_cli("doctor", *base)[0], 1)
        self.assertEqual(self.run_cli("build", *base)[0], 0)
        code, out, _ = self.run_cli("search", *base, "--budget", "balanced", "exponential", "backoff")
        self.assertEqual((code, json.loads(out)["results"][0]["path"]), (0, "pkg/retry.py"))
        self.assertEqual(json.loads(self.run_cli("show", *base, "docs/guide.md")[1])["chunks"][1]["symbol"], "Retries")
        code, out, _ = self.run_cli("doctor", *base)
        self.assertEqual((code, json.loads(out)["verdict"]), (0, "OK"))
        self.assertEqual(self.run_cli("build", "--repo", str(self.repo), "--db", str(self.repo / "x.sqlite"))[0], 64)
        self.assertEqual(self.run_cli("bogus")[0], 64)

    def test_a_saved_file_list_stands_in_for_the_index(self):
        listing = Path(self.tmp.name, "ls-files.txt")
        listing.write_text("README.md\npkg/retry.py\n", encoding="utf-8")
        code, state = ci.sync(self.repo, self.db, "build", files_list=str(listing))
        self.assertEqual((state["listed_by"], state["pages"]), ("saved list", 2))


class ChunkTests(unittest.TestCase):
    def test_markdown_sections_ignore_fenced_hashes(self):
        chunks = ci.chunk_page("docs/guide.md", FILES["docs/guide.md"], ci.config())
        self.assertEqual([c["symbol"] for c in chunks], ["Guide", "Retries", "Deploying"])

    def test_windows_and_the_size_cap(self):
        cfg = ci.config()
        words = " ".join(f"w{i}" for i in range(700))
        chunks = ci.chunk_page("notes.dat", words, cfg)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[1]["text"].split()[0], "w250", "windows overlap by 50 words")
        long = "\n".join("x = '" + "a" * 70 + "'" for _ in range(200))
        capped = ci.chunk_page("big.py", long, cfg)
        self.assertTrue(all(len(c["text"]) <= 8000 for c in capped))
        self.assertGreater(len(capped), 1)

    def test_regex_definitions_by_language(self):
        chunks = ci.chunk_page("web/app.js", FILES["web/app.js"], ci.config())
        self.assertEqual([c["symbol"] for c in chunks], ["renderWidget", "WidgetStore"])
        go = "package main\n\nfunc main() {\n}\n\nfunc (s *Server) Start() error {\n  return nil\n}\n"
        self.assertEqual([c["symbol"] for c in ci.chunk_page("main.go", go, ci.config())], [None, "main", "Start"])

    def test_the_index_stays_outside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ci.UsageError):
                ci.resolve_db(Path(tmp), str(Path(tmp, "idx.sqlite")))

    def test_remote_normalisation(self):
        cases = {"https://user:tok@GitHub.com/Org/Repo.git": "github.com/org/repo",
                 "git@github.com:org/repo.git": "github.com/org/repo",
                 "ssh://git@host.example:2222/org/repo/": "host.example:2222/org/repo"}
        for url, want in cases.items():
            with self.subTest(url=url):
                self.assertEqual(ci.normalise_remote(url), want)


if __name__ == "__main__":
    unittest.main()
