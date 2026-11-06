"""Tests for westack-onboard's call graph, context pack and delta (codeindex.py def, refs, callers, callees, context,
delta) on a temporary git repository. Each query has an in-suite broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-onboard/tests
"""
import contextlib
import copy
import io
import json
import sqlite3
import unittest
from unittest import mock

from test_codeindex import Fixture, broken, ci

CLIENT = ("from pkg.retry import retry, Backoff\n\n\n@retry(times=5)\ndef fetch(url):\n    return url\n\n\n"
          "def fetch_all(urls):\n    return [fetch(u) for u in urls]\n\n\n"
          "def wait(backoff, attempt):\n    return backoff.delay(attempt)\n\n\n"
          "def count_down(n):\n    if n:\n        return count_down(n - 1)\n    return 0\n")
APP = ("export function renderWidget(el) {\n  return el;\n}\n\nexport function mount(el) {\n  return renderWidget(el);\n}\n")


class GraphFixture(Fixture):
    def setUp(self):
        super().setUp()
        self.write("pkg/client.py", CLIENT)
        self.write("web/app.js", APP)
        self.base = self.commit("graph fixture")
        self.sync()

    def q(self, fn, *args, module=None):
        m = module or ci
        conn = m.connect(self.db)
        try:
            return getattr(m, fn)(conn, *args)
        finally:
            conn.close()

    @staticmethod
    def names(rows):
        return [(r["path"], r["symbol"]) for r in rows]


class DefinitionTests(GraphFixture):
    def test_def(self):
        self.assertEqual([(d["path"], d["qualname"], d["lines"]) for d in self.q("definitions", "fetch")],
                         [("pkg/client.py", "fetch", [4, 6])])
        self.assertEqual([d["qualname"] for d in self.q("definitions", "Backoff.delay")], ["Backoff.delay"])
        self.assertEqual([d["path"] for d in self.q("definitions", "delay")], ["pkg/retry.py"])
        self.assertEqual(self.q("definitions", "nothing_here"), [])


class CallerTests(GraphFixture):
    def test_callers(self):
        self.assertEqual(self.names(self.q("callers", "fetch")), [("pkg/client.py", "fetch_all")])
        self.assertEqual(self.names(self.q("callers", "retry")), [("pkg/client.py", "fetch")], "a decorator call counts")
        self.assertEqual(self.names(self.q("callers", "Backoff.delay")), [("pkg/client.py", "wait")])
        recursive = self.q("callers", "count_down")
        self.assertEqual([(r["symbol"], r["self"]) for r in recursive], [("count_down", True)])
        self.assertEqual(self.names(self.q("callers", "renderWidget")), [("web/app.js", "mount")])

    def test_the_control_without_method_calls_misses_the_attribute_caller(self):
        b = broken('        return f.attr, "attr"\n', "        return None\n", "codeindex_no_attr_calls")
        b.sync(self.repo, self.db, "build")
        self.assertEqual(self.q("callers", "delay", module=b), [], "the broken copy misses backoff.delay(...)")


