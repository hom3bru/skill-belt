"""Tests for westack-review's scripts/sharedcode.py (the shared-code lens) on a fixture repository with one helper copied
into three files: one exact copy, one reformatted with comments, one with its locals renamed.

Run from the repo root:  python -B -m unittest discover -s skills/westack-review/tests
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "sharedcode.py"


def load(path=SCRIPT, name="westack_sharedcode_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sc = load()


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        return load(path, name)


SLUG = ('def slugify(text):\n    """Lower-case, hyphenated."""\n    words = text.strip().lower().split()\n'
        '    joined = "-".join(words)\n    if not joined:\n        return "untitled"\n'
        '    return "".join(c for c in joined if c.isalnum() or c == "-")\n')
SLUG_REFORMATTED = ('def slugify(text):\n    # make a slug for the URL\n    words = text.strip().lower().split()  # words\n'
                    '    joined = "-".join(\n        words\n    )\n    if not joined:  # empty titles\n'
                    '        return "untitled"\n'
                    '    return "".join(c for c in joined if c.isalnum() or c == "-")\n')
SLUG_RENAMED = ('def make_slug(title):\n    parts = title.strip().lower().split()\n    s = "-".join(parts)\n'
                '    if not s:\n        return "untitled"\n'
                '    return "".join(ch for ch in s if ch.isalnum() or ch == "-")\n')
FILES = {
    "blog/posts.py": "import os\n\n\n" + SLUG + "\n\ndef publish(post):\n    return slugify(post.title)\n",
    "shop/products.py": SLUG_REFORMATTED + "\n\ndef price(p):\n    return p.cents / 100\n",
    "docs/pages.py": "class Pages:\n    pass\n\n\n" + SLUG_RENAMED,
    "util/small.py": "def tiny(x):\n    return x\n",
    "util/other.py": "def tiny(y):\n    return y\n",
}


class LensTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel, text in FILES.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def test_one_candidate_with_its_three_sites(self):
        result = sc.scan(self.root)
        self.assertEqual(len(result["candidates"]), 1, "tiny() is under the size floor; slugify is the one candidate")
        c = result["candidates"][0]
        self.assertEqual(sorted((s["path"], s["symbol"]) for s in c["sites"]),
                         [("blog/posts.py", "slugify"), ("docs/pages.py", "make_slug"), ("shop/products.py", "slugify")])
        self.assertEqual((c["kind"], c["files"]), ("renamed", 3))
        self.assertGreater(c["estimate"]["net"], 0)

    def test_exact_when_only_formatting_differs(self):
        (self.root / "docs/pages.py").unlink()
        (c,) = sc.scan(self.root)["candidates"]
        self.assertEqual((c["kind"], len(c["sites"])), ("exact", 2))

    def test_changed_files_keep_only_new_duplication(self):
        self.assertEqual(len(sc.scan(self.root, changed={"shop/products.py"})["candidates"]), 1)
        self.assertEqual(sc.scan(self.root, changed={"util/small.py"})["candidates"], [])

    def test_the_size_floor(self):
        self.assertEqual(len(sc.scan(self.root, min_lines=1)["candidates"]), 2, "tiny() counts once the floor drops")

    def test_the_control_without_name_normalisation_misses_the_renamed_copy(self):
        b = broken("        if n not in self.local:\n", "        if True:\n", "sharedcode_no_rename")
        (c,) = b.scan(self.root)["candidates"]
        self.assertEqual(len(c["sites"]), 2, "the broken copy finds two sites, not three")

    def test_the_control_comparing_raw_text_finds_nothing(self):
        b = broken("            exact, renamed = fingerprints(fn)\n",
                   "            exact = renamed = __import__('hashlib').sha256(ast.get_source_segment("
                   "path.read_text(encoding='utf-8'), fn).encode()).hexdigest()\n", "sharedcode_raw_text")
        self.assertEqual(b.scan(self.root)["candidates"], [], "raw text misses every reformatted or renamed copy")

    def test_cli(self):
        self.assertEqual(sc.main(["scan", str(self.root)]), 0)
        listing = self.root / "changed.txt"
        listing.write_text("shop\\products.py\n", encoding="utf-8")
        self.assertEqual(sc.main(["scan", str(self.root), "--changed", str(listing)]), 0)
        self.assertEqual(sc.main(["scan"]), 64)


if __name__ == "__main__":
    unittest.main()
