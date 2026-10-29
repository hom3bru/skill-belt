"""Regression guard for the rename of this skill to westack (0.3.1).

The old name survives only where it is a record of what ran, shipped or was decided under that name, or a wire
identifier whose bytes feed a stored hash. Every survivor is listed in KEEP or WIRE with the keep rule it falls
under; any other occurrence of the old name, in a file's text or in its path, fails. So does the double prefix
that a careless find-and-replace produces. Once per file the phrase "westack (then called <old name>)" may
state a historical fact. The old name is assembled from parts, so this file does not contain it and is scanned
like every other file.
"""
import collections
import fnmatch
import hashlib
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OLD = "e" + "stack"
NEW = "w" + OLD
OLD_NAME = re.compile(r"(?<![A-Za-z0-9])" + OLD, re.I)
DOUBLE = re.compile("w" + NEW, re.I)
THEN = NEW + " (then called " + OLD + ")"

# Keep rules of the rename specification.
RULES = {1: "records of what ran, shipped or was decided under the old name",
         2: "release notes for versions released before the rename, and the rename entry",
         3: "hash-pinned inputs",
         4: "wire identifiers that feed hashes or stored IDs",
         5: "the other project's names",
         6: "real paths outside our repositories"}

# Whole files kept as written: (path glob relative to the package root, rule, why).
KEEP = [
    ("CHANGELOG.md", 2, "older entries stay as written (pinned below); the rename entry names the old name"),
    ("provenance/" + OLD + "-0.2.0-package-manifest.json", 3, "the 0.2.0 release manifest, kept under its old version's name"),
    ("provenance/build-inputs.json", 3, "hashed input names inside the research archive"),
    ("provenance/decisions.json", 1, "the twenty donor decisions keep their original wording"),
    ("provenance/source-qualification.json", 1, "source-qualification record; its format string is also a wire identifier"),
    ("provenance/ARTIFACT_REVIEW.md", 1, "dated review of the 2026-10-26 artifacts"),
    ("provenance/continuation.md", 1, "dated continuation findings"),
    ("provenance/lineage.json", 1, "the rename record; it also names the other project (rule 5)"),
    ("tests/acceptance-results.json", 1, "acceptance results name the tests as they ran"),
    ("tests/results/*", 1, "test receipts and run logs"),
]

# Wire identifiers kept inside live files (rule 4): file -> identifiers. Changing one changes every stored
# patch_id or manifest, so records written before the rename would read as stale.
WIRE = {
    "scripts/validate.py": [OLD + "-fingerprint-v1", OLD + "-manifest-v1"],
    "contracts/contract.json": [OLD + "-shape-v1"],
    "contracts/README.md": [OLD + "-fingerprint-v1"],
    "tests/test_hardening.py": [OLD + "-fingerprint-v1"],
}

# SHA-256 of CHANGELOG.md from the first pre-rename entry heading to the end of the file, as released in 0.3.0.
OLD_ENTRIES_MARKER = "## Unreleased — 2026-10-27".encode("utf-8")
OLD_ENTRIES_SHA256 = "8dce1d5ffa374194dc1ce118930c26d20d8f232f01cf2374172e66940c366e51"