class CalleeTests(GraphFixture):
    def test_callees(self):
        (fa,) = self.q("callees", "fetch_all")
        self.assertEqual([(c["name"], c["definitions"][0]["path"]) for c in fa["calls"]], [("fetch", "pkg/client.py")])
        (w,) = self.q("callees", "wait")
        self.assertEqual([c["definitions"][0]["qualname"] for c in w["calls"]], ["Backoff.delay"])
        (f,) = self.q("callees", "fetch")
        self.assertEqual([c["name"] for c in f["calls"]], ["retry"])
        (m,) = self.q("callees", "Backoff.delay")
        self.assertEqual((m["calls"], m["unresolved"]), ([], []))

    def test_a_same_file_definition_wins_and_in_pins_the_definition(self):
        self.write("pkg/other.py", "def fetch(x):\n    return x\n")
        self.commit("another fetch")
        self.sync("update")
        self.assertEqual(len(self.q("definitions", "fetch")), 2)
        self.assertEqual([d["path"] for d in self.q("definitions", "fetch", "pkg/other.py")], ["pkg/other.py"])
        (fa,) = self.q("callees", "fetch_all")
        self.assertEqual([(c["resolved"], [t["path"] for t in c["definitions"]]) for c in fa["calls"]],
                         [("same file", ["pkg/client.py"])])

    def test_the_control_without_the_same_file_preference_resolves_both(self):
        b = broken('"definitions": same or targets}', '"definitions": targets}', "codeindex_no_same_file")
        self.write("pkg/other.py", "def fetch(x):\n    return x\n")
        self.commit("another fetch")
        self.sync("update")
        (fa,) = self.q("callees", "fetch_all", module=b)
        self.assertEqual(len(fa["calls"][0]["definitions"]), 2, "the broken copy keeps the unrelated definition")

    def test_a_method_call_never_resolves_to_a_function(self):
        self.write("pkg/files.py", "def read_text():\n    return ''\n\n\ndef read_all(p):\n    return p.read_text()\n")
        self.commit("files")
        self.sync("update")
        (ra,) = self.q("callees", "read_all")
        self.assertEqual((ra["calls"], ra["unresolved"]), ([], ["read_text"]))

    def test_the_control_without_the_call_kind_resolves_the_method_call_to_the_function(self):
        b = broken("            targets = [t for t in definitions(conn, called) if fits(kind, t)]\n",
                   "            targets = definitions(conn, called)\n", "codeindex_no_kind")
        self.write("pkg/files.py", "def read_text():\n    return ''\n\n\ndef read_all(p):\n    return p.read_text()\n")
        self.commit("files")
        self.sync("update")
        (ra,) = self.q("callees", "read_all", module=b)
        self.assertEqual([c["name"] for c in ra["calls"]], ["read_text"], "the broken copy mistakes p.read_text()")

    def test_callers_pinned_to_a_file_keep_only_linked_ones(self):
        self.write("pkg/other.py", "def fetch(x):\n    return x\n")
        self.write("pkg/user.py", "from pkg.other import fetch\n\n\ndef go():\n    return fetch(1)\n")
        self.commit("other fetch and a user")
        self.sync("update")
        everyone = {(c["path"], c["symbol"], c["linked"]) for c in self.q("callers", "fetch")}
        self.assertIn(("pkg/user.py", "go", "names the module"), everyone)
        pinned = [(c["path"], c["symbol"], c["linked"]) for c in self.q("callers", "fetch", "pkg/client.py")]
        self.assertEqual(pinned, [("pkg/client.py", "fetch_all", "same file")])
        other = [(c["path"], c["symbol"]) for c in self.q("callers", "fetch", "pkg/other.py")]
        self.assertEqual(other, [("pkg/user.py", "go")])

    def test_unresolved_calls_are_kept_apart(self):
        self.write("pkg/io.py", "def save(path):\n    return open(path).read()\n")
        self.commit("io")
        self.sync("update")
        (s,) = self.q("callees", "save")
        self.assertEqual((s["calls"], s["unresolved"]), ([], ["open", "read"]))

    def test_the_control_without_resolution_resolves_nothing(self):
        b = broken("            if targets:\n", "            if False:\n", "codeindex_no_resolve")
        (fa,) = self.q("callees", "fetch_all", module=b)
        self.assertEqual((fa["calls"], fa["unresolved"]), ([], ["fetch"]), "the broken copy misses the resolution")


class ReferenceTests(GraphFixture):
    def test_refs_find_mentions_beyond_calls(self):
        refs = self.q("references", "Backoff")
        self.assertIn(("pkg/client.py", None), self.names(refs), "the import line mentions it")
        self.assertNotIn(("pkg/retry.py", "Backoff"), self.names(refs), "its own definition is not a reference")
        line = next(r for r in refs if r["path"] == "pkg/client.py")
        self.assertEqual((line["line"], line["text"]), (1, "from pkg.retry import retry, Backoff"))


class ContextTests(GraphFixture):
    def test_a_pack_is_definition_then_callees_then_callers(self):
        pack = self.q("context_pack", "fetch", ci.config(), "balanced")
        self.assertEqual([(p["role"], p["symbol"]) for p in pack["pack"]],
                         [("definition", "fetch"), ("callee", "retry"), ("caller", "fetch_all")])
        self.assertTrue(pack["pack"][0]["text"].startswith("@retry(times=5)"))

    def test_the_budget_holds(self):
        cfg = copy.deepcopy(ci.config())
        conn = ci.connect(self.db)
        try:
            need = ci.chunk_row(conn, ci.definitions(conn, "fetch")[0]["chunk"])["tokens"]
            cfg["budgets"]["conservative"] = need
            pack = ci.context_pack(conn, "fetch", cfg)
        finally:
            conn.close()
        self.assertEqual([p["role"] for p in pack["pack"]], ["definition"])
        self.assertEqual([p["role"] for p in pack["left_out"]], ["callee", "caller"])
        self.assertLessEqual(pack["tokens_used"], need)

    def test_the_control_a_pack_without_the_budget_takes_everything(self):
        b = broken('            left_out.append(dict(entry, tokens=r["tokens"]))\n            continue\n',
                   "            pass\n", "codeindex_no_budget")
        cfg = copy.deepcopy(ci.config())
        cfg["budgets"]["conservative"] = 1
        conn = b.connect(self.db)
        try:
            pack = b.context_pack(conn, "fetch", cfg)
        finally:
            conn.close()
        self.assertEqual(len(pack["pack"]), 3, "the broken copy ignores the budget")


