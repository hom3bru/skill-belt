"""Meaningful rejection controls for publication checks and test-count honesty."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("belt_verify", Path(__file__).resolve().parents[1] / "scripts/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-belt-publication-test-")
        self.root = Path(self.temp.name)
        self.previous = verify.ROOT
        verify.ROOT = self.root
        rows = []
        for name in verify.SKILLS:
            path = self.root / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("# Authored fixture\n", encoding="utf-8")
            rows.append(dict(name=name, files={"SKILL.md": hashlib.sha256(path.read_bytes()).hexdigest()}))
        (self.root / "skills-manifest.json").write_text(json.dumps(dict(skills=rows)), encoding="utf-8")

    def tearDown(self):
        verify.ROOT = self.previous
        self.temp.cleanup()

    def test_clean_published_snapshot_passes(self):
        self.assertGreater(verify.structure(), 0)

    def test_private_identifier_is_rejected(self):
        # Construct an obviously synthetic identifier without putting one in
        # the public source tree that the publication scanner itself reads.
        (self.root / "README.md").write_text("libfile_" + "a" * 32, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Private identifier"):
            verify.structure()

    def test_broken_local_link_is_rejected(self):
        (self.root / "README.md").write_text("[missing](absent.md)", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Broken/escaping"):
            verify.structure()

    def test_changed_skill_bytes_are_rejected(self):
        (self.root / "skills/frankenmine/SKILL.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            verify.structure()


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
