"""Sibling-stack public builds preserve links, ownership and atomic replacement."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_collection import load, make_dir_link, tree


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_public.py"


class WestackBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="belt-sibling-build-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "belt"
        self.source = self.base / "canonical/skills"
        self.names = ("westack", "westack-build", "westack-review")
        for name in self.names:
            folder = self.source / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(
                "---\nname: " + name + "\ndescription: Fixture.\nmetadata:\n"
                "  stack: westack\n  version: 1.0.0-alpha.0\n---\n", encoding="utf-8")
        (self.source / "westack/stack.json").write_text(json.dumps(dict(
            format="westack-stack-1", skills=[
                dict(name="build", status="built", invocation="model"),
                dict(name="review", status="built", invocation="manual"),
                dict(name="spec", status="planned", invocation="model"),
                dict(name="plan-review", status="built", invocation="folded", into="review")
            ])), encoding="utf-8")
        (self.source / "westack-build/guide.md").write_text(
            "[Router](../westack/SKILL.md)\n[Peer](../westack-review/SKILL.md)\n", encoding="utf-8")
        (self.root / "shared").mkdir(parents=True)
        (self.root / "shared/evidence-vocabulary.md").write_text("# Fixture\n", encoding="utf-8")
        public = self.root / "skills/westack"
        public.mkdir(parents=True)
        (public / "SKILL.md").write_text("old router\n", encoding="utf-8")
        self.config = dict(format="skill-belt-public-build-1", skills={
            name: dict(exclude=[], overlays={}) for name in self.names})
        self.write_config()
        self.before = tree(self.root / "skills")
        spec = importlib.util.spec_from_file_location("sibling_build", SCRIPT)
        self.build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.build)

    def write_config(self):
        (self.root / "public-build.json").write_text(json.dumps(self.config), encoding="utf-8")

    def run_build(self, check=False):
        return self.build.build({}, root=self.root, check=check, westack_stack=self.source)

    def assert_unchanged(self):
        self.assertEqual(tree(self.root / "skills"), self.before)
        self.assertFalse((self.root / ".public-build").exists())

    def test_cli_accepts_sibling_source(self):
        # Check the normal parser without changing the real collection root.
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--westack-stack",
                                 str(self.source), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--westack-stack", result.stdout)

    def test_complete_stack_preserves_bytes_and_sibling_links(self):
        report = self.run_build()
        self.assertEqual(set(report["skills"]), set(self.names))
        for name in self.names:
            self.assertEqual(tree(self.root / "skills" / name), tree(self.source / name))
        self.assertFalse((self.root / ".public-build").exists())

    def test_check_mode_leaves_all_current_bytes_unchanged(self):
        self.assertEqual(self.run_build(check=True)["mode"], "check")
        self.assert_unchanged()

    def test_router_only_input_cannot_publish_an_incomplete_sibling_stack(self):
        with self.assertRaisesRegex(ValueError, "sibling|westack-stack"):
            self.build.build({"westack": self.source / "westack"}, root=self.root)
        self.assert_unchanged()

    def test_legacy_single_skill_replaces_a_stack_without_leaving_stale_children(self):
        self.run_build()
        legacy = self.base / "legacy"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text("---\nname: westack\ndescription: Legacy.\n---\n")
        self.build.build({"westack": legacy}, root=self.root)
        self.assertFalse((self.root / "skills/westack-build").exists())
        self.assertFalse((self.root / "skills/westack-review").exists())

    def test_missing_declared_sibling_blocks_every_replacement(self):
        (self.source / "westack-review/SKILL.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing|Missing|canonical"):
            self.run_build()
        self.assert_unchanged()

    def test_undeclared_sibling_is_rejected(self):
        (self.source / "westack-unknown").mkdir()
        with self.assertRaisesRegex(ValueError, "undeclared|Unexpected|disagree"):
            self.run_build()
        self.assert_unchanged()

    def test_escaping_manifest_name_is_rejected(self):
        path = self.source / "westack/stack.json"
        data = json.loads(path.read_text())
        data["skills"][0]["name"] = "../escape"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "name"):
            self.run_build()
        self.assert_unchanged()

    def test_overlay_cannot_change_final_stack_membership(self):
        relative = "stack.json"
        original = (self.source / "westack" / relative).read_bytes()
        overlay = self.root / "public-overlays/westack" / relative
        overlay.parent.mkdir(parents=True)
        overlay.write_text(json.dumps(dict(format="westack-stack-1", skills=[])))
        self.config["skills"]["westack"]["overlays"][relative] = dict(
            base_sha256=hashlib.sha256(original).hexdigest(), reason="planted membership drift")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "membership|disagree"):
            self.run_build()
        self.assert_unchanged()

    def test_invalid_current_manifest_does_not_leave_staging_behind(self):
        (self.root / "skills/westack/stack.json").write_text("{broken")
        self.before = tree(self.root / "skills")
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.run_build()
        self.assert_unchanged()

    def test_leak_in_one_sibling_blocks_the_whole_stack(self):
        (self.source / "westack-review/leak.txt").write_text("libfile_" + "b" * 32)
        with self.assertRaisesRegex(ValueError, "Private identifier"):
            self.run_build()
        self.assert_unchanged()

    def test_link_outside_the_stack_is_rejected(self):
        (self.source / "westack-build/guide.md").write_text("[Escape](../../outside.md)\n")
        (self.base / "outside.md").write_text("outside\n")
        with self.assertRaisesRegex(ValueError, "Broken/escaping"):
            self.run_build()
        self.assert_unchanged()

    def test_linked_sibling_is_rejected(self):
        linked = self.source / "westack-linked"
        make_dir_link(linked, self.source / "westack-build")
        try:
            with self.assertRaisesRegex(ValueError, "[Ll]ink"):
                self.run_build()
            self.assert_unchanged()
        finally:
            os.rmdir(linked) if os.name == "nt" else linked.unlink()

    def test_failed_swap_restores_every_previous_skill(self):
        original = self.build.os.rename
        def fail_one(source, target):
            if Path(source).name == "westack-review" and Path(target).parent == self.root / "skills":
                raise OSError("planted replacement failure")
            return original(source, target)
        with patch.object(self.build.os, "rename", side_effect=fail_one):
            with self.assertRaisesRegex(ValueError, "restored"):
                self.run_build()
        self.assert_unchanged()

    def test_obsolete_declared_sibling_is_removed_only_after_a_valid_build(self):
        self.run_build()
        manifest = self.source / "westack/stack.json"
        data = json.loads(manifest.read_text())
        data["skills"][1]["status"] = "planned"
        manifest.write_text(json.dumps(data))
        (self.source / "westack-review/SKILL.md").unlink()
        (self.source / "westack-review").rmdir()
        (self.source / "westack-build/guide.md").write_text("[Router](../westack/SKILL.md)\n")
        report = self.run_build()
        self.assertEqual(report["removed_stack_skills"], ["westack-review"])
        self.assertFalse((self.root / "skills/westack-review").exists())

    def test_manifest_records_component_versions_and_stack_release_separately(self):
        router = self.source / "westack"
        (router / "README.md").write_text("# westack core 1.0.0-alpha.0\n")
        (router / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0-alpha.65, unreleased\n")
        generator = load("generate_manifest")
        generator.ROOT = self.source.parent
        generator.NAMES = ("westack",)
        generator.main()
        rows = json.loads((generator.ROOT / "skills-manifest.json").read_text())["skills"]
        self.assertEqual({row["name"] for row in rows}, set(self.names))
        core = next(row for row in rows if row["name"] == "westack")
        self.assertEqual(core["version"], "1.0.0-alpha.0")
        self.assertEqual(core["stack_release"], "1.0.0-alpha.65")

    def test_version_metadata_keeps_inline_comment_support(self):
        generator = load("generate_manifest")
        entry = self.source / "westack/SKILL.md"
        for version in ('"1.2.3" # release', '1.2.3 # release'):
            with self.subTest(version=version):
                entry.write_text('---\nname: westack\nmetadata:\n  version: ' + version + '\n---\n')
                self.assertEqual(generator.skill_version(entry.parent), "1.2.3")


if __name__ == "__main__":
    unittest.main()
