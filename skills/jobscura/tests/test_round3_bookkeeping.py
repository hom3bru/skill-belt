"""Round-three helper discoverability and exact-byte bookkeeping."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RoundThreeBookkeeping(unittest.TestCase):
    def test_j19_helper_index_changelog_and_inventory(self):
        helpers = (ROOT / "references/helpers.md").read_text(encoding="utf-8")
        for marker in ("--as-of YYYY-MM-DD", "--forbid TERM", "direction mismatch", "proficiency",
                       "not comparable", "shingles()"):
            self.assertIn(marker, helpers)
        changes = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("Round-three adopt-adapt additions", changes)
        self.assertIn("J19:", changes)
        inventory = json.loads((ROOT / "package-files.json").read_text(encoding="utf-8"))["files"]
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.name == "package-files.json" or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith("evals/results/"):
                continue
            self.assertEqual(inventory.get(relative), hashlib.sha256(path.read_bytes()).hexdigest(), relative)


if __name__ == "__main__":
    unittest.main()
