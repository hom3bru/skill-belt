"""Structural checks for the behavioural eval suite (claude plugin eval layout).

These tests validate the suite's files; they do not run a model. Running the suite
needs `claude plugin eval` and model usage (see evals/README.md).
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
PROMPT_KEYS = {"name", "description", "tags", "plugins", "runs", "expected_outcome", "model", "max_turns",
               "timeout_seconds", "allowed_tools", "append_system_prompt", "env"}
GRADER_KEYS = {"regex": {"pattern", "flags", "match", "target"}, "tool_used": {"tool", "input_match", "min", "max"},
               "tool_order": {"before", "after"}, "file_exists": {"path", "exists"}, "llm": {"criteria", "focus"},
               "baseline": {"baseline_file", "criteria"}}
REQUIRED = {"regex": {"pattern"}, "tool_used": {"tool"}, "tool_order": {"before", "after"}, "file_exists": {"path"},
            "llm": set(), "baseline": {"baseline_file"}}
SKILLS = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}


def split(path):
    text = path.read_text(encoding="utf-8")
    found = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not found:
        raise AssertionError(f"{path.relative_to(ROOT)} has no frontmatter")
    fields = {}
    for line in found.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, found.group(2).strip()


class EvalSuiteTests(unittest.TestCase):
    def cases(self):
        return sorted(p for p in EVALS.iterdir() if p.is_dir() and p.name != "results")

    def test_suite_has_cases_and_no_committed_results(self):
        self.assertGreaterEqual(len(self.cases()), 10)
        self.assertFalse((EVALS / "results").exists(), "evals/results is local output and must not ship")

    def test_prompts_use_only_documented_keys_and_carry_their_input(self):
        for case in self.cases():
            with self.subTest(case=case.name):
                fields, body = split(case / "prompt.md")
                self.assertLessEqual(set(fields), PROMPT_KEYS)
                self.assertGreater(len(body), 40, "prompt must carry its own input; each run starts empty")
                self.assertNotRegex(body, r"[A-Za-z]:[/\\]{1,2}Users[/\\]")

    def test_graders_are_valid_and_every_case_is_graded(self):
        for case in self.cases():
            with self.subTest(case=case.name):
                graders = sorted((case / "graders").glob("*.md"))
                self.assertTrue(graders)
                for grader in graders:
                    fields, body = split(grader)
                    kind = fields.get("type")
                    self.assertIn(kind, GRADER_KEYS)
                    allowed = GRADER_KEYS[kind] | {"type", "weight", "arm"}
                    self.assertLessEqual(set(fields), allowed, grader.name)
                    self.assertLessEqual(REQUIRED[kind], set(fields), grader.name)
                    if kind == "llm":
                        self.assertTrue(body.startswith("PASS if"), grader.name)
                        self.assertIn("FAIL", body)
                    if kind == "tool_used" and fields.get("tool") == "Skill":
                        named = re.findall(r"\(\?:\[\\w-\]\+:\)\?([a-z-]+)", fields["input_match"])
                        self.assertTrue(named and set(named) <= SKILLS, f"{grader.name} names an unknown skill")
                        re.compile(fields["input_match"].strip("'"))

    def test_every_new_workflow_has_a_behavioural_case_or_trigger(self):
        text = "\n".join(p.read_text(encoding="utf-8") for p in EVALS.rglob("*.md"))
        for skill in ("application-intake", "offer-negotiation"):
            self.assertIn(skill, text)


if __name__ == "__main__":
    unittest.main()