def collect(root, repo=None):
    """(label, path) for every file in the package, plus the repository's top-level README and git settings."""
    entries = [(path.relative_to(root).as_posix(), path) for path in sorted(root.rglob("*"))
               if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"]
    if repo is not None:
        entries += [("repo:" + name, repo / name) for name in ("README.md", ".gitattributes", ".gitignore")
                    if (repo / name).is_file()]
    return entries


def scan(entries, keep=KEEP, wire=WIRE):
    """Where the old name appears. Returns violations, files with the double prefix and what the lists matched."""
    found = dict(violations=[], doubles=[], kept=collections.Counter(), wire=collections.Counter(), then=[])
    for label, path in entries:
        text = path.read_bytes().decode("utf-8", "replace")
        if DOUBLE.search(label) or DOUBLE.search(text):
            found["doubles"].append(label)
        owner = next((i for i, (glob, _, _) in enumerate(keep) if fnmatch.fnmatchcase(label, glob)), None)

        def note(line, snippet):
            if owner is None:
                found["violations"].append("%s:%d: %s" % (label, line, snippet))
            else:
                found["kept"][owner] += 1

        if OLD_NAME.search(label):
            note(0, label)
        for token in wire.get(label, []):
            count = text.count(token)
            if count:
                found["wire"][(label, token)] += count
                text = text.replace(token, "<wire-id>")
        if THEN in text:
            found["then"].append(label)
            text = text.replace(THEN, NEW, 1)
        for number, line in enumerate(text.split("\n"), 1):
            for match in OLD_NAME.finditer(line):
                note(number, line[max(0, match.start() - 30):match.end() + 30].strip())
    return found


def repository():
    top = ROOT.parents[1] if len(ROOT.parents) > 1 else None
    return top if top is not None and ROOT.parent.name == "skills" and (top / ".git").exists() else None


class RenameGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = scan(collect(ROOT, repository()))

    def test_old_name_appears_only_where_listed(self):
        violations = self.found["violations"]
        self.assertEqual(violations, [], "old name outside the keep list (%d):\n%s"
                         % (len(violations), "\n".join(violations[:40])))

    def test_no_double_prefix_anywhere(self):
        self.assertEqual(self.found["doubles"], [])

    def test_keep_lists_have_no_stale_entries(self):
        unused = [glob for i, (glob, _, _) in enumerate(KEEP) if not self.found["kept"][i]]
        unused += ["%s: %s" % pair for pair in ((f, t) for f, tokens in WIRE.items() for t in tokens)
                   if not self.found["wire"][pair]]
        self.assertEqual(unused, [], "keep-list entries that match nothing")
        self.assertTrue(all(rule in RULES for _, rule, _ in KEEP))

    def test_changelog_records_the_rename_and_leaves_older_entries_as_released(self):
        data = (ROOT / "CHANGELOG.md").read_bytes()
        cut = data.index(OLD_ENTRIES_MARKER)
        head = data[:cut].decode("utf-8")
        self.assertIn("## 0.3.1 ", head)
        self.assertIn("Renamed from %s to %s; no behaviour change; evidence vocabulary v3." % (OLD, NEW), head)
        self.assertEqual(hashlib.sha256(data[cut:]).hexdigest(), OLD_ENTRIES_SHA256)

    def test_guard_flags_a_planted_old_name_and_a_double_prefix(self):
        files = {"SKILL.md": "name: %s\n" % NEW,
                 "docs/a.md": "one\nsee %s here\n" % OLD,
                 "docs/%s.md" % OLD: "named for it\n",
                 "docs/double.md": "w%s\n" % NEW,
                 "docs/fine.md": "%s, and %s.\n" % (NEW, THEN),
                 "docs/twice.md": "%s and %s\n" % (THEN, THEN),
                 "kept/record.json": "%s\n" % OLD,
                 "listed.py": 'H = "%s-fingerprint-v1"\n' % OLD,
                 "unlisted.py": 'H = "%s-fingerprint-v1"\n' % OLD}
        with tempfile.TemporaryDirectory(prefix=NEW + "-guard-") as temp:
            root = pathlib.Path(temp)
            for name, text in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text, encoding="utf-8", newline="\n")
            found = scan(collect(root), keep=[("kept/*", 1, "test")], wire={"listed.py": [OLD + "-fingerprint-v1"]})
        flagged = sorted(item.split(": ")[0] for item in found["violations"])
        self.assertEqual(flagged, sorted(["docs/a.md:2", "docs/%s.md:0" % OLD, "docs/twice.md:1", "unlisted.py:1"]))
        self.assertEqual(found["doubles"], ["docs/double.md"])
        self.assertEqual(dict(found["kept"]), {0: 1})
        self.assertEqual(dict(found["wire"]), {("listed.py", OLD + "-fingerprint-v1"): 1})
        self.assertEqual(sorted(found["then"]), ["docs/fine.md", "docs/twice.md"])


if __name__ == "__main__":
    unittest.main()
