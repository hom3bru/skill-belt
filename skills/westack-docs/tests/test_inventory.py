"""DS-5 (dsh-superagent, 2026-10-31): a document that lists a folder's files is checked both ways, and a numbered series
links only to earlier documents.

  python prose.py inventory DOC FOLDER [--glob PATTERN] [--recursive]
      every file of FOLDER matching the pattern is named by DOC (`inventory-unlisted`), and every such file DOC names exists
      (`inventory-stale`). DOC names a file in a code span or a link target; a bare name is the folder's own, a path is
      read from DOC's folder. Fenced blocks and bare names in prose are not read.
  python prose.py series FOLDER [--glob PATTERN]
      a document whose name starts with a number links to no numbered document of the folder with the same or a higher
      number (`series-forward-link`).

Run: python -B -m unittest discover -s skills/westack-docs/tests -v
PROSE_UNDER_TEST=<path> points the suite at another copy. Every check also runs against a copy of the helper with that one
condition edited out, and the copy must let the bad input through. Each copy is built before its assertions.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("PROSE_UNDER_TEST") or HERE.parent / "scripts" / "prose.py")
RULES = HERE.parent / "references" / "rules.json"


def load(path=SCRIPT):
    key = "westack_docs_inventory_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DEFAULT_RULES = RULES
    return module


def codes(report):
    return sorted((f["code"], f["item"]) for f in report["findings"])


class Tree(unittest.TestCase):
    """A repository with src/ (alpha.py, beta.py, gamma.py, notes.txt, sub/deep.py), other/zeta.py and the documents."""

    FILES = {"src/alpha.py": "", "src/beta.py": "", "src/gamma.py": "", "src/notes.txt": "", "src/sub/deep.py": "",
             "other/zeta.py": ""}

    def setUp(self):
        self.pr = load()
        self.temp = tempfile.TemporaryDirectory(prefix="westack-inventory-")
        self.root = pathlib.Path(self.temp.name)
        for name, text in self.FILES.items():
            self.put(name, text)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def inventory(self, doc_text, doc="README.md", module=None, **kwargs):
        path = self.put(doc, doc_text)
        return (module or self.pr).inventory(str(path), str(self.root / "src"), **kwargs)


class BothWays(Tree):
    LISTING = "| Module | Role |\n| --- | --- |\n| `alpha.py` | first |\n| `beta.py` | second |\n"

    def test_a_listing_that_matches_the_folder_is_clean(self):
        report = self.inventory(self.LISTING + "| `gamma.py` | third |\n", glob="*.py")
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)
        self.assertEqual((report["existing"], report["listed"]), (3, 3))

    def test_one_unlisted_module_and_one_stale_row_are_both_reported(self):
        report = self.inventory(self.LISTING + "| `delta.py` | removed last month |\n", glob="*.py")
        self.assertEqual(codes(report), [("inventory-stale", "delta.py"), ("inventory-unlisted", "gamma.py")], report)
        self.assertEqual(report["status"], "findings")

    def test_the_pattern_decides_which_files_the_document_owes(self):
        report = self.inventory(self.LISTING + "| `gamma.py` | third |\n", glob="*.py")
        self.assertNotIn("notes.txt", json.dumps(report["findings"]))
        every = self.inventory(self.LISTING + "| `gamma.py` | third |\n")
        self.assertEqual(codes(every), [("inventory-unlisted", "notes.txt")], "no pattern: every file is owed")

    def test_links_and_paths_from_the_documents_own_folder_count(self):
        text = "- [alpha](../src/alpha.py)\n- [beta](../src/beta.py#L10)\n- `../src/gamma.py`\n"
        report = self.inventory(text, doc="docs/guide.md", glob="*.py")
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)

    def test_a_document_at_the_root_names_the_folders_files_by_path(self):
        report = self.inventory("`src/alpha.py` `src/beta.py` `src/gamma.py`\n", glob="*.py")
        self.assertEqual(report["findings"], [], report)

    def test_a_file_name_in_another_folder_is_not_a_stale_row(self):
        text = self.LISTING + "| `gamma.py` | third |\n| `../other/zeta.py` | lives elsewhere |\n"
        report = self.inventory(text, glob="*.py", recursive=True)
        self.assertEqual(codes(report), [("inventory-unlisted", "sub/deep.py")], report)

    def test_fenced_blocks_and_bare_names_in_prose_are_not_read(self):
        text = self.LISTING + "| `gamma.py` | third |\n\nSee ghost.py in prose.\n\n```\nghost.py\n`phantom.py`\n```\n"
        self.assertEqual(self.inventory(text, glob="*.py")["findings"], [])

    def test_subfolders_are_read_only_when_asked(self):
        text = self.LISTING + "| `gamma.py` | third |\n"
        self.assertEqual(self.inventory(text, glob="*.py")["findings"], [], "deep.py is not a direct child")
        self.assertEqual(codes(self.inventory(text, glob="*.py", recursive=True)), [("inventory-unlisted", "sub/deep.py")])
        listed = text + "| `src/sub/deep.py` | nested |\n"
        self.assertEqual(self.inventory(listed, glob="*.py", recursive=True)["findings"], [])

    def test_crlf_documents_read_the_same(self):
        report = self.inventory((self.LISTING + "| `gamma.py` | third |\n").replace("\n", "\r\n"), glob="*.py")
        self.assertEqual(report["findings"], [], report)

    def test_an_unreadable_document_is_unreadable_not_clean(self):
        report = self.pr.inventory(str(self.root / "missing.md"), str(self.root / "src"))
        self.assertEqual((report["status"], self.pr.exit_code(report)), ("unreadable", 2), report)
        binary = self.put("bad.md", "x")
        binary.write_bytes(b"\xff\xfe\x00bad")
        report = self.pr.inventory(str(binary), str(self.root / "src"))
        self.assertEqual(report["status"], "unreadable")

    def test_the_report_says_it_compares_names_only(self):
        text = json.dumps(self.inventory(self.LISTING, glob="*.py")).lower()
        self.assertIn("does not show", text)


class Series(Tree):
    def setUp(self):
        super().setUp()
        self.docs = self.root / "docs"
        for name in ("000-intro.md", "001-scope.md", "002-design.md", "003-plan.md", "004-api.md"):
            self.put("docs/" + name, "# " + name + "\n")

    def series(self, module=None, **kwargs):
        return (module or self.pr).series(str(self.docs), **kwargs)

    def test_links_to_earlier_documents_pass(self):
        self.put("docs/004-api.md", "See [design](002-design.md), [scope](001-scope.md#goals), [web](https://example.com/005-x.md)"
                                    " and [top](#api).\n")
        report = self.series()
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)
        self.assertEqual(report["documents"], 5)

    def test_a_document_that_links_to_a_later_one_is_flagged(self):
        self.put("docs/002-design.md", "The API is in [004](004-api.md#top).\n")
        report = self.series()
        self.assertEqual(codes(report), [("series-forward-link", "002-design.md -> 004-api.md")], report)

    def test_a_link_to_itself_and_a_reference_style_link_count(self):
        self.put("docs/003-plan.md", "[here](003-plan.md)\n\n[later]: ./004-api.md\n")
        self.assertEqual(sorted(i for _, i in codes(self.series())),
                         ["003-plan.md -> 003-plan.md", "003-plan.md -> 004-api.md"])

    def test_unnumbered_documents_other_folders_and_fenced_links_are_not_series_links(self):
        self.put("docs/README.md", "[later](004-api.md)\n")
        self.put("docs/001-scope.md", "[readme](README.md) [other](../src/alpha.py)\n\n```\n[x](004-api.md)\n```\n")
        self.assertEqual(self.series()["findings"], [])

    def test_the_series_pattern_picks_the_documents(self):
        self.put("docs/002-design.md", "[four](004-api.md)\n")
        self.assertEqual(self.series(glob="*.txt")["documents"], 0)
        self.assertEqual(self.series(glob="*.txt")["findings"], [])


class Cli(Tree):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), *args], capture_output=True, text=True, env=env,
                              timeout=120)

    def test_exit_codes_and_json(self):
        self.put("good.md", "`alpha.py` `beta.py` `gamma.py`\n")
        self.put("short.md", "`alpha.py` `beta.py` `delta.py`\n")
        src = str(self.root / "src")
        ok = self.run_cli("inventory", str(self.root / "good.md"), src, "--glob", "*.py")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["command"], "inventory")
        bad = self.run_cli("inventory", str(self.root / "short.md"), src, "--glob", "*.py")
        self.assertEqual(bad.returncode, 1)
        self.assertEqual({f["code"] for f in json.loads(bad.stdout)["findings"]}, {"inventory-stale", "inventory-unlisted"})
        self.assertEqual(self.run_cli("inventory", str(self.root / "missing.md"), src).returncode, 2)
        self.assertEqual(self.run_cli("inventory", str(self.root / "good.md"), str(self.root / "nope")).returncode, 64)
        self.put("docs/001-a.md", "[b](002-b.md)\n")
        self.put("docs/002-b.md", "x\n")
        self.assertEqual(self.run_cli("series", str(self.root / "docs")).returncode, 1)
        self.put("docs/001-a.md", "x\n")
        self.assertEqual(self.run_cli("series", str(self.root / "docs")).returncode, 0)
        self.assertEqual(self.run_cli("series", str(self.root / "nope")).returncode, 64)


class BrokenCopies(Tree):
    """One condition of the check edited out of a copy; the copy must pass what the condition exists to refuse."""

    BOTH = "`alpha.py` `beta.py` `delta.py`\n"  # gamma.py is unlisted, delta.py is stale

    def broken(self, *edits):
        source = SCRIPT.read_text(encoding="utf-8")
        for pattern, replacement in edits:
            edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
            self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
            self.assertNotEqual(edited, source)
            source = edited
        target = pathlib.Path(self.temp.name) / ("prose_broken_%d.py" % len(list(self.root.glob("prose_broken_*.py"))))
        target.write_text(source, encoding="utf-8")
        return load(target)

    def test_a_copy_that_checks_only_the_unlisted_direction_misses_the_stale_row(self):
        copy = self.broken((r"^    for item in stale:$", "    for item in []:"))
        real, broken = self.inventory(self.BOTH, glob="*.py"), self.inventory(self.BOTH, glob="*.py", module=copy)
        self.assertEqual({c for c, _ in codes(real)}, {"inventory-stale", "inventory-unlisted"})
        self.assertEqual({c for c, _ in codes(broken)}, {"inventory-unlisted"})

    def test_a_copy_that_checks_only_the_stale_direction_misses_the_unlisted_module(self):
        copy = self.broken((r"^    for item in unlisted:$", "    for item in []:"))
        real, broken = self.inventory(self.BOTH, glob="*.py"), self.inventory(self.BOTH, glob="*.py", module=copy)
        self.assertEqual({c for c, _ in codes(real)}, {"inventory-stale", "inventory-unlisted"})
        self.assertEqual({c for c, _ in codes(broken)}, {"inventory-stale"})

    def test_a_copy_that_treats_every_path_as_the_folders_calls_another_folders_file_stale(self):
        text = "`alpha.py` `beta.py` `gamma.py` `../other/zeta.py` `sub/deep.py`\n"
        copy = self.broken((r"^    if folder not in resolved\.parents:$", "    if False:"))
        real = self.inventory(text, doc="docs/guide.md", glob="*.py", recursive=True)
        broken = self.inventory(text, doc="docs/guide.md", glob="*.py", recursive=True, module=copy)
        self.assertNotIn("../other/zeta.py", [f["item"] for f in real["findings"]])
        self.assertIn("../other/zeta.py", [f["item"] for f in broken["findings"]])

    def test_a_copy_without_the_series_order_check_lets_002_link_to_004(self):
        for name in ("000-intro.md", "001-scope.md", "002-design.md", "003-plan.md", "004-api.md"):
            self.put("docs/" + name, "# x\n")
        self.put("docs/002-design.md", "[four](004-api.md)\n")
        copy = self.broken((r"^            if later:$", "            if False:"))
        self.assertEqual(codes(self.pr.series(str(self.root / "docs"))), [("series-forward-link", "002-design.md -> 004-api.md")])
        self.assertEqual(copy.series(str(self.root / "docs"))["findings"], [])


class Discipline(unittest.TestCase):
    def test_the_helper_still_only_reads(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import subprocess", "os.system", "eval(", "exec(", "urllib", "socket", "shutil.rmtree"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
