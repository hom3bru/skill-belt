"""Exercise the optional starter against the actual canonical task contract."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import test_westack as fixtures


class TaskStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-task-start-")
        self.root = pathlib.Path(self.temp.name)
        self.output = self.root / "run/task.json"

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *extra, output=None):
        command = [sys.executable, "-B", str(fixtures.ROOT / "scripts/validate.py"), "init",
            str(output or self.output), "--root", str(self.root), "--goal", "Add bounded CSV import",
            "--revision", "authored-source-v1", "--scope", "local-import", "--patch", "a" * 64,
            "--author", "fixture-author", "--allow-path", "src", *extra]
        return subprocess.run(command, capture_output=True, text=True, timeout=60)

    def test_new_record_uses_existing_contract_without_work_or_approval(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "created-incomplete")
        record = fixtures.v.read_json(self.output)
        self.assertFalse(fixtures.v.check_task(record, self.root))
        self.assertEqual((record["state"], record["completion"], record["verification"]),
                         ("framed", "open", "unverified"))
        self.assertEqual(record["authority"]["allowed_actions"], [])
        self.assertEqual((record["actions"], record["evidence"], record["acceptance"]), ([], [], []))
        self.assertEqual(record["host"]["capabilities"], [])

    def test_explicit_scope_is_recorded_without_authorizing_an_action(self):
        result = self.invoke("--allow-action", "read", "--allow-action", "local-write",
                             "--allow-path", "tests", "--task-mode", "repair", "--size", "tiny")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = fixtures.v.read_json(self.output)
        self.assertEqual(record["authority"]["allowed_paths"], ["src", "tests"])
        self.assertEqual(record["authority"]["allowed_actions"], ["read", "local-write"])
        self.assertEqual(record["actions"], [])
        self.assertEqual(record["mode"], "repair")

    def test_existing_output_is_preserved(self):
        self.assertEqual(self.invoke().returncode, 0)
        before = self.output.read_bytes()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_output_escape_is_rejected_before_creation(self):
        outside = self.root.parent / (self.root.name + "-outside-task.json")
        self.assertNotEqual(self.invoke(output=outside).returncode, 0)
        self.assertFalse(outside.exists())

    def test_unsafe_scope_path_is_rejected(self):
        self.assertNotEqual(self.invoke("--allow-path", "../unrelated").returncode, 0)
        self.assertFalse(self.output.exists())

    def test_invalid_context_hash_is_rejected(self):
        self.assertNotEqual(self.invoke("--patch", "unknown").returncode, 0)
        self.assertFalse(self.output.exists())
