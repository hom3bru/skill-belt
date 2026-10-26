import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts" / "package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
aa_spec = importlib.util.spec_from_file_location("documented_aa", ROOT / "scripts" / "aa.py")
aa = importlib.util.module_from_spec(aa_spec)
aa_spec.loader.exec_module(aa)


class ParsedCommand(BaseException):
    def __init__(self, namespace):
        self.namespace = namespace


def check_documented_aa_commands(root):
    prefix = "python -B <skill>/scripts/aa.py "
    guide = (root / "references" / "records.md").read_text(encoding="utf-8")
    examples = [line.strip()[len(prefix):] for line in guide.splitlines()
                if line.strip().startswith(prefix)]
    if not examples:
        raise AssertionError("No documented aa.py commands selected")

    original_parse = aa.argparse.ArgumentParser.parse_args

    def parse_without_dispatch(parser, *args, **kwargs):
        # Use argparse itself, then stop before aa.main can load records or write files.
        raise ParsedCommand(original_parse(parser, *args, **kwargs))

    parsed = []
    for example in examples:
        diagnostics = io.StringIO()
        try:
            with contextlib.redirect_stderr(diagnostics), mock.patch.object(
                    aa.argparse.ArgumentParser, "parse_args", parse_without_dispatch):
                aa.main(shlex.split(example))
        except ParsedCommand as result:
            parsed.append(result.namespace)
        except SystemExit as error:
            raise AssertionError(f"Documented aa.py command does not parse: {example}\n"
                                 f"{diagnostics.getvalue()}") from error
        else:
            raise AssertionError(f"Parser interception was not reached: {example}")

    missing = {"validate", "render", "check-output"} - {args.command for args in parsed}
    if missing:
        raise AssertionError("Missing documented aa.py commands: " + ", ".join(sorted(missing)))
    return parsed


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "canonical"
        shutil.copytree(ROOT, self.source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        (self.source / "release.json").write_text(json.dumps(package.manifest(self.source)), encoding="utf-8")

    def test_install_and_exact_rollback(self):
        destination = self.root / "skills" / "adopt-adapt"
        package.install(self.source, destination)
        self.assertEqual(package.verify(destination), package.verify(self.source))
        package.uninstall(destination, self.source / "release.json")
        self.assertFalse(destination.exists())

    def test_existing_destination_refused(self):
        destination = self.root / "adopt-adapt"; destination.mkdir()
        (destination / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overwrite"): package.install(self.source, destination)
        self.assertEqual((destination / "user.txt").read_text(), "keep")

    def test_modified_install_not_deleted(self):
        destination = self.root / "adopt-adapt"; package.install(self.source, destination)
        (destination / "SKILL.md").write_text("user edit", encoding="utf-8")
        with self.assertRaises(ValueError): package.uninstall(destination, self.source / "release.json")
        self.assertTrue(destination.exists())

    def test_extra_file_not_deleted(self):
        destination = self.root / "adopt-adapt"; package.install(self.source, destination)
        (destination / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError): package.uninstall(destination, self.source / "release.json")
        self.assertTrue((destination / "user.txt").exists())

    def test_wrong_destination_refused(self):
        with self.assertRaises(ValueError): package.install(self.source, self.root / "adopt-adapt-v2")

    def test_missing_required_reference_fails(self):
        (self.source / "references" / "routing.md").unlink()
        with self.assertRaises(ValueError): package.verify(self.source)
        with self.assertRaises(ValueError): self.write_manifest()

    def test_stripped_skill_body_fails_even_regenerated_manifest(self):
        (self.source / "SKILL.md").write_text("---\nname: adopt-adapt\n---\n", encoding="utf-8")
        with self.assertRaises(ValueError): self.write_manifest()

    def test_protected_rule_mutations_fail_approved_manifest(self):
        original = (self.source / "SKILL.md").read_text(encoding="utf-8")
        for needle in ("No new paid elements", "Queue, not shortlist", "Untrusted input", "No history leakage", "Self-change brake"):
            line = next(x for x in original.splitlines(True) if needle in x)
            (self.source / "SKILL.md").write_text(original.replace(line, ""), encoding="utf-8")
            with self.subTest(rule=needle), self.assertRaises(ValueError): package.verify(self.source)
        (self.source / "SKILL.md").write_text(original, encoding="utf-8")

    def test_doc_and_script_changes_fail_approved_manifest(self):
        for relative in ("references/routing.md", "scripts/aa.py"):
            path = self.source / relative
            original = path.read_bytes(); path.write_bytes(original + b"\nchanged\n")
            with self.assertRaises(ValueError): package.verify(self.source)
            path.write_bytes(original)

    def test_local_reference_links_resolve(self):
        for doc in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((doc.parent / target.split("#")[0]).is_file(), f"{doc}: {target}")

    def test_documented_aa_commands_parse(self):
        parsed = check_documented_aa_commands(self.source)
        self.assertEqual({args.command for args in parsed}, {"validate", "render", "check-output"})

    def test_documented_aa_command_typo_fails_after_manifest_regeneration(self):
        doc = self.source / "references" / "records.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace(
            "scripts/aa.py validate ", "scripts/aa.py validatx "), encoding="utf-8")
        self.write_manifest()
        package.verify(self.source)
        with self.assertRaisesRegex(AssertionError, "validatx"):
            check_documented_aa_commands(self.source)

    def test_documented_aa_flag_typo_fails(self):
        doc = self.source / "references" / "records.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace(
            "render <run-dir>/run.json --output ", "render <run-dir>/run.json --outpot "), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "outpot"):
            check_documented_aa_commands(self.source)

    def test_documented_aa_empty_selection_fails(self):
        doc = self.source / "references" / "records.md"
        doc.write_text("\n".join(line for line in doc.read_text(encoding="utf-8").splitlines()
                                 if not line.startswith("python -B <skill>/scripts/aa.py ")), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "No documented aa.py commands"):
            check_documented_aa_commands(self.source)

    def test_documented_aa_missing_required_example_fails(self):
        doc = self.source / "references" / "records.md"
        doc.write_text("\n".join(line for line in doc.read_text(encoding="utf-8").splitlines()
                                 if not line.startswith("python -B <skill>/scripts/aa.py check-output ")), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "Missing documented aa.py commands: check-output"):
            check_documented_aa_commands(self.source)

    def test_documented_aa_commands_do_not_dispatch(self):
        with mock.patch.object(aa, "load", side_effect=AssertionError("Command dispatch reached")) as load:
            parsed = check_documented_aa_commands(self.source)
        self.assertEqual(len(parsed), 3)
        load.assert_not_called()

    def test_documented_aa_parser_interception_must_be_reached(self):
        with mock.patch.object(aa, "main", return_value=0):
            with self.assertRaisesRegex(AssertionError, "Parser interception was not reached"):
                check_documented_aa_commands(self.source)

    def test_cli_manifest_writes_stable_lf_bytes(self):
        result = subprocess.run([sys.executable, '-B', str(self.source / 'scripts/package.py'), 'manifest', str(self.source)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'\r\n', (self.source / 'release.json').read_bytes())
        self.assertEqual(package.verify(self.source)['version'], package.VERSION)


if __name__ == "__main__":
    unittest.main()
