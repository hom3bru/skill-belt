"""The stack manifest (stack.json): well formed, and in agreement with the router's section 5 table and the
core fallbacks it names. The manifest is the one list of sub-skills, so adding one is an edit to it. Whether
the skill folders on disk match it is checked by tools/tests/test_skills_stack.py, which can see them all."""
import json
import re
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
STACK = json.loads((ROOT / "stack.json").read_text(encoding="utf-8"))
ENTRIES = {entry["name"]: entry for entry in STACK["skills"]}
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
BODY = SKILL[re.match(r"^---\n(.*?)\n---\n", SKILL, re.S).end():]
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STATUSES = {"built", "planned"}
INVOCATIONS = {"model", "manual", "folded", "library"}
ENTRY_KEYS = {"name", "status", "invocation", "wave", "fallback", "outside_ceiling", "excludes", "into", "path"}


def table_rows(text):
    return {cells[0]: cells[1] for cells in (
        [c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
        if line.startswith("|") and "---" not in line) if len(cells) >= 2}


def row(prefix):
    return next(v for k, v in table_rows(BODY).items() if k.startswith(prefix))


def listed(cell):
    return {x.strip() for x in cell.split(",")}


def names(status, invocation):
    return {e["name"] for e in STACK["skills"] if e["status"] == status and e["invocation"] == invocation}


def skills():
    return [e for e in STACK["skills"] if e["invocation"] in {"model", "manual"}]


class ManifestShapeTests(unittest.TestCase):
    def test_format_and_unique_names(self):
        self.assertEqual(STACK["format"], "westack-stack-1")
        listed_names = [e["name"] for e in STACK["skills"]]
        self.assertEqual(len(listed_names), len(set(listed_names)), "one entry per name")
        for name in listed_names:
            self.assertRegex(name, NAME)

    def test_every_entry_has_a_known_status_invocation_and_wave(self):
        for entry in STACK["skills"]:
            with self.subTest(entry=entry["name"]):
                self.assertLessEqual(set(entry), ENTRY_KEYS)
                self.assertIn(entry["status"], STATUSES)
                self.assertIn(entry["invocation"], INVOCATIONS)
                self.assertIn("wave", entry, "wave is null for a skill no source has scheduled, never absent")
                wave = entry["wave"]
                self.assertTrue(wave is None or (isinstance(wave, int) and not isinstance(wave, bool) and wave >= 0), wave)
                if entry["status"] == "built":
                    self.assertIsInstance(wave, int, "a built skill records the wave that built it")

    def test_a_folded_entry_names_the_built_skill_it_is_a_mode_of(self):
        for entry in (e for e in STACK["skills"] if e["invocation"] == "folded"):
            with self.subTest(entry=entry["name"]):
                self.assertIn(entry.get("into"), names("built", "model") | names("built", "manual"))
                self.assertFalse({"fallback", "excludes", "outside_ceiling", "path"} & set(entry))

    def test_a_library_entry_names_a_path_inside_the_router(self):
        for entry in (e for e in STACK["skills"] if e["invocation"] == "library"):
            with self.subTest(entry=entry["name"]):
                self.assertRegex(entry.get("path", ""), r"^references/[\w./-]+/$")
                self.assertEqual((ROOT / entry["path"]).is_dir(), entry["status"] == "built")

    def test_only_a_built_skill_carries_description_rules(self):
        built = names("built", "model") | names("built", "manual")
        for entry in STACK["skills"]:
            for key in ("outside_ceiling", "excludes", "fallback"):
                if key in entry:
                    with self.subTest(entry=entry["name"], key=key):
                        self.assertIn(entry["name"], built)
        for entry in skills():
            if "outside_ceiling" in entry:
                self.assertIsInstance(entry["outside_ceiling"], int)
                self.assertGreaterEqual(entry["outside_ceiling"], 0)

    def test_each_exclusion_names_a_built_sibling_other_than_itself(self):
        built = names("built", "model") | names("built", "manual")
        for entry in STACK["skills"]:
            for other in entry.get("excludes", []):
                with self.subTest(entry=entry["name"], excludes=other):
                    self.assertIn(other, built)
                    self.assertNotEqual(other, entry["name"])

    def test_overlap_groups_are_built_model_skills_and_every_pair_excludes_both_ways(self):
        model = names("built", "model")
        for group in STACK["overlap"]:
            members = group["members"]
            self.assertLessEqual(set(members), model)
            unpaired = {frozenset(pair) for pair in group.get("not_paired", [])}
            for pair in unpaired:
                self.assertLessEqual(pair, set(members))
            for a in members:
                for b in members:
                    if a == b or frozenset((a, b)) in unpaired:
                        continue
                    with self.subTest(excluder=a, excluded=b):
                        self.assertIn(b, ENTRIES[a].get("excludes", []), a + " must list " + b + " in excludes")

    def test_a_fallback_is_a_core_reference_that_exists(self):
        for entry in (e for e in STACK["skills"] if "fallback" in e):
            with self.subTest(entry=entry["name"]):
                self.assertRegex(entry["fallback"], r"^references/[\w-]+\.md$")
                self.assertTrue((ROOT / entry["fallback"]).is_file())


class RouterAgreesWithManifestTests(unittest.TestCase):
    """Section 5 of the router is a claim about the stack: it must say what stack.json says."""

    def test_the_four_skill_rows_equal_the_manifest(self):
        self.assertEqual(listed(row("Built, model-invocable")), names("built", "model"))
        self.assertEqual(listed(row("Built, manual only")), names("built", "manual"))
        self.assertEqual(listed(row("Planned, model-invocable")), names("planned", "model"))
        self.assertEqual(listed(row("Planned, manual only")), names("planned", "manual"))

    def test_the_folded_and_library_rows_name_every_such_entry(self):
        folded = row("Folded")
        for entry in (e for e in STACK["skills"] if e["invocation"] == "folded"):
            self.assertIn(entry["name"], folded)
            self.assertIn("`" + entry["into"] + "`", folded)
        library = row("Not a skill")
        for entry in (e for e in STACK["skills"] if e["invocation"] == "library"):
            self.assertIn(entry["name"], library)
            self.assertIn(entry["path"], library)

    def test_the_router_points_at_the_manifest_as_the_source_of_the_table(self):
        self.assertIn("stack.json", BODY)

    def test_a_skill_is_in_one_row_only(self):
        rows = [listed(row(p)) for p in ("Built, model-invocable", "Built, manual only", "Planned, model-invocable",
                                         "Planned, manual only")]
        flat = [name for group in rows for name in group]
        self.assertEqual(len(flat), len(set(flat)))

    def test_each_fallback_has_a_command_row_that_prefers_the_installed_skill(self):
        commands = table_rows(BODY)
        for entry in (e for e in STACK["skills"] if "fallback" in e):
            with self.subTest(entry=entry["name"]):
                cell = commands["`" + entry["name"] + "`"]
                self.assertIn("westack-" + entry["name"], cell)
                self.assertIn(entry["fallback"], cell)
                self.assertRegex(cell, r"(?i)when installed|if installed")
                self.assertRegex(cell, r"(?i)otherwise|else|falls? back")

    def test_the_route_reference_names_each_skill_that_has_a_core_fallback(self):
        route = (ROOT / "references" / "route.md").read_text(encoding="utf-8")
        for entry in (e for e in STACK["skills"] if "fallback" in e):
            with self.subTest(entry=entry["name"]):
                self.assertIn("westack-" + entry["name"], route)


if __name__ == "__main__":
    unittest.main()
