"""Package identity, deterministic bytes, and private-file rejection controls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jobscura_package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


def short_alias(path):
    """Query an existing fixture alias; never change filesystem settings."""
    if sys.platform != "win32":
        return path
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if not length or length >= len(buffer):
        raise OSError("Temporary fixture alias unavailable")
    return Path(buffer.value)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "toolkit"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))

    def test_package_is_deterministic_and_preserves_compatible_identity(self):
        first, second = self.base / "first.zip", self.base / "second.zip"
        self.assertEqual(package.build(first, self.root), package.build(second, self.root))
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with ZipFile(first) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, set(package.payload(self.root)))
            for path in ("plugin.json", ".codex-plugin/plugin.json"):
                meta = json.loads(archive.read(path))
                self.assertEqual(meta["name"], "application-assistant-workflows")
                self.assertEqual(meta["version"], package.declared_version(self.root))
                self.assertNotIn("email", meta["author"])
            workflows = {n.split("/")[1] for n in names if n.startswith("skills/") and n.endswith("/SKILL.md")}
            # The six original skill names are retained for update continuity; three were added in 0.5.0.
            self.assertLessEqual({"application-intake", "application-tracking", "application-history", "application-writing",
                                  "application-packet", "interview-preparation"}, workflows)
            self.assertEqual(len(workflows), 9)
            self.assertFalse(any(n.startswith("evals/results/") for n in names))

    def test_version_is_declared_once_and_must_agree(self):
        self.assertRegex(package.declared_version(self.root), r"^\d+\.\d+\.\d+$")
        skill = self.root / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace(package.declared_version(self.root), "9.9.9"), encoding="utf-8")
        data = json.loads((self.root / "package-files.json").read_text())
        data["files"]["SKILL.md"] = hashlib.sha256(skill.read_bytes()).hexdigest()
        (self.root / "package-files.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            package.payload(self.root)

    def test_local_eval_results_are_ignored_but_never_inventoried(self):
        results = self.root / "evals" / "results" / "run-1"
        results.mkdir(parents=True)
        (results / "aggregate-result.json").write_text("{}")
        self.assertNotIn("evals/results/run-1/aggregate-result.json", package.payload(self.root))
        data = json.loads((self.root / "package-files.json").read_text())
        data["files"]["evals/results/run-1/aggregate-result.json"] = hashlib.sha256(b"{}").hexdigest()
        (self.root / "package-files.json").write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            package.payload(self.root)

    def test_extra_ignored_private_file_and_changed_public_file_block_packaging(self):
        for name in (".env", "user-context.json", "personal.local.json", "private-context/profile.json"):
            p = self.root / name
            p.parent.mkdir(exist_ok=True)
            p.write_text("fictional private data")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                package.payload(self.root)
            p.unlink()
        (self.root / "README.md").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            package.payload(self.root)

    def test_corrupted_identity_and_private_inventory_are_rejected_even_when_rehashed(self):
        manifest = self.root / "package-files.json"
        data = json.loads(manifest.read_text())
        path = self.root / "plugin.json"
        metadata = json.loads(path.read_text())
        metadata["name"] = "different-plugin"
        path.write_text(json.dumps(metadata))
        data["files"]["plugin.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "identity"):
            package.payload(self.root)
        private = self.root / "user-context.json"
        private.write_text("fictional")
        data["files"]["user-context.json"] = hashlib.sha256(private.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Private"):
            package.payload(self.root)

    def test_short_alias_output_stays_outside_toolkit(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            package.build(short_alias(self.root) / "blocked.zip", self.root)
        self.assertFalse((self.root / "blocked.zip").exists())
        output = short_alias(self.base) / "allowed.zip"
        result = package.build(output, self.root)
        self.assertEqual(result["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_package_never_overwrites_and_rejects_output_inside_toolkit(self):
        output = self.base / "result.zip"
        output.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            package.build(output, self.root)
        self.assertEqual(output.read_bytes(), b"existing")
        with self.assertRaisesRegex(ValueError, "outside"):
            package.build(self.root / "result.zip", self.root)


if __name__ == "__main__":
    unittest.main()
