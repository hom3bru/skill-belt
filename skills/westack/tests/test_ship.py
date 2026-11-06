"""What ships: the one list of files that stay out of an installed or run copy of a skill.

The installer (tools/install.py), the eval runner's work-folder copy (tools/eval/campaign_run.py) and the
eval campaign's skill hash all read this one list from skillmeta.py. A skill's own evals/ (rubrics, canaries,
fixtures) and tests/ are an answer key: a host that can read them in its work folder can score itself."""
import pathlib
import shutil
import tempfile
import unittest

import test_westack as fixtures

v = fixtures.v


def make(base, names):
    base = pathlib.Path(base)
    for name in names:
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x\n")
    return base


SHIPS = ["SKILL.md", "references/a.md", "references/tests.md", "references/evals-guide.md", "scripts/tool.py",
         "scripts/tests_helper.py", "provenance/donors.json", "hosts/README.md", "examples/workspace/src/parser.txt"]
STAYS = ["evals/trigger-cases.json", "evals/tasks/campaign.json", "evals/tasks/fixtures/x/tests/test_x.py",
         "tests/test_x.py", "tests/fixtures/y.json", ".validation/out.txt",
         "scripts/__pycache__/tool.cpython-314.pyc", "__pycache__/m.cpython-314.pyc", "references/old.pyc"]


class ShipRuleTests(unittest.TestCase):
    def test_the_list_names_the_answer_key_and_the_caches(self):
        self.assertEqual(set(v.SHIP_EXCLUDE_DIRS), {"evals", "tests", ".validation"})
        self.assertEqual(set(v.CACHE_DIRS), {"__pycache__"})
        self.assertEqual(set(v.CACHE_SUFFIXES), {".pyc"})

    def test_is_shipped(self):
        for relative in SHIPS:
            self.assertTrue(v.is_shipped(relative), relative)
        for relative in STAYS:
            self.assertFalse(v.is_shipped(relative), relative)
        self.assertFalse(v.is_shipped("tests\\test_x.py"), "a Windows spelling is the same path")
        self.assertFalse(v.is_shipped(pathlib.PurePosixPath("evals/trigger-cases.json")))

    def test_shipped_files_lists_only_what_ships(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            make(temp, SHIPS + STAYS)
            found = [p.relative_to(temp).as_posix() for p in v.shipped_files(temp)]
            self.assertEqual(sorted(found), sorted(SHIPS))

    def test_ship_ignore_gives_copytree_the_same_answer(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            source = make(pathlib.Path(temp) / "source", SHIPS + STAYS)
            target = pathlib.Path(temp) / "target"
            shutil.copytree(source, target, ignore=v.ship_ignore(source))
            copied = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
            self.assertEqual(copied, sorted(SHIPS))
            self.assertEqual([p.name for p in target.iterdir() if p.is_dir() and p.name in v.SHIP_EXCLUDE_DIRS], [])

    def test_the_installed_manifest_is_never_copied(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            source = make(pathlib.Path(temp) / "source", SHIPS + [".westack-install.json"])
            target = pathlib.Path(temp) / "target"
            shutil.copytree(source, target, ignore=v.ship_ignore(source))
            self.assertFalse((target / ".westack-install.json").exists())


class ShippedLinkTests(unittest.TestCase):
    """A document that ships must not link to a file that does not: in the installed copy the link is dead."""

    def package(self, base, body, extra=None):
        folder = pathlib.Path(base) / "westack-linky"
        (folder / "references").mkdir(parents=True)
        (folder / "tests").mkdir()
        (folder / "SKILL.md").write_text(
            "---\nname: westack-linky\ndescription: A fake sub-skill for the link test.\nmetadata:\n  stack: westack\n"
            "  version: 0.0.1\n  requires_core: \">=1.0.0-alpha.0 <2\"\n---\n# Linky\n\n" + body + "\n", encoding="utf-8")
        (folder / "references" / "notes.md").write_text("# Notes\n", encoding="utf-8")
        (folder / "tests" / "answers.md").write_text("# Answers\n\nBack to [notes](../references/notes.md).\n", encoding="utf-8")
        for relative, text in (extra or {}).items():
            (folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (folder / relative).write_text(text, encoding="utf-8")
        return folder

    def test_a_link_to_a_shipped_file_is_fine(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            self.assertEqual(v.check_package(self.package(temp, "See [notes](references/notes.md).")), [])

    def test_a_shipped_document_may_not_link_into_the_answer_key(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            folder = self.package(temp, "See [answers](tests/answers.md).",
                                  {"references/more.md": "See [answers](../tests/answers.md).\n"})
            errors = v.check_package(folder)
            self.assertTrue(any("SKILL.md" in e and "does not ship" in e for e in errors), errors)
            self.assertTrue(any("more.md" in e and "does not ship" in e for e in errors), errors)

    def test_files_that_do_not_ship_may_link_to_each_other(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            folder = self.package(temp, "See [notes](references/notes.md).")
            self.assertEqual(v.check_package(folder), [], "tests/answers.md links to ../references/notes.md and tests/")

    def test_a_missing_target_is_still_broken_not_unshipped(self):
        with tempfile.TemporaryDirectory(prefix="westack-ship-") as temp:
            errors = v.check_package(self.package(temp, "See [x](references/gone.md)."))
            self.assertTrue(any("broken/escaping" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
