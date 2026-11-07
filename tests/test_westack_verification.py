"""Publication controls for the sibling westack stack and its authored gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "westack_collection_verify", Path(__file__).resolve().parents[1] / "scripts/verify.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class WestackVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.names = verify.SKILLS + ("westack-build", "westack-eval")
        for name in self.names:
            self.write("skills/" + name + "/SKILL.md", "# Portable fixture\n")
        for parent, children in verify.SUB_SKILLS.items():
            for child in children:
                self.write("skills/" + parent + "/skills/" + child + "/SKILL.md", "# Nested fixture\n")
        self.write("shared/evidence-vocabulary.md", "# Vocabulary\n")
        self.write("skills/westack/stack.json", json.dumps(dict(format="westack-stack-1", skills=[
            dict(name="build", status="built", invocation="model"),
            dict(name="eval", status="built", invocation="manual"),
            dict(name="future", status="planned", invocation="model"),
            dict(name="folded", status="built", invocation="folded", into="build")])))
        self.manifest()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def manifest(self, names=None):
        rows = []
        for name in self.names if names is None else names:
            files = verify.source_files(self.root / "skills" / name)
            rows.append(dict(name=name, files={rel: hashlib.sha256(path.read_bytes()).hexdigest()
                                               for rel, path in files.items()}))
        self.write("skills-manifest.json", json.dumps(dict(skills=rows)))

    def structure(self):
        with patch.object(verify, "ROOT", self.root), patch.object(verify.user_profile, "check_files"):
            return verify.structure()

    def test_declared_siblings_and_existing_nested_skills_pass(self):
        self.assertEqual(verify.snapshot_names(self.root), self.names)
        self.assertGreater(self.structure(), 0)

    def test_missing_declared_sibling_fails(self):
        (self.root / "skills/westack-build/SKILL.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing.*westack-build"):
            self.structure()

    def test_undeclared_sibling_fails(self):
        self.write("skills/westack-future/SKILL.md", "# Unexpected\n")
        with self.assertRaisesRegex(ValueError, "unexpected.*westack-future"):
            self.structure()

    def test_nested_westack_child_fails(self):
        self.write("skills/westack/skills/westack-build/SKILL.md", "# Wrong layout\n")
        with self.assertRaisesRegex(ValueError, "unexpected.*westack/skills"):
            self.structure()

    def test_manifest_must_include_siblings(self):
        self.manifest(verify.SKILLS)
        with self.assertRaisesRegex(ValueError, "manifest identities"):
            self.structure()

    def test_duplicate_manifest_identity_fails(self):
        self.manifest(self.names + ("westack-build",))
        with self.assertRaisesRegex(ValueError, "manifest identities"):
            self.structure()

    def test_changed_sibling_bytes_fail_manifest(self):
        self.write("skills/westack-build/SKILL.md", "# Changed sibling\n")
        with self.assertRaisesRegex(ValueError, "snapshot mismatch: westack-build"):
            self.structure()

    def test_sibling_vocabulary_is_checked(self):
        self.write("skills/westack-build/references/evidence-vocabulary.md", "# Different vocabulary\n")
        self.manifest()
        with self.assertRaisesRegex(ValueError, "vocabulary in westack-build differs"):
            self.structure()

    def test_legacy_router_without_stack_keeps_seven_snapshots(self):
        (self.root / "skills/westack/stack.json").unlink()
        for name in ("westack-build", "westack-eval"):
            (self.root / "skills" / name / "SKILL.md").unlink()
        self.manifest(verify.SKILLS)
        self.assertEqual(verify.snapshot_names(self.root), verify.SKILLS)
        self.assertGreater(self.structure(), 0)

    def test_gates_cover_packages_minimum_core_and_present_suites(self):
        self.write("skills/westack-build/tests/test_sample.py", "# Suite fixture\n")
        calls = []
        verify.westack_checks(lambda *args: calls.append(args), self.root / "results", self.root)
        labels = [call[0] for call in calls]
        self.assertEqual(set(labels), {"westack-package", "westack-build-package", "westack-eval-package",
                                       "westack-minimum-core", "westack-tests", "westack-build-tests"})
        child = next(call for call in calls if call[0] == "westack-build-tests")
        self.assertIn("unittest", child[1])
        self.assertEqual(child[2], self.root / "skills/westack-build")
        minimum = next(call for call in calls if call[0] == "westack-minimum-core")
        self.assertIn("check", minimum[1])

    def test_json_suite_counts_require_nonempty_all_passing(self):
        self.assertEqual(verify.json_test_counts('{"collected":7,"passed":7,"failed":0,"skipped":0}'),
                         dict(collected=7, passed=7, skipped=0))
        for counts in (dict(total=0, passed=0, failed=0, skipped=0),
                       dict(total=7, passed=6, failed=0, skipped=1),
                       dict(total=7, passed=6, failed=1, skipped=0),
                       dict(total=7, passed=6, failed=0, skipped=0)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                verify.json_test_counts(json.dumps(counts))

    def test_westack_unittest_skips_fail_without_platform_exceptions(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts("test_x (suite.Case.test_x) ... skipped 'reason'\n"
                                   "Ran 2 tests in 0.1s\nOK (skipped=1)\n")

    def test_zero_subskill_suite_fails(self):
        with self.assertRaises(ValueError):
            verify.unittest_counts("Ran 0 tests in 0.1s\nOK\n")

    def test_legacy_gates_run_only_router_package_and_tests(self):
        (self.root / "skills/westack/stack.json").unlink()
        calls = []
        verify.westack_checks(lambda *args: calls.append(args), self.root / "results", self.root)
        self.assertEqual([call[0] for call in calls], ["westack-package", "westack-tests"])

    def test_renamed_wire_location_and_bounded_provenance_exceptions(self):
        wire = verify._OLD + "-fingerprint-v1"
        relative = "skills/westack/scripts/evidence.py"
        self.write(relative, wire)
        verify.check_stale_names({relative: self.root / relative})
        self.write(relative, wire + " " + verify._OLD + " unintended live name")
        with self.assertRaisesRegex(ValueError, "rename problem"):
            verify.check_stale_names({relative: self.root / relative})
        donor = "skills/westack-eval/provenance/donors.json"
        self.write(donor, "singularityhacker/" + verify._OLD.capitalize())
        verify.check_stale_names({donor: self.root / donor})
        self.write(donor, (verify._OLD + "-1.0-capability-map ") * 5)
        with self.assertRaisesRegex(ValueError, "at most 4"):
            verify.check_stale_names({donor: self.root / donor})

    def rights_history(self):
        return (verify._OLD + " remains a separate standalone workflow.\n"
                + verify._OLD.capitalize() + " adapts ideas only and copies no donor text.\n"
                + "On 2026-10-28 " + verify._OLD + " was renamed westack (see lineage.json).\n")

    def test_rights_history_is_allowed_in_snapshot_and_overlay(self):
        for relative in ("skills/westack/provenance/RIGHTS.md",
                         "public-overlays/westack/provenance/RIGHTS.md"):
            with self.subTest(relative=relative):
                self.write(relative, self.rights_history())
                verify.check_stale_names({relative: self.root / relative})

    def test_rights_history_exceptions_reject_broken_copies(self):
        for relative in ("skills/westack/provenance/RIGHTS.md",
                         "public-overlays/westack/provenance/RIGHTS.md"):
            extras = (verify._OLD + " new live instruction\n", "w" + "w" + verify._OLD + "\n")
            extras += tuple(line + "\n" for line in self.rights_history().splitlines())
            for extra in extras:
                with self.subTest(relative=relative, extra=extra):
                    self.write(relative, self.rights_history() + extra)
                    with self.assertRaisesRegex(ValueError, "rename problem"):
                        verify.check_stale_names({relative: self.root / relative})
        relative = "skills/westack/provenance/unreviewed.md"
        self.write(relative, self.rights_history())
        with self.assertRaisesRegex(ValueError, "rename problem"):
            verify.check_stale_names({relative: self.root / relative})


if __name__ == "__main__":
    unittest.main()
