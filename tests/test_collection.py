"""Meaningful rejection controls for publication checks, public builds and test-count honesty."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location("belt_" + name.replace("-", "_"), SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("verify")
VOCABULARY = b"# Evidence vocabulary fixture\n\nObserved, inferred and unknown stay distinct.\n"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root):
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(Path(root).rglob("*")) if path.is_file()}


def make_dir_link(link, target):
    """A directory symlink on POSIX; a junction (no privilege needed) on Windows."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


class PublishedFixture:
    """A throwaway collection root that verify.structure() accepts, with verify.ROOT pointed at it."""

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-publication-test-")
        self.root = Path(self.temp.name)
        self.previous = verify.ROOT
        verify.ROOT = self.root
        (self.root / "shared").mkdir()
        (self.root / "shared/evidence-vocabulary.md").write_bytes(VOCABULARY)
        for name in verify.SKILLS:
            skill = self.root / "skills" / name
            (skill / "references").mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Authored fixture\n", encoding="utf-8")
            (skill / "references/evidence-vocabulary.md").write_bytes(VOCABULARY)
        for parent, subs in verify.SUB_SKILLS.items():
            for sub in subs:
                (self.root / "skills" / parent / "skills" / sub).mkdir(parents=True)
                (self.root / "skills" / parent / "skills" / sub / "SKILL.md").write_text("# Sub-skill fixture\n", encoding="utf-8")
        self.write_manifest()
        return self.root

    def write_manifest(self):
        rows = [dict(name=name, files=tree(self.root / "skills" / name)) for name in verify.SKILLS]
        (self.root / "skills-manifest.json").write_text(json.dumps(dict(skills=rows)), encoding="utf-8")

    def __exit__(self, *exc):
        verify.ROOT = self.previous
        self.temp.cleanup()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PublishedFixture()
        self.root = self.fixture.__enter__()

    def write_manifest(self):
        self.fixture.write_manifest()

    def tearDown(self):
        self.fixture.__exit__(None, None, None)

    def test_clean_published_snapshot_passes(self):
        self.assertGreater(verify.structure(), 0)

    def test_private_identifier_is_rejected(self):
        # Construct an obviously synthetic identifier without putting one in
        # the public source tree that the publication scanner itself reads.
        (self.root / "README.md").write_text("libfile_" + "a" * 32, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Private identifier"):
            verify.structure()

    def test_json_escaped_windows_user_path_is_rejected(self):
        # JSON doubles the backslashes in a Windows user path; the scan must still see it.
        (self.root / "receipt.json").write_text('{"cwd": "C:' + "\\\\" + "Users" + "\\\\" + 'someone"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Private identifier"):
            verify.structure()

    def test_broken_local_link_is_rejected(self):
        (self.root / "README.md").write_text("[missing](absent.md)", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Broken/escaping"):
            verify.structure()

    def test_undeclared_nested_skill_is_rejected(self):
        extra = self.root / "skills/carrier-pigeon/skills/co-stray"
        extra.mkdir()
        (extra / "SKILL.md").write_text("# Stray\n", encoding="utf-8")
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "unexpected: skills/carrier-pigeon/skills/co-stray/SKILL.md"):
            verify.structure()

    def test_missing_declared_sub_skill_is_rejected(self):
        (self.root / "skills/carrier-pigeon/skills/co-build/SKILL.md").unlink()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "missing: skills/carrier-pigeon/skills/co-build/SKILL.md"):
            verify.structure()

    def test_changed_skill_bytes_are_rejected(self):
        (self.root / "skills/frankenmine/SKILL.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            verify.structure()

    def test_missing_vocabulary_copy_is_rejected_when_the_skill_links_to_it(self):
        skill = self.root / "skills/westack"
        (skill / "SKILL.md").write_text("[evidence vocabulary](references/evidence-vocabulary.md)\n", encoding="utf-8")
        (skill / "references/evidence-vocabulary.md").unlink()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Missing evidence vocabulary copy in westack"):
            verify.structure()

    def test_skill_that_never_links_the_vocabulary_may_omit_it(self):
        (self.root / "skills/westack/references/evidence-vocabulary.md").unlink()
        self.write_manifest()
        self.assertGreater(verify.structure(), 0)

    def test_differing_vocabulary_copy_is_rejected(self):
        # Byte-identical means line endings too.
        (self.root / "skills/frankenmine/references/evidence-vocabulary.md").write_bytes(VOCABULARY.replace(b"\n", b"\r\n"))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "evidence vocabulary.*frankenmine"):
            verify.structure()


class VocabularyRuleTests(unittest.TestCase):
    """A copy is required exactly when the skill's files link to it; any copy present must match shared/."""

    LINK = "[evidence vocabulary]({target})\n"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-vocabulary-test-")
        self.root = Path(self.temp.name)
        (self.root / "shared").mkdir()
        (self.root / "shared/evidence-vocabulary.md").write_bytes(VOCABULARY)
        self.skill = self.root / "skills/fixture"
        (self.skill / "references").mkdir(parents=True)
        (self.skill / "examples").mkdir()
        (self.skill / "SKILL.md").write_text("# Fixture\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        verify.check_vocabulary(self.skill, "fixture", self.root)

    def link_from(self, relative, target):
        (self.skill / relative).write_text(self.LINK.format(target=target), encoding="utf-8")

    def test_skill_that_never_links_the_vocabulary_needs_no_copy(self):
        (self.skill / "references/other.md").write_text("[other](../SKILL.md)\n", encoding="utf-8")
        self.check()

    def test_link_from_skill_md_requires_the_copy(self):
        self.link_from("SKILL.md", "references/evidence-vocabulary.md")
        with self.assertRaisesRegex(ValueError, "Missing evidence vocabulary copy in fixture"):
            self.check()

    def test_link_from_a_nested_file_requires_the_copy(self):
        self.link_from("examples/case.md", "../references/evidence-vocabulary.md")
        with self.assertRaisesRegex(ValueError, "Missing evidence vocabulary copy in fixture"):
            self.check()

    def test_link_from_a_sibling_reference_requires_the_copy(self):
        self.link_from("references/other.md", "evidence-vocabulary.md#observed")
        with self.assertRaisesRegex(ValueError, "Missing evidence vocabulary copy in fixture"):
            self.check()

    def test_link_to_another_file_with_the_same_name_needs_no_copy(self):
        (self.skill / "other").mkdir()
        self.link_from("SKILL.md", "other/evidence-vocabulary.md")
        self.check()

    def test_linked_identical_copy_passes(self):
        self.link_from("SKILL.md", "references/evidence-vocabulary.md")
        (self.skill / "references/evidence-vocabulary.md").write_bytes(VOCABULARY)
        self.check()

    def test_unlinked_identical_copy_passes(self):
        (self.skill / "references/evidence-vocabulary.md").write_bytes(VOCABULARY)
        self.check()

    def test_unlinked_copy_must_still_match_shared(self):
        (self.skill / "references/evidence-vocabulary.md").write_bytes(VOCABULARY + b"local drift\n")
        with self.assertRaisesRegex(ValueError, "evidence vocabulary in fixture differs"):
            self.check()

    def test_linked_copy_must_match_shared(self):
        self.link_from("SKILL.md", "references/evidence-vocabulary.md")
        (self.skill / "references/evidence-vocabulary.md").write_bytes(VOCABULARY.replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "evidence vocabulary in fixture differs"):
            self.check()


# The pre-rename skill name, assembled so that this file does not itself contain it.
OLD_NAME = "e" + "stack"
NEW_NAME = "westack"
DOUBLED_NAME = "w" + NEW_NAME


class StaleNameTests(unittest.TestCase):
    """No published file or path may use the pre-rename name outside a named, numbered allowlist."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-stale-name-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def files(self, contents):
        """{relative path: text} -> the {relative path: Path} mapping that check_stale_names reads."""
        result = {}
        for relative, text in contents.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            result[relative] = path
        return result

    def allow(self, path, rule="3", pattern=None, max=None):
        entry = dict(path=path, rule=rule, why="fixture")
        if pattern is not None:
            entry["pattern"] = pattern
        if max is not None:
            entry["max"] = max
        return [entry]

    def check(self, contents, allowed=(), skip=()):
        verify.check_stale_names(self.files(contents), allowed=list(allowed), skip=tuple(skip))

    def test_clean_files_pass(self):
        self.check({"README.md": "Use " + NEW_NAME + " to repair this.\n"})

    def test_old_name_in_text_is_rejected_in_every_form(self):
        forms = ["Use " + OLD_NAME + " here", OLD_NAME.capitalize() + " is", OLD_NAME.upper() + "_SPEC", "a_" + OLD_NAME + "-x",
                 "`" + OLD_NAME + "`", "(" + OLD_NAME + ")", "/" + OLD_NAME + "/", "an " + OLD_NAME + " example",
                 OLD_NAME + "-mode", "--" + OLD_NAME + " DIR", "first line\n" + OLD_NAME]
        for form in forms:
            with self.subTest(form=form):
                with self.assertRaisesRegex(ValueError, "Stale name"):
                    self.check({"README.md": form + "\n"})

    def test_new_name_in_every_form_passes(self):
        text = "\n".join([NEW_NAME, NEW_NAME.capitalize(), NEW_NAME.upper() + "_SPEC", "a_" + NEW_NAME, "`" + NEW_NAME + "`",
                          "an " + NEW_NAME + " example", NEW_NAME + "-mode", "--" + NEW_NAME + " DIR", "# " + NEW_NAME + " 0.3.1"])
        self.check({"README.md": text + "\n"})

    def test_doubled_prefix_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Doubled prefix"):
            self.check({"README.md": "Use " + DOUBLED_NAME + ".\n"})

    def test_doubled_prefix_is_rejected_even_in_an_allowlisted_file(self):
        contents = {"notes.md": "Pinned record names " + OLD_NAME + " and " + DOUBLED_NAME + ".\n"}
        with self.assertRaisesRegex(ValueError, "Doubled prefix"):
            self.check(contents, allowed=self.allow("notes.md"))

    def test_doubled_prefix_in_a_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Doubled prefix"):
            self.check({"skills/" + DOUBLED_NAME + "/SKILL.md": "Plain text.\n"})

    def test_old_name_in_a_file_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Stale name"):
            self.check({"skills/" + NEW_NAME + "/tests/test_" + OLD_NAME + ".py": "pass\n"})

    def test_old_name_in_a_directory_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Stale name"):
            self.check({"public-overlays/" + OLD_NAME + "/RIGHTS.md": "Plain text.\n"})

    def test_whole_file_allowlist_entry_covers_text_and_path(self):
        name = "record/" + OLD_NAME + "-note.md"
        self.check({name: "Pinned record about " + OLD_NAME + ".\n"}, allowed=self.allow(name, rule="1"))

    def test_allowlist_glob_covers_a_directory(self):
        contents = {"receipts/a.json": '{"tool": "' + OLD_NAME + '"}\n', "receipts/b.json": '{"tool": "' + OLD_NAME + '"}\n'}
        self.check(contents, allowed=self.allow("receipts/*.json", rule="1"))

    def test_allowlist_does_not_cover_other_files(self):
        contents = {"record.md": "Pinned " + OLD_NAME + ".\n", "README.md": "Live text about " + OLD_NAME + ".\n"}
        with self.assertRaisesRegex(ValueError, "README.md"):
            self.check(contents, allowed=self.allow("record.md"))

    def test_pattern_entry_allows_only_the_matching_phrase(self):
        phrase = r"\(then called " + OLD_NAME + r"\)"
        allowed = self.allow("README.md", rule="history", pattern=phrase)
        self.check({"README.md": NEW_NAME + " (then called " + OLD_NAME + ") shipped it.\n"}, allowed=allowed)
        with self.assertRaisesRegex(ValueError, "Stale name"):
            self.check({"README.md": NEW_NAME + " (then called " + OLD_NAME + ") and live " + OLD_NAME + " text.\n"}, allowed=allowed)

    def test_pattern_entry_respects_its_maximum_per_file(self):
        phrase = r"\(then called " + OLD_NAME + r"\)"
        contents = {"README.md": NEW_NAME + " (then called " + OLD_NAME + "), later " + NEW_NAME + " (then called " + OLD_NAME + ").\n"}
        self.check(contents, allowed=self.allow("README.md", rule="history", pattern=phrase))
        with self.assertRaisesRegex(ValueError, "at most 1"):
            self.check(contents, allowed=self.allow("README.md", rule="history", pattern=phrase, max=1))

    def test_allowlist_entry_without_a_keep_rule_is_rejected(self):
        for entry in (dict(path="README.md", why="x"), dict(path="README.md", rule="9", why="x"), dict(path="README.md", rule="3"),
                      dict(rule="3", why="x")):
            with self.subTest(entry=entry):
                with self.assertRaisesRegex(ValueError, "[Aa]llowlist"):
                    self.check({"README.md": "Plain text.\n"}, allowed=[entry])

    def test_skipped_prefix_is_not_scanned_but_everything_else_is(self):
        pending = "skills/" + OLD_NAME + "/"
        self.check({pending + "SKILL.md": "Old " + OLD_NAME + " folder.\n"}, skip=[pending])
        contents = {pending + "SKILL.md": "Old " + OLD_NAME + " folder.\n", "docs/guide.md": OLD_NAME + "\n"}
        with self.assertRaisesRegex(ValueError, "docs/guide.md"):
            self.check(contents, skip=[pending])

    def test_shipped_allowlist_is_well_formed(self):
        self.assertTrue(verify.STALE_NAME_ALLOWED)
        verify.check_stale_names({}, allowed=verify.STALE_NAME_ALLOWED, skip=())  # validates every entry

    def test_structure_rejects_the_old_name_in_a_published_file(self):
        with PublishedFixture() as root:
            (root / "README.md").write_text("Use " + OLD_NAME + " to repair this.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stale name"):
                verify.structure()

    def test_structure_rejects_the_doubled_prefix(self):
        with PublishedFixture() as root:
            (root / "README.md").write_text("Use " + DOUBLED_NAME + " to repair this.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Doubled prefix"):
                verify.structure()


class ManifestVersionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load("generate_manifest")
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-version-test-")
        self.skill = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, text):
        (self.skill / relative).write_text(text, encoding="utf-8")

    def test_frontmatter_version_is_read(self):
        self.write("SKILL.md", '---\nname: frankenmine\nmetadata:\n  version: "0.1.2-portfolio.2"\n---\n# Body\n')
        self.assertEqual(self.manifest.skill_version(self.skill), "0.1.2-portfolio.2")

    def test_version_outside_frontmatter_is_ignored(self):
        self.write("SKILL.md", '---\nname: westack\ndescription: x\n---\n```yaml\n  version: "9.9.9"\n```\n')
        with self.assertRaisesRegex(ValueError, "version"):
            self.manifest.skill_version(self.skill)

    def test_westack_version_comes_from_readme_heading(self):
        self.write("SKILL.md", "---\nname: westack\ndescription: x\n---\n")
        self.write("README.md", "# westack 0.3.1 \u2014 experimental portable skill\n\nText.\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## Unreleased\n\nLater the same day, toward 0.3.1 (unreleased).\n")
        self.assertEqual(self.manifest.skill_version(self.skill), "0.3.1")

    def test_changelog_must_mention_the_readme_version(self):
        self.write("SKILL.md", "---\nname: westack\ndescription: x\n---\n")
        self.write("README.md", "# westack 0.3.1\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## 0.3.0\n\nSee 0.3.11 later.\n")
        with self.assertRaisesRegex(ValueError, "CHANGELOG"):
            self.manifest.skill_version(self.skill)

    def test_missing_version_is_rejected(self):
        self.write("SKILL.md", "---\nname: westack\ndescription: x\n---\n")
        self.write("README.md", "# westack\n")
        with self.assertRaisesRegex(ValueError, "version"):
            self.manifest.skill_version(self.skill)


class BuildTests(unittest.TestCase):
    """The public build stages, checks and only then replaces a skill."""

    def setUp(self):
        self.build = load("build_public")
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-build-test-")
        base = Path(self.temp.name)
        self.root = base / "belt"
        self.outside = base / "outside"
        self.canonical = base / "canonical" / "frankenmine"
        (self.root / "shared").mkdir(parents=True)
        (self.root / "shared/evidence-vocabulary.md").write_bytes(VOCABULARY)
        self.public = self.root / "skills/frankenmine"
        self.public.mkdir(parents=True)
        (self.public / "SKILL.md").write_bytes(b"old public copy\n")
        (self.public / "stale.md").write_bytes(b"removed by a passing build\n")
        files = {
            "SKILL.md": b"---\nname: frankenmine\ndescription: Canonical description.\nmetadata:\n  version: \"1.0\"\n---\n# Fixture\n",
            "references/evidence-vocabulary.md": VOCABULARY,
            "notes.md": b"Canonical notes with a private citation.\n",
            "private/audit-log.txt": b"machine-specific transcript\n",
            "private/fixture.json": b"{\"kept\": true}\n",
        }
        for relative, data in files.items():
            path = self.canonical / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        overlay = self.root / "public-overlays/frankenmine/notes.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_bytes(b"Public notes.\n")
        self.config = dict(format="skill-belt-public-build-1", skills=dict(frankenmine=dict(
            exclude=["private/**", "!private/fixture.json"],
            overlays={"notes.md": dict(base_sha256=sha256(self.canonical / "notes.md"), reason="test redaction")})))
        self.write_config()
        self.before = tree(self.public)

    def tearDown(self):
        link = self.canonical / "linked"
        if os.path.lexists(link):
            os.rmdir(link) if os.name == "nt" else os.unlink(link)
        self.temp.cleanup()

    def write_config(self):
        (self.root / "public-build.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def run_build(self):
        return self.build.build({"frankenmine": self.canonical}, root=self.root)

    def assert_public_copy_unchanged(self):
        self.assertEqual(tree(self.public), self.before)
        self.assertFalse((self.root / self.build.STAGING_NAME).exists(), "staging directory left behind")

    def test_excluded_file_is_absent_from_output(self):
        report = self.run_build()
        self.assertFalse((self.public / "private/audit-log.txt").exists())
        self.assertEqual((self.public / "private/fixture.json").read_bytes(), b"{\"kept\": true}\n")
        self.assertEqual((self.public / "notes.md").read_bytes(), b"Public notes.\n")
        self.assertFalse((self.public / "stale.md").exists())
        changes = report["skills"]["frankenmine"]
        self.assertIn("stale.md", changes["removed"])
        self.assertIn("SKILL.md", changes["changed"])
        self.assertIn("notes.md", changes["added"])
        self.assertFalse((self.root / self.build.STAGING_NAME).exists())

    def test_drifted_overlay_base_is_rejected(self):
        (self.canonical / "notes.md").write_bytes(b"Canonical notes, edited after the overlay was made.\n")
        with self.assertRaisesRegex(ValueError, "drifted"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_private_identifier_in_staged_copy_blocks_replacement(self):
        (self.canonical / "leak.md").write_text("libfile_" + "b" * 32, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Private identifier"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_broken_link_in_staged_copy_blocks_replacement(self):
        # The link target exists canonically but is excluded from the edition.
        (self.canonical / "guide.md").write_text("[log](private/audit-log.txt)", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Broken/escaping"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_vocabulary_must_equal_shared_copy(self):
        (self.canonical / "references/evidence-vocabulary.md").write_bytes(VOCABULARY + b"local drift\n")
        with self.assertRaisesRegex(ValueError, "evidence vocabulary"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_linked_source_directory_is_rejected(self):
        self.outside.mkdir()
        (self.outside / "secret.md").write_text("outside the canonical skill", encoding="utf-8")
        make_dir_link(self.canonical / "linked", self.outside)
        with self.assertRaisesRegex(ValueError, "[Ll]ink"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_stale_exclude_pattern_is_rejected(self):
        self.config["skills"]["frankenmine"]["exclude"].append("renamed-audit/**")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "matches nothing"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_description_override_replaces_only_that_line(self):
        skill = (self.canonical / "SKILL.md").read_bytes()
        base = hashlib.sha256(b"Canonical description.").hexdigest()
        self.config["skills"]["frankenmine"]["description"] = dict(base_sha256=base, text="Public description.")
        self.write_config()
        self.run_build()
        self.assertEqual((self.public / "SKILL.md").read_bytes(), skill.replace(b"Canonical description.", b"Public description."))

    def test_drifted_description_base_is_rejected(self):
        self.config["skills"]["frankenmine"]["description"] = dict(base_sha256="0" * 64, text="Public description.")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "drifted"):
            self.run_build()
        self.assert_public_copy_unchanged()

    def test_adopt_adapt_release_manifest_is_regenerated_without_excluded_files(self):
        # adopt-adapt's own package.py manifest() hashes whatever is present, so the
        # edition's release.json must be rebuilt after private files are excluded.
        canonical = self.canonical.parent / "adopt-adapt"
        package = (b"import hashlib\nfrom pathlib import Path\n\ndef manifest(root):\n"
                   b"    return {'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()\n"
                   b"            for p in sorted(Path(root).rglob('*')) if p.is_file() and p.name != 'release.json'}}\n")
        for relative, data in {"SKILL.md": b"---\nname: adopt-adapt\ndescription: Fixture.\n---\n",
                               "references/evidence-vocabulary.md": VOCABULARY, "scripts/package.py": package,
                               "references/profiles/private.md": b"private recipient\n",
                               "release.json": b"{\"files\": {\"references/profiles/private.md\": \"stale\"}}\n"}.items():
            (canonical / relative).parent.mkdir(parents=True, exist_ok=True)
            (canonical / relative).write_bytes(data)
        self.config["skills"]["adopt-adapt"] = dict(exclude=["references/profiles/private.md"])
        self.write_config()
        self.build.build({"adopt-adapt": canonical}, root=self.root)
        release = json.loads((self.root / "skills/adopt-adapt/release.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(release["files"]), ["SKILL.md", "references/evidence-vocabulary.md", "scripts/package.py"])

    def test_westack_edition_adds_no_generated_files(self):
        # westack 0.3.1 deliberately has no package manifest (the old one moved into provenance/), and its own
        # rename guard scans every published file, so the build must publish exactly the canonical files
        # minus the excludes: no generated manifest.
        canonical = self.canonical.parent / "westack"
        files = {"SKILL.md": b"---\nname: westack\ndescription: Fixture.\n---\n# westack fixture\n",
                 "README.md": "# westack 0.3.1 — fixture\n".encode("utf-8"),
                 "CHANGELOG.md": b"# Changelog\n\n## 0.3.1\n\nFixture.\n",
                 "provenance/old-0.2.0-package-manifest.json": b"{}\n",
                 "tests/results/run.json": b"machine-specific\n"}
        for relative, data in files.items():
            (canonical / relative).parent.mkdir(parents=True, exist_ok=True)
            (canonical / relative).write_bytes(data)
        self.config["skills"]["westack"] = dict(exclude=["tests/results/**"])
        self.write_config()
        self.build.build({"westack": canonical}, root=self.root)
        published = tree(self.root / "skills/westack")
        self.assertEqual(sorted(published), ["CHANGELOG.md", "README.md", "SKILL.md", "provenance/old-0.2.0-package-manifest.json"])
        for relative in published:
            self.assertEqual(published[relative], sha256(canonical / relative), relative)

    def test_canonical_source_is_not_modified(self):
        before = tree(self.canonical)
        self.run_build()
        self.assertEqual(tree(self.canonical), before)


class TimeoutTests(unittest.TestCase):
    def test_default_allows_a_slow_machine(self):
        self.assertGreaterEqual(verify.DEFAULT_TIMEOUT, 600)

    def test_timeout_must_be_positive(self):
        self.assertEqual(verify.positive_seconds("1200"), 1200)
        for text in ("0", "-5"):
            with self.assertRaises(Exception):
                verify.positive_seconds(text)

    def test_partial_output_is_decoded(self):
        self.assertEqual(verify.text_of(b"Ran 3 tests"), "Ran 3 tests")
        self.assertEqual(verify.text_of(None), "")


class CountTests(unittest.TestCase):
    def skipped(self, test=None, reason=None, count=2):
        test = test or verify.WINDOWS_SKIP[0]
        reason = reason or verify.WINDOWS_SKIP[1]
        return f"test_linked ({test}) ... skipped '{reason}'\nRan {count} tests in 1.0s\nOK (skipped=1)\n"

    def test_normal_nonzero_count_passes(self):
        self.assertEqual(verify.unittest_counts("Ran 3 tests in 1.0s\nOK\n")["passed"], 3)

    def test_zero_count_fails(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts("Ran 0 tests in 0.0s\nOK\n")

    def test_all_skipped_fails_even_for_allowlisted_platform(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts(self.skipped(count=1), windows=True)

    def test_exact_windows_limitation_is_visible(self):
        counts = verify.unittest_counts(self.skipped(), windows=True)
        self.assertEqual((counts["passed"], counts["skipped"]), (1, 1))
        self.assertTrue(counts["platform_limitations"])

    def test_same_skip_is_not_allowed_on_linux(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts(self.skipped(), windows=False)

    def test_unexpected_skip_is_rejected(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts(self.skipped(test="Other.test"), windows=True)

    def test_unsupported_reason_is_rejected(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts(self.skipped(reason="not implemented"), windows=True)

    def test_unaccounted_skip_is_rejected(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts("Ran 3 tests in 1.0s\nOK (skipped=1)\n", windows=True)
