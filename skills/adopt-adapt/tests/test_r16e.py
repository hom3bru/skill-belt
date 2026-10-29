"""r16 candidate, fix round after the 2026-10-28 blind comparison: proportion by default.

The comparison found ceremony and extra artefacts on tasks too small to need them, a hedged verdict on a need the
user had stated, a prerequisite whose outcome could not change the decision, and side files nobody asked for. These
checks pin the instructions that replace those drivers so a later edit cannot drop them silently. They test wording,
not behaviour; behaviour needs a fresh blind campaign on unseen cases."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


BODY = read("SKILL.md")
START = section(BODY, "## 1.", "### Quick call") if "### Quick call" in BODY else section(BODY, "## 1.", "### Bounded")


def quick_call():
    return section(BODY, "### Quick call", "### Bounded mechanism review")


class QuickCallTests(unittest.TestCase):
    def test_quick_call_is_the_default_route_for_a_small_idea(self):
        route = section(BODY, "## 1.", "## 2.")
        self.assertIn("### Quick call", route)
        self.assertLess(route.index("### Quick call"), route.index("### Bounded mechanism review"))
        quick = quick_call()
        self.assertIn("default", quick.splitlines()[0])
        for size in ("snippet", "one function", "one idea"):
            self.assertIn(size, quick)
        for risk in ("governed or frozen seam", "skill/hook/MCP/config donor", "new dependency", "whole-tool adoption"):
            self.assertIn(risk, quick)

    def test_quick_call_answer_keeps_the_contract_in_a_few_lines(self):
        quick = quick_call()
        for part in ("file:line", "licence in one line", "read versus run", "the verdict with its reason",
                     "strongest reason against", "the transfer step", "one test that fails without the mechanism"):
            self.assertIn(part, quick)
        self.assertIn("ledger (§0.6)", quick)  # its evidence lines are the ledger, printed before the verdict

    def test_quick_call_adds_no_ceremony_or_files(self):
        excluded = quick_call().split("Add no", 1)[1]
        for ceremony in ("template", "refutation targets", "lens list", "printed numbers",
                         "routing line for a named recipient", "files"):
            self.assertIn(ceremony, excluded)
        self.assertIn("Move up a route only when", quick_call())

    def test_numbers_and_lens_reporting_exempt_the_quick_call(self):
        numbers = section(BODY, "**Numbers by route.**", "\n")
        self.assertIn("Quick call: judged, not printed.", numbers)
        salvage = section(BODY, "## 5.", "## 6.")
        self.assertNotIn("reporting rule everywhere", salvage)
        self.assertIn("bounded and full manual reports", salvage)
        self.assertIn("bounded and full manual reports", read("references/transfer.md"))

    def test_rigour_is_not_ceremony(self):
        self.assertIn("never default to rejection or ceremony to look rigorous", BODY)


class UserStatementTests(unittest.TestCase):
    def test_what_the_user_states_is_input(self):
        for phrase in ("What the user states", "is input", "without re-verifying or hedging", "contradicts"):
            self.assertIn(phrase, START)

    def test_a_stated_need_is_confirmed_never_promising(self):
        value = re.search(r"\*\*Mechanism value \(0–3\)\*\*(.+)", BODY).group(1)
        one = value.split("1:", 1)[1].split("2:", 1)[0]
        two = value.split("2:", 1)[1].split("3:", 1)[0]
        self.assertIn("never for a need the user stated", one)
        self.assertIn("the user's own statement counts", two)
        self.assertIn("observed symptom or a stated requirement", two)  # r16's need rule is kept
        need = next(line for line in read("references/bounded-ledger-template.md").splitlines() if line.startswith("Need:"))
        self.assertIn("the user's statement counts", need)


class PrerequisiteAndScopeTests(unittest.TestCase):
    def test_a_prerequisite_must_be_able_to_change_the_decision(self):
        publish = section(BODY, "## 8.", "## 9.")
        self.assertIn("A prerequisite must be able to change the verdict or plan", publish)

    def test_patent_signal_check_reads_the_material_not_a_database(self):
        gates = section(BODY, "## 3.", "## 4.")
        self.assertIn("reads the material you hold, not a patent database", gates)
        rung = next(line for line in read("references/legal.md").splitlines() if line.startswith("2. **Idea-only**"))
        for phrase in ("not a patent database", "nothing found is `none`", "`unknown` means"):
            self.assertIn(phrase, rung)

    def test_write_scope_allows_no_side_files(self):
        self.assertIn("only the files the user asked for", START)
        publish = section(BODY, "## 8.", "## 9.")
        self.assertIn("when the write scope allows a run directory", publish)


if __name__ == "__main__":
    unittest.main()
