"""registry.py: list installed skills from the documented host roots by reading front matter only.
A westack-* folder counts as ours only with metadata.stack: westack. Fake homes and projects only."""
import ast
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
SCRIPT = ROOT / "scripts" / "registry.py"


def skill(folder, *front, body="# Body\n", newline="\n"):
    folder.mkdir(parents=True, exist_ok=True)
    text = "---\n" + "\n".join(front) + "\n---\n" + body
    (folder / "SKILL.md").write_bytes(text.replace("\n", newline).encode("utf-8"))
    return folder


def tree(base):
    return sorted((str(p.relative_to(base)), p.stat().st_size) for p in base.rglob("*"))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-registry-")
        base = pathlib.Path(self.temp.name)
        self.home, self.project = base / "home", base / "project"
        ours = ("metadata:", "  stack: westack", "  version: 1.0.0-alpha.0")
        skill(self.home / ".claude/skills/westack", "name: westack", "description: Router.",
              "disable-model-invocation: true", *ours)
        skill(self.home / ".claude/skills/gstack-qa", "name: qa", "description: >-", "  QA the site", "  in a browser.",
              "allowed-tools:", "  - Bash", "version: 2.3.0", newline="\r\n")
        skill(self.home / ".claude/skills/westack-review", "name: westack-review", "description: Someone else's.",
              "metadata:", "  stack: otherstack", "  version: 9.0.0")
        skill(self.home / ".codex/skills/.system/skill-installer", "name: skill-installer", "description: Installs.")
        skill(self.home / ".agents/skills/codex-user", "name: codex-user", "description: Codex user skill.")
        skill(self.home / ".cursor/skills/cursor-user", "name: cursor-user", "description: Cursor user skill.")
        skill(self.project / ".claude/skills/westack-debug", "name: westack-debug", "description: Debug.",
              "metadata:", "  stack: westack", "  version: 0.1.0", '  requires_core: ">=1.0.0-alpha.0 <2"')
        skill(self.project / ".agents/skills/shared", "name: shared", "description: Shared project skill.")
        skill(self.project / ".cursor/skills/cursor-project", "name: cursor-project", "description: Project.")
        skill(self.project / ".claude/skills/broken", "name broken without colon", body="")
        (self.project / ".claude/skills/not-a-skill").mkdir(parents=True)
        trap = self.project / ".claude/skills/westack-debug/scripts"
        trap.mkdir()
        (trap / "run.py").write_text("open(r'%s', 'w').write('ran')\n" % (self.project / "EXECUTED"), encoding="utf-8")
        self.before = tree(pathlib.Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, env=None):
        environment = dict(os.environ, **(env or {}))
        environment.pop("CODEX_HOME", None) if not env or "CODEX_HOME" not in env else None
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--home", str(self.home), "--project",
                               str(self.project), *args], capture_output=True, text=True, timeout=60, env=environment)

    def report(self, *args, env=None):
        result = self.cli(*args, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def by_name(self, report):
        return {s["name"] or s["folder"]: s for s in report["skills"]}

    def test_lists_every_documented_root(self):
        report = self.report()
        self.assertEqual(report["format"], "westack-registry-1")
        names = set(self.by_name(report))
        self.assertTrue({"westack", "qa", "westack-review", "skill-installer", "codex-user", "cursor-user",
                         "westack-debug", "shared", "cursor-project"} <= names, names)
        self.assertNotIn("not-a-skill", names)

    def test_ours_needs_the_stack_metadata(self):
        report = self.report()
        self.assertEqual(report["ours"], ["westack", "westack-debug"])
        self.assertEqual(report["foreign_westack_names"], ["westack-review"])
        debug = self.by_name(report)["westack-debug"]
        self.assertEqual((debug["stack"], debug["version"], debug["requires_core"]),
                         ("westack", "0.1.0", ">=1.0.0-alpha.0 <2"))
        self.assertEqual(report["core"], {"present": True, "version": "1.0.0-alpha.0",
                                          "path": str(self.home / ".claude/skills/westack")})

    def test_foreign_front_matter_is_read_leniently(self):
        qa = self.by_name(self.report())["qa"]
        self.assertEqual((qa["folder"], qa["version"], qa["stack"]), ("gstack-qa", "2.3.0", None))
        self.assertEqual(len(qa["description_sha256"]), 64)
        self.assertTrue(qa["name_differs_from_folder"])
        broken = next(s for s in self.report()["skills"] if s["folder"] == "broken")
        self.assertTrue(broken["errors"])

    def test_shared_agents_root_is_listed_once_for_both_hosts(self):
        report = self.report()
        roots = [r for r in report["roots"] if r["path"] == str(self.project / ".agents/skills")]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["hosts"], ["codex", "cursor"])
        self.assertEqual(self.by_name(report)["shared"]["hosts"], ["codex", "cursor"])

    def test_host_filter_and_codex_home(self):
        claude = self.report("--host", "claude")
        self.assertEqual({r["scope"] for r in claude["roots"]}, {"user", "project"})
        self.assertTrue(all(r["hosts"] == ["claude"] for r in claude["roots"]))
        custom = self.home / "codexhome"
        skill(custom / "skills/from-codex-home", "name: from-codex-home", "description: Here.")
        codex = self.report("--host", "codex", env={"CODEX_HOME": str(custom)})
        self.assertIn("from-codex-home", self.by_name(codex))

    def test_reads_only(self):
        self.report()
        self.assertFalse((self.project / "EXECUTED").exists())
        self.assertEqual(tree(pathlib.Path(self.temp.name)), self.before)
        source = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = {a.name.split(".")[0] for n in ast.walk(source) if isinstance(n, ast.Import) for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(source) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"subprocess", "socket", "urllib", "http", "runpy", "multiprocessing"})


if __name__ == "__main__":
    unittest.main()