class MigrationTests(GraphFixture):
    def make_old(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("DROP TABLE symbols")
        conn.execute("DROP TABLE refs")
        conn.execute("UPDATE meta SET value = '1' WHERE key = 'schema_version'")
        conn.commit()
        conn.close()

    def test_an_older_schema_is_reported_then_migrated(self):
        self.make_old()
        result = ci.doctor(self.repo, self.db, ci.config())
        self.assertEqual(result["verdict"], "ERR")
        self.assertIn(f"schema 1, expected {ci.SCHEMA_VERSION}", result["checks"][-1]["detail"])
        code, state = self.sync("update")
        self.assertEqual((code, state["rewalk"]), (0, True))
        self.assertGreater(state["symbols"], 0)
        self.assertEqual(ci.doctor(self.repo, self.db, ci.config())["verdict"], "OK")

    def test_the_control_without_the_schema_rewalk_leaves_no_symbols(self):
        b = broken(" or old_schema not in (None, SCHEMA_VERSION)", "", "codeindex_no_schema_rewalk")
        self.make_old()
        state = b.sync(self.repo, self.db, "update")[1]
        self.assertEqual(state["symbols"], 0, "the broken copy migrates the tables but never fills them")


class DeltaTests(GraphFixture):
    def change(self):
        self.write("pkg/retry.py", self.repo.joinpath("pkg/retry.py").read_text(encoding="utf-8") +
                   "\n\ndef jitter():\n    return 0\n")
        self.write("pkg/new.py", "def fresh():\n    return 1\n")
        self.git("mv", "web/app.js", "web/main.js")
        self.git("rm", "-q", "docs/guide.md")
        return self.commit("changes")

    def test_delta_since_a_watermark(self):
        head = self.change()
        self.sync("update")
        d = self.q("delta", self.base[:9])
        self.assertEqual(d["until"], head)
        self.assertEqual([(c["path"], c["change"], c.get("from")) for c in d["changes"]],
                         [("docs/guide.md", "deleted", None), ("pkg/new.py", "added", None),
                          ("pkg/retry.py", "modified", None), ("web/main.js", "renamed", "web/app.js")])
        self.assertEqual(self.q("delta", head)["changes"], [])
        with mock.patch.object(ci, "CHUNKER_VERSION", ci.CHUNKER_VERSION + 1):
            self.sync("update")
        self.assertEqual(self.q("delta", head)["changes"], [], "a re-chunk is not a change")
        self.assertIsNone(self.q("delta", "deadbeefcafe"))
        self.assertIsNone(self.q("delta", self.base[:5]), "a prefix shorter than seven characters is refused")

    def test_the_control_without_rename_logging_reports_add_and_delete(self):
        b = broken('                    change = "renamed"\n', '                    change = "added"\n',
                   "codeindex_no_rename_log")
        b.sync(self.repo, self.db, "build")
        self.change()
        b.sync(self.repo, self.db, "update")
        d = self.q("delta", self.base, module=b)
        self.assertNotIn("renamed", [c["change"] for c in d["changes"]], "the broken copy loses the rename")

    def test_cli(self):
        base = ["--repo", str(self.repo), "--db", str(self.db)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ci.main(["callers", *base, "fetch"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual((result["name"], result["callers"][0]["symbol"], result["watermark"]),
                         ("fetch", "fetch_all", self.base))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ci.main(["delta", *base, "--since", "deadbeefcafe"]), 2)
            self.assertEqual(ci.main(["context", *base, "--budget", "balanced", "fetch"]), 0)


if __name__ == "__main__":
    unittest.main()
