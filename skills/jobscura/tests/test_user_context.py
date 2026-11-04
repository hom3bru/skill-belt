"""Fictional private-context controls. No user files or external services."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jobscura_context", ROOT / "scripts/user_context.py")
context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context)


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


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "context.json"
        self.value = json.loads((ROOT / "context/user-context.example.json").read_text())
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.value), encoding="utf-8")

    def test_explicit_context_and_env_selection_return_data_in_memory(self):
        self.assertEqual(context.load_context(str(self.path), {}), self.value)
        self.assertEqual(context.load_context(environ={"JOBSCURA_CONTEXT_FILE": str(self.path)}), self.value)
        self.assertEqual(context.load_context(str(self.path), {"JOBSCURA_CONTEXT_FILE": "bad"}), self.value)

    def test_missing_selection_does_not_load_example_or_search(self):
        with self.assertRaisesRegex(context.ContextError, "No context selected"):
            context.load_context(environ={})

    def test_missing_file_and_malformed_json_do_not_echo_data_or_path(self):
        for text in (None, "SENSITIVE malformed text", '{"schema_version":1,"schema_version":1}'):
            if text is None:
                self.path.unlink()
            else:
                self.path.write_text(text)
            with self.assertRaises(context.ContextError) as caught:
                context.load_context(str(self.path), {})
            self.assertNotIn("SENSITIVE", str(caught.exception))
            self.assertNotIn(str(self.path), str(caught.exception))

    def test_version_types_permissions_and_credentials_are_rejected(self):
        original = copy.deepcopy(self.value)
        mutations = [("schema_version", 3), ("schema_version", 0), ("schema_version", True),
                     ("schema_version", 10**400), ("profile", []),
                     ("permissions", {"submit": True}), ("api_key", "fictional")]
        for key, value in mutations:
            with self.subTest(key=key, value_type=type(value).__name__):
                self.value = dict(original, **{key: value})
                self.save()
                with self.assertRaises(context.ContextError):
                    context.load_context(str(self.path), {})

    def test_nested_unknown_secret_field_and_blank_required_field_are_rejected(self):
        self.value["profile"]["password"] = "fictional"
        self.save()
        with self.assertRaises(context.ContextError):
            context.load_context(str(self.path), {})
        del self.value["profile"]["password"]
        self.value["preferences"]["timezone"] = " "
        self.save()
        with self.assertRaises(context.ContextError):
            context.load_context(str(self.path), {})

    def test_boundary_is_inclusive_configuration_and_not_an_action_grant(self):
        for boundary in (0, 3.5, 5):
            self.value["preferences"]["routing"]["main_max_gap"] = boundary
            self.save()
            self.assertEqual(context.load_context(str(self.path), {})["preferences"]["routing"]["main_max_gap"], boundary)
        for boundary in (-1, 5.1, True, "3.5", float("nan"), float("inf")):
            self.value["preferences"]["routing"]["main_max_gap"] = boundary
            self.save()
            with self.assertRaises(context.ContextError):
                context.load_context(str(self.path), {})

    def test_source_references_are_never_opened(self):
        self.value["materials"][0]["reference"] = str(self.path.parent / "does-not-exist.txt")
        self.value["tracker"]["reference"] = "https://example.invalid/do-not-fetch"
        self.save()
        opened = []
        original = Path.open
        def observed(path, *args, **kwargs):
            opened.append(path.resolve())
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", observed):
            context.load_context(str(self.path), {})
        self.assertEqual(set(opened), {self.path.resolve(), (ROOT / "context/user-context.schema.json").resolve()})

    def test_relative_paths_oversized_and_linked_files_are_rejected(self):
        with self.assertRaisesRegex(context.ContextError, "absolute"):
            context.load_context("context.json", {})
        self.path.write_bytes(b" " * (context.MAX_BYTES + 1))
        with self.assertRaises(context.ContextError):
            context.load_context(str(self.path), {})
        self.save()
        # Simulate platform metadata; exercise the same branch used for symlinks/junctions.
        original = Path.lstat
        def linked(path, *args, **kwargs):
            if path == self.path:
                class Link:
                    st_mode = 0
                    st_file_attributes = 0x400
                return Link()
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", linked):
            with self.assertRaisesRegex(context.ContextError, "Linked"):
                context.load_context(str(self.path), {})

    def test_context_inside_installed_tree_and_git_root_is_rejected(self):
        with self.assertRaisesRegex(context.ContextError, "outside"):
            context.load_context(str(ROOT / "context/user-context.example.json"), {})
        fake = self.path.parent / "repository"
        installed = fake / "skills/jobscura"
        installed.mkdir(parents=True)
        (fake / ".git").mkdir()
        local = fake / "ignored-context.json"
        local.write_text(json.dumps(self.value))
        with patch.object(context, "ROOT", installed):
            with self.assertRaisesRegex(context.ContextError, "outside"):
                context.load_context(str(local), {})

    def test_short_alias_toolkit_root_rejects_internal_context_before_read(self):
        installed = self.path.parent / "alias-toolkit"
        installed.mkdir()
        private = installed / "context.json"
        private.write_text(json.dumps(self.value))
        with patch.object(context, "ROOT", short_alias(installed)):
            with patch.object(Path, "open", side_effect=AssertionError("Forbidden context must not be opened")):
                with self.assertRaisesRegex(context.ContextError, "outside"):
                    context.load_context(str(private.resolve()), {})

    def test_version_one_files_still_load_but_cannot_carry_version_two_fields(self):
        v1 = copy.deepcopy(self.value)
        v1["schema_version"] = 1
        for key in ("monitoring", "search"):
            v1["preferences"].pop(key)
        self.value = v1
        self.save()
        self.assertEqual(context.load_context(str(self.path), {})["schema_version"], 1)
        self.value["preferences"]["monitoring"] = {"dated_check_days": 1}
        self.save()
        with self.assertRaisesRegex(context.ContextError, "schema_version 2"):
            context.load_context(str(self.path), {})

    def test_monitoring_bounds_and_defaults(self):
        merged = context.monitoring(context.load_context(str(self.path), {}))
        self.assertEqual(merged["reminder_windows_days"], [14, 7, 3, 1, 0])
        self.assertEqual(context.monitoring(None), context.MONITORING_DEFAULTS)
        for key, value in (("dated_check_days", 0), ("undated_check_days", 31), ("reminder_windows_days", [7, 7]),
                           ("reminder_windows_days", [-1]), ("shortlist_size", 2.5), ("long_open_days", True),
                           ("permission_to_send", True)):
            with self.subTest(key=key, value=value):
                broken = copy.deepcopy(self.value)
                broken["preferences"]["monitoring"][key] = value
                self.path.write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(context.ContextError):
                    context.load_context(str(self.path), {})

    def test_search_preferences_are_closed_and_typed(self):
        for change in ({"work_arrangements": ["anywhere"]}, {"min_base_pay": {"amount": 1, "currency": "US", "period": "year"}},
                       {"min_base_pay": {"amount": -5, "currency": "USD", "period": "year"}}, {"auto_apply": True}):
            with self.subTest(change=change):
                broken = copy.deepcopy(self.value)
                broken["preferences"]["search"].update(change)
                self.path.write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(context.ContextError):
                    context.load_context(str(self.path), {})

    def test_operating_system_alias_above_the_file_is_allowed(self):
        # macOS keeps temporary folders under /var -> /private/var; redirected profiles do the same.
        real = Path(self.temp.name) / "real-folder"
        real.mkdir()
        target = real / "context.json"
        target.write_text(json.dumps(self.value), encoding="utf-8")
        alias = Path(self.temp.name) / "alias-folder"
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(real), str(alias))
        else:
            alias.symlink_to(real, target_is_directory=True)
        self.assertEqual(context.load_context(str(alias / "context.json"), {}), self.value)

    def test_alias_into_the_toolkit_is_still_rejected_after_resolution(self):
        installed = Path(self.temp.name) / "toolkit"
        installed.mkdir()
        (installed / "context.json").write_text(json.dumps(self.value), encoding="utf-8")
        alias = Path(self.temp.name) / "innocent-looking"
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(installed), str(alias))
        else:
            alias.symlink_to(installed, target_is_directory=True)
        with patch.object(context, "ROOT", installed):
            with self.assertRaisesRegex(context.ContextError, "outside"):
                context.load_context(str(alias / "context.json"), {})

    def test_cloud_placeholder_reparse_point_is_an_ordinary_file(self):
        import stat as stat_module
        original = Path.lstat
        def placeholder(path, *args, **kwargs):
            if path == self.path:
                class Info:
                    st_mode = stat_module.S_IFREG | 0o644
                    st_file_attributes = 0x400
                    st_reparse_tag = 0x9000001A  # cloud files: not a name surrogate
                return Info()
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", placeholder):
            self.assertEqual(context.load_context(str(self.path), {}), self.value)

    def test_timezone_status_never_guesses(self):
        self.assertIn(context.timezone_status("Etc/UTC"), {"available", "unavailable_in_host", "zoneinfo_unavailable"})
        self.assertNotEqual(context.timezone_status("Nowhere/Invented_Zone"), "available")

    def test_cli_only_emits_status_and_section_names(self):
        self.value["profile"]["display_name"] = "SENSITIVE candidate"
        self.save()
        run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/user_context.py"), "--context", str(self.path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "validated")
        self.assertIn(json.loads(run.stdout)["timezone_status"], {"available", "unavailable_in_host", "zoneinfo_unavailable"})
        self.assertNotIn("SENSITIVE", run.stdout + run.stderr)
        self.assertNotIn(str(self.path), run.stdout + run.stderr)
        self.path.write_text("SENSITIVE invalid")
        run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/user_context.py"), "--context", str(self.path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stderr)["status"], "context_not_loaded")
        self.assertNotIn("SENSITIVE", run.stderr)


if __name__ == "__main__":
    unittest.main()
