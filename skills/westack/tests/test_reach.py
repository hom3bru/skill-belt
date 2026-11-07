"""DG-42: every reference page a skill ships is reachable, linked or named by path from its SKILL.md, from a page
SKILL.md reaches, or from another westack skill beside it. A page nothing reaches fails the package check; a page
mentioned only in prose (its bare file name) is not reached. The cross-skill case is in tools/tests/test_reference_reach.py.

Each check also runs on a broken copy of skillmeta.py with that one condition removed: the orphan must get through
there, or the test protects nothing. The copy is built before any assertion runs."""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT.parent


def load_meta(scripts, name):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(scripts) / "skillmeta.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


meta = load_meta(ROOT / "scripts", "westack_skillmeta_reach")


def unreached(errors):
    return sorted(e.split(":", 1)[0] for e in errors if "not reached" in e)


class ReachTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="westack-reach-")
        self.addCleanup(temp.cleanup)
        self.base = pathlib.Path(temp.name)

    def copy(self, name="westack-design"):
        """A shipped copy of a built skill, alone in its folder."""
        target = self.base / "skills" / name
        shutil.copytree(SKILLS / name, target, ignore=meta.ship_ignore(SKILLS / name))
        return target

    def broken(self, old, new):
        scripts = self.base / "broken" / "scripts"
        shutil.copytree(ROOT / "scripts", scripts, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        path = scripts / "skillmeta.py"
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError("mutation target occurs %d times: %r" % (text.count(old), old))
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        return load_meta(scripts, "westack_skillmeta_reach_broken_%d" % abs(hash((old, new))))

    def test_the_core_and_a_built_skill_reach_every_page_today(self):
        self.assertEqual(unreached(meta.check_package(ROOT)), [])
        self.assertEqual(meta.check_package(self.copy()), [], "an untouched copy passes")

    def test_an_orphan_page_is_named(self):
        control = self.broken("if orphans:", "if False:")
        folder = self.copy()
        (folder / "references" / "zz-orphan.md").write_text("# Orphan\n\nNothing links here.\n", encoding="utf-8")
        self.assertEqual(unreached(meta.check_package(folder)), ["references/zz-orphan.md"])
        self.assertEqual(unreached(control.check_package(folder)), [], "a copy without the check lets it through")

    def test_a_mention_in_prose_is_not_a_path(self):
        control = self.broken("if orphans:", "if False:")
        folder = self.copy()
        (folder / "references" / "zz-orphan.md").write_text("# Orphan\n", encoding="utf-8")
        skill = folder / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        skill.write_text(text + "\nThe zz-orphan.md page and the zz-orphan notes are mentioned here only in prose.\n",
                         encoding="utf-8")
        self.assertEqual(unreached(meta.check_package(folder)), ["references/zz-orphan.md"],
                         "a substring test would accept it; a bare file name is not a path")
        self.assertEqual(unreached(control.check_package(folder)), [])
        skill.write_text(text + "\nSee `references/zz-orphan.md` for the notes.\n", encoding="utf-8")
        self.assertEqual(meta.check_package(folder), [], "a named path reaches it")

    def test_a_page_reached_only_from_an_unreached_page_is_unreached(self):
        folder = self.copy()
        refs = folder / "references"
        (refs / "zz-orphan.md").write_text("# Orphan\n", encoding="utf-8")
        (refs / "zz-hub.md").write_text("# Hub\n\nSee [orphan](zz-orphan.md).\n", encoding="utf-8")
        self.assertEqual(unreached(meta.check_package(folder)), ["references/zz-hub.md", "references/zz-orphan.md"])
        browser = refs / "browser.md"
        browser.write_text(browser.read_text(encoding="utf-8") + "\nMore in [hub](zz-hub.md).\n", encoding="utf-8")
        self.assertEqual(meta.check_package(folder), [], "linked from a page SKILL.md reaches, so both are reached")


if __name__ == "__main__":
    unittest.main()
