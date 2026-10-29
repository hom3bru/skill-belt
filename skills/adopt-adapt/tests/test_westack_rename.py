"""Rename guard (2026-10-28). The recipient skill once called by the retired name is now westack, because a
separate public project owns the retired names. A plain find-and-replace would turn westack into a doubled
prefix, so this guard scans the live files for the retired name and for the doubled prefix, and fails on any
hit outside an explicit allowlist. Each allowlist entry cites its keep rule:

  1  receipts, logs, archives, engineering records and historical records of what ran under the old name
  2  changelog entries for versions released before the rename, and the entry that records the rename
  3  hash-pinned inputs (none in this skill)
  4  wire identifiers that feed hashes or stored IDs (none in this skill)
  5  the other, unrelated public project and its skills (none in this skill)
  6  real directories on this machine whose names still carry the old name

The retired name is built from parts so that this file carries no hit itself."""
from pathlib import Path
import re
import tempfile
import unittest

from test_aa import aa

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]  # the git checkout, when this skill is tested in place rather than installed
OLD = "e" + "stack"
RETIRED = re.compile(rf"(?<![A-Za-z0-9]){OLD}", re.IGNORECASE)
DOUBLED = re.compile("w" + "w" + "e" + "stack", re.IGNORECASE)  # what a naive replace of OLD with westack produces

# Keep rule 6: directories that exist on disk under their old names (the build copies kept in the RSS Radar data folder).
REAL_PATHS = re.compile(rf"\.data/(?:{OLD}-frankenmine-2026-10-26/{OLD}|{OLD}-build-2026-10-26/{OLD}|frankenmine-{OLD}-2026-10-26/frankenmine)")

# (path relative to its root, text that may stay or None for any, keep rule, reason)
ALLOWED = (
    ("CHANGES.md", None, 2, "entries for released versions, and the entry that records the rename"),
    ("references/historical-findings.md", None, 1, "private archive of past-run records"),
    ("references/profiles/local-roots.json", REAL_PATHS, 6, "root hints that name build copies which exist under the old name"),
    ("evals/trigger-evals.json", REAL_PATHS, 6, "a routing query that quotes a real path"),
)
# Repository files outside the skill directory (present only in a checkout).
ALLOWED_REPO = (
    ("ENGINEERING-RECORD.md", None, 1, "engineering record of work done under the old name"),
)
REPO_LIVE = ("README.md", "compat", "tools")  # scanned when present; research/ holds receipts and is not scanned


def files_under(root, only=None):
    root = Path(root)
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or "__pycache__" in rel.parts or path.suffix in {".pyc", ".pyo"} or ".git" in rel.parts:
            continue
        if only is not None and rel.parts[0] not in only:
            continue
        yield rel.as_posix(), path


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None  # binary content carries no prose


def scan(root, allowed, only=None):
    """(retired-name hits outside the allowlist, doubled-prefix hits anywhere) as 'file:line: text' strings."""
    rules = {rel: pattern for rel, pattern, _rule, _why in allowed}
    retired, doubled = [], []
    for rel, path in files_under(root, only):
        if RETIRED.search(rel) and rel not in rules:
            retired.append(f"{rel}: the file name carries the retired name")
        text = read_text(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if DOUBLED.search(line):
                doubled.append(f"{rel}:{number}: {line.strip()[:120]}")
            if rel in rules and rules[rel] is None:
                continue
            checked = rules[rel].sub("", line) if rel in rules else line
            if RETIRED.search(checked):
                retired.append(f"{rel}:{number}: {line.strip()[:120]}")
    return retired, doubled


def live_scan():
    retired, doubled = scan(ROOT, ALLOWED)
    if (REPO / "ENGINEERING-RECORD.md").is_file():
        more_retired, more_doubled = scan(REPO, ALLOWED_REPO, only=set(REPO_LIVE) | {"ENGINEERING-RECORD.md"})
        retired += more_retired
        doubled += more_doubled
    return retired, doubled


class RenameGuardTests(unittest.TestCase):
    def test_no_retired_name_outside_the_allowlist(self):
        retired, _ = live_scan()
        self.assertEqual(retired, [], "the retired name survives outside the allowlist")

    def test_no_doubled_prefix_anywhere(self):
        _, doubled = live_scan()
        self.assertEqual(doubled, [], "a naive replace produced the doubled prefix")

    def test_every_allowlist_entry_cites_a_keep_rule(self):
        for rel, _pattern, rule, why in ALLOWED + ALLOWED_REPO:
            self.assertIn(rule, range(1, 7), rel)
            self.assertTrue(why.strip(), rel)

    def test_recipient_profile_is_renamed_and_routable(self):
        profiles = ROOT / "references" / "profiles"
        self.assertTrue((profiles / "westack.md").is_file())
        self.assertFalse((profiles / f"{OLD}.md").exists())
        self.assertIn("westack", aa.known_profiles())
        self.assertNotIn(OLD, aa.known_profiles())
        description = next(line for line in (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines() if line.startswith("description:"))
        self.assertIn("westack", description)


class ScannerTests(unittest.TestCase):
    """The scanner itself, run against a planted copy: it must catch what a rename can leave or break."""
    def plant(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for rel, text in files.items():
            target = Path(temp.name) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return temp.name

    def test_flags_a_planted_retired_name_at_any_casing_and_position(self):
        root = self.plant({"a.md": f"use {OLD} here\n", "b.md": f"# {OLD.title()}\n", "c.json": f'{{"profile": "{OLD}"}}\n',
                           "d.py": f"x = '{OLD.upper()}_ROOT'\n", "e.md": f"path/{OLD}-copy\n"})
        retired, doubled = scan(root, ())
        self.assertEqual(sorted(hit.split(":")[0] for hit in retired), ["a.md", "b.md", "c.json", "d.py", "e.md"])
        self.assertEqual(doubled, [])

    def test_flags_a_retired_file_name(self):
        retired, _ = scan(self.plant({f"references/profiles/{OLD}.md": "text\n"}), ())
        self.assertEqual(len(retired), 1)
        self.assertIn("file name", retired[0])

    def test_leaves_the_new_name_alone_and_flags_the_doubled_prefix(self):
        root = self.plant({"ok.md": "westack and Westack-build and skills/westack\n", "bad.md": "w" + "westack here\n"})
        retired, doubled = scan(root, ())
        self.assertEqual(retired, [])
        self.assertEqual([hit.split(":")[0] for hit in doubled], ["bad.md"])

    def test_allowlist_masks_only_the_declared_text(self):
        real = f"C:/x/.data/{OLD}-frankenmine-2026-10-26/{OLD}"
        root = self.plant({"keep.json": f'{{"p": "{real}"}}\n', "mixed.json": f'{{"p": "{real}", "n": "{OLD}"}}\n',
                           "any.md": f"{OLD}\n"})
        allowed = (("keep.json", REAL_PATHS, 6, "real path"), ("mixed.json", REAL_PATHS, 6, "real path"), ("any.md", None, 1, "record"))
        retired, _ = scan(root, allowed)
        self.assertEqual([hit.split(":")[0] for hit in retired], ["mixed.json"])

    def test_doubled_prefix_is_flagged_even_in_an_allowlisted_file(self):
        root = self.plant({"any.md": "w" + "westack\n"})
        _, doubled = scan(root, (("any.md", None, 1, "record"),))
        self.assertEqual(len(doubled), 1)


if __name__ == "__main__":
    unittest.main()
