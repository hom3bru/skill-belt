"""The router SKILL.md contract: explicit-only, lean, honest about what is built, and carrying the
invocation policy the owner decided (eval, skill and orchestrate manual; lang a library; plan-review
folded into review). What is built and what is planned is read from the stack manifest (stack.json),
not listed here: adding a sub-skill is a manifest edit, and test_stack.py checks the table against it."""
import json
import re
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
FRONT = re.match(r"^---\n(.*?)\n---\n", SKILL, re.S)[1]
BODY = SKILL[len(FRONT) + 8:]
STACK = json.loads((ROOT / "stack.json").read_text(encoding="utf-8"))


def named(status, invocation):
    return {entry["name"] for entry in STACK["skills"]
            if entry["status"] == status and entry["invocation"] == invocation}


BUILT_MODEL = named("built", "model")
BUILT_MANUAL = named("built", "manual")
PLANNED_MODEL = named("planned", "model")
PLANNED_MANUAL = named("planned", "manual")


def table_rows(text):
    return {cells[0]: cells[1] for cells in (
        [c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
        if line.startswith("|") and "---" not in line) if len(cells) >= 2}


class RouterFrontMatterTests(unittest.TestCase):
    def test_explicit_invocation_only(self):
        self.assertIn("\ndisable-model-invocation: true\n", "\n" + FRONT + "\n")
        description = re.search(r"^description: (.+)$", FRONT, re.M)[1]
        self.assertTrue(description.startswith("Use when the user names westack"), description)
        self.assertLessEqual(len(description), 300)

    def test_stack_metadata(self):
        self.assertRegex(FRONT, r"(?m)^name: westack$")
        self.assertRegex(FRONT, r"(?m)^metadata:$")
        self.assertRegex(FRONT, r"(?m)^  stack: westack$")
        self.assertRegex(FRONT, r"(?m)^  version: 1\.0\.0-alpha\.0$")


class RouterBodyTests(unittest.TestCase):
    def test_lean(self):
        self.assertLessEqual(len(BODY.split()), 600)

    def test_makes_no_static_claim_that_nothing_is_built(self):
        flat = re.sub(r"\s+", " ", BODY)
        self.assertNotIn("No `westack-*` sub-skill is built yet", flat)
        self.assertNotIn("ships the core only", flat)
        self.assertNotRegex(flat, r"(?i)no .{0,20}sub-skill is built")
        self.assertNotRegex(BODY, r"\]\(\.\./westack-")

    def test_not_built_yet_is_said_only_for_a_skill_the_registry_does_not_list(self):
        flat = re.sub(r"\s+", " ", BODY)
        rule = re.search(r"If the owner is not listed[^.]*\.[^.]*\.", flat)
        self.assertIsNotNone(rule, "the dynamic rule must stay, keyed to the registry listing")
        self.assertIn("is not built yet", rule[0])
        self.assertIn("not installed", rule[0], "a built skill that is not installed is not 'not built'")
        self.assertIn("registry", rule[0])
        self.assertEqual(flat.count("is not built yet"), 1, "one rule, not a list of names")

    def test_marks_the_manifests_built_skills_as_built(self):
        rows = table_rows(BODY)
        built = next(v for k, v in rows.items() if k.startswith("Built, model-invocable"))
        self.assertEqual({x.strip() for x in built.split(",")}, BUILT_MODEL)
        key, manual = next((k, v) for k, v in rows.items() if k.startswith("Built, manual only"))
        self.assertIn("`disable-model-invocation: true`", key)
        self.assertEqual({x.strip() for x in manual.split(",")}, BUILT_MANUAL)

    def test_verify_command_prefers_the_sub_skill_and_falls_back_to_the_core_reference(self):
        row = table_rows(BODY)["`verify`"]
        self.assertIn("westack-verify", row)
        self.assertIn("references/verify.md", row)
        self.assertRegex(row, r"(?i)when installed|if installed")
        self.assertRegex(row, r"(?i)otherwise|else|falls? back")

    def test_build_command_prefers_the_sub_skill_and_falls_back_to_the_core_reference(self):
        row = table_rows(BODY)["`build`"]
        self.assertIn("westack-build", row)
        self.assertIn("references/build.md", row)
        self.assertRegex(row, r"(?i)when installed|if installed")
        self.assertRegex(row, r"(?i)otherwise|else|falls? back")
        self.assertTrue((ROOT / "references" / "build.md").is_file(), "the fallback it names")

    def test_design_review_tie_break(self):
        flat = re.sub(r"\s+", " ", BODY)
        self.assertRegex(flat, r"(?i)design review[^.;]*(plan|spec|document)[^.;]*`review`[^.;]*document mode")
        self.assertRegex(flat, r"(?i)design review[^.]*built UI[^.]*`design`")

    def test_route_reference_agrees_about_verify(self):
        route = (ROOT / "references" / "route.md").read_text(encoding="utf-8")
        self.assertIn("westack-verify", route)
        self.assertRegex(route, r"(?i)design review")

    def test_trigger_cases_do_not_expect_a_bare_core(self):
        data = json.loads((ROOT / "tests" / "trigger-cases.json").read_text(encoding="utf-8"))
        text = json.dumps(data)
        self.assertNotIn("no sub-skill is built yet", text)
        self.assertNotIn("westack-review is not built yet", text)
        requests = [c["request"] for c in data["cases"]]
        self.assertTrue(any("design review" in r.lower() and "plan" in r.lower() for r in requests), requests)
        self.assertTrue(any("design review" in r.lower() and "page" in r.lower() for r in requests), requests)
        for case in data["cases"]:
            self.assertTrue(case.get("expected"), case)

    def test_finds_installed_skills_through_registry(self):
        self.assertIn("scripts/registry.py", BODY)
        self.assertIn("metadata.stack: westack", BODY)

    def test_routing_order_and_tie_breaks(self):
        self.assertIn("An explicit name wins", BODY)
        for word in ("artifact", "verb", "object", "Tie-breaks", "recommended answer"):
            self.assertIn(word, BODY)

    def test_consent_and_memory_rules(self):
        flat = re.sub(r"\s+", " ", BODY)
        for phrase in ("ask once per session", "never saved", "never deferred", "host's own memory",
                       "explicit save"):
            self.assertIn(phrase, flat)

    def test_invocation_policy_table(self):
        rows = table_rows(BODY)
        manual = next(v for k, v in rows.items() if k.startswith("Planned, manual only"))
        self.assertEqual({x.strip() for x in manual.split(",")}, PLANNED_MANUAL)
        folded = next(v for k, v in rows.items() if k.startswith("Folded"))
        self.assertIn("plan-review", folded)
        self.assertIn("review", folded.replace("plan-review", ""))
        self.assertIn("document mode", folded)
        library = next(v for k, v in rows.items() if k.startswith("Not a skill"))
        self.assertIn("lang", library)
        self.assertIn("references/lang/", library)
        self.assertIn("not routed", library)
        invocable = next(v for k, v in rows.items() if k.startswith("Planned, model-invocable"))
        self.assertEqual(set(x.strip() for x in invocable.split(",")), PLANNED_MODEL)
        built_and_planned = BUILT_MODEL | BUILT_MANUAL
        self.assertFalse(built_and_planned & (PLANNED_MODEL | PLANNED_MANUAL), "a skill is built or planned, not both")

    def test_stack_commands(self):
        rows = table_rows(BODY)
        for command in ("`list`", "`doctor`", "`defer`", "`verify`", "`build`"):
            self.assertIn(command, rows)


if __name__ == "__main__":
    unittest.main()
