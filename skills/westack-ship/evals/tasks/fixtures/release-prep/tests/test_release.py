# release-test-5b8
import pathlib
import re
import tomllib
import unittest

import slugkit

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_package_and_pyproject_agree(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], slugkit.__version__)

    def test_changelog_has_a_dated_entry_for_this_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^## \[%s\] - \d{4}-\d{2}-\d{2}$" % re.escape(slugkit.__version__))


if __name__ == "__main__":
    unittest.main()
