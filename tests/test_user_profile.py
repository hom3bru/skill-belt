"""Synthetic broken-copy controls for the local publication deny list."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "belt_user_profile", Path(__file__).resolve().parents[1] / "scripts/user_profile.py")
user_profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(user_profile)


class UserProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / "local.json"
        self.values = dict(user_name="Mira", user_handle="quartz_badger",
                           research_root="D:/Synthetic/Research",
                           palette_home="D:/Synthetic/Palette",
                           plans_dir="/opt/synthetic/plans",
                           cp_home="/opt/synthetic/pigeon",
                           projects_root="D:/Synthetic/Projects", notes="allowed-note-marker")
        self.profile.write_text(json.dumps(self.values), encoding="utf-8-sig")
        self.copy = self.root / "published.md"
        self.copy.write_text("A portable example with placeholders.\n", encoding="utf-8")

    def scan(self, relative="published.md"):
        return user_profile.check_files({relative: self.copy}, self.profile)

    def assert_rejected(self, text, relative="published.md"):
        self.copy.write_text(text, encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with self.assertRaises(ValueError) as caught:
                self.scan(relative)
        self.assertEqual(output.getvalue(), "")
        for value in self.values.values():
            self.assertNotIn(value.casefold(), str(caught.exception).casefold())
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_clean_bom_profile_and_counts(self):
        report = self.scan()
        self.assertEqual(report, dict(configured=True, files_checked=1, patterns_checked=9))

    def test_name_and_handle_broken_copies(self):
        for text in ("Author MIRA.", "@QUARTZ_BADGER", "(mira)", "quartz_badger@example.invalid"):
            with self.subTest(text=text):
                self.assert_rejected(text)

    def test_bounded_tokens_allow_substrings(self):
        self.values["user_name"] = "Mat"
        self.profile.write_text(json.dumps(self.values), encoding="utf-8")
        self.copy.write_text("matters format Matilda xquartz_badgery", encoding="utf-8")
        self.assertTrue(self.scan()["configured"])

    def test_every_path_plain_slashes_json_and_case(self):
        for key in user_profile.PATH_KEYS:
            value = self.values[key]
            for path in (value, value.replace("/", "\\")):
                for text in (path, path.upper(), json.dumps(dict(location=path)),
                             path.replace("/", r"\/")):
                    with self.subTest(key=key, text=text):
                        self.assert_rejected("copied path " + text + "/child")

    def test_derived_user_roots(self):
        for value in ("C:" + "/Users/Mira/work", "C:" + r"\Users\Mira\work", "/Users/Mira/work"):
            self.assert_rejected(json.dumps(value.upper()))

    def test_unicode_json_escaping(self):
        self.assert_rejected(r'{"author":"\u004dira"}')
        self.assert_rejected(r'D:\u002fSynthetic\u002fResearch')

    def test_relative_names_are_scanned(self):
        self.assert_rejected("clean", "docs/QUARTZ_BADGER.md")
        self.assert_rejected("clean", "D:/Synthetic/Research/example.md")

    def test_notes_and_placeholders_permitted(self):
        self.copy.write_text("allowed-note-marker <user_name> <user_handle> "
                             "skill-belt-profile.example.json", encoding="utf-8")
        self.assertTrue(self.scan("skill-belt-profile.example.json")["configured"])

    def test_absent_profile_returns_status(self):
        self.profile.unlink()
        self.assertEqual(self.scan(), dict(configured=False, files_checked=1, patterns_checked=0))

    def test_default_profile_location(self):
        folder = self.root / ".claude"
        folder.mkdir()
        self.profile.replace(folder / user_profile.PROFILE_NAME)
        with patch.object(user_profile.Path, "home", return_value=self.root):
            self.assertTrue(user_profile.check_files({"doc.md": self.copy})["configured"])

    def test_private_filename_always_rejected(self):
        self.profile.unlink()
        for relative in ("skill-belt-profile.json", "nested/SKILL-BELT-PROFILE.JSON",
                         r"nested\skill-belt-profile.json"):
            self.assert_rejected("{}", relative)

    def test_malformed_existing_profiles_fail_redacted(self):
        for text in ("{secret-broken", "[]", "null", '{"user_name":42}',
                     '{"plans_dir":[]}', '{"user_name":"a","user_name":"b"}',
                     '{"notes":NaN}', '{"notes":Infinity}'):
            with self.subTest(text=text):
                self.profile.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "profile is malformed") as caught:
                    self.scan()
                self.assertNotIn(text, str(caught.exception))

    def test_invalid_profile_encoding_and_directory_fail(self):
        self.profile.write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "profile cannot be read"):
            self.scan()
        self.profile.unlink()
        self.profile.mkdir()
        with self.assertRaisesRegex(ValueError, "profile cannot be read"):
            self.scan()

    def test_binary_publication_fails_utf8_contract(self):
        self.copy.write_bytes(b"\xff\xfe\x00")
        with self.assertRaisesRegex(ValueError, "cannot be read as UTF-8"):
            self.scan()

    def test_empty_fields_and_nonstring_notes_ignored(self):
        self.profile.write_text(json.dumps(dict(user_name="", plans_dir=" ", notes={"private": 5})),
                                encoding="utf-8")
        self.assertEqual(self.scan()["patterns_checked"], 0)


if __name__ == "__main__":
    unittest.main()
