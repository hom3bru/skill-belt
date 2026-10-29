"""Regressions for the 2026-10-28 donor source review: the inconclusive result, the
trigger-first description and the adopted module guidance. Inputs are synthetic and local."""
import copy
import json
import pathlib
import re
import unittest

import test_westack as fixtures
from test_round2 import Records, Workspace, cli, out

v = fixtures.v
ROOT = fixtures.ROOT
MEANING = ("it ran, but the result can't settle the claim (flaky outcome, missing oracle, environment limitation "
           "or ambiguous observation). Never counts as passed; record why and what would settle it.")


def text(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class InconclusiveTests(Records):
    def inconclusive(self, **changes):
        receipt = dict(self.task["evidence"][0], id="inc", status="inconclusive",
                       limitations=["Flaky: 1 of 3 runs failed; 20 runs on an idle machine would settle it"])
        receipt.update(changes)
        self.task["evidence"].append(receipt)
        return receipt

    def test_contract_offers_inconclusive_for_receipts_and_criteria(self):
        defs = v.CONTRACT["$defs"]
        self.assertIn("inconclusive", defs["evidence"]["properties"]["status"]["enum"])
        self.assertIn("inconclusive", defs["acceptance"]["properties"]["status"]["enum"])

    def test_inconclusive_receipt_and_criterion_are_valid_in_progress(self):
        self.in_progress()
        self.inconclusive()
        self.task["acceptance"][0].update(status="inconclusive", evidence_ids=["inc"])
        self.assertEqual(self.errors(), [])

    def test_inconclusive_never_counts_as_passed(self):
        self.inconclusive()
        self.task["acceptance"][0]["evidence_ids"] = ["inc"]
        self.assertError("a1: passing acceptance lacks passing evidence")

    def test_required_inconclusive_criterion_blocks_completion(self):
        self.inconclusive()
        self.task["acceptance"][0].update(status="inconclusive", evidence_ids=["inc"])
        self.assertError("required acceptance incomplete")

    def test_inconclusive_records_why_and_what_would_settle_it(self):
        self.in_progress()
        self.inconclusive(limitations=[])
        self.assertError("inc: an inconclusive receipt records why and what would settle it")

    def test_inconclusive_means_it_ran(self):
        self.in_progress()
        self.inconclusive(collected=0, executed=0, passed=0)
        self.assertError("inc: zero executed checks")

    def test_inconclusive_cannot_serve_as_a_control(self):
        e1 = self.task["evidence"][0]
        (self.root / "broken.txt").write_text("broken\n", encoding="utf-8")
        e1.update(type="unit", negative_control="inc")
        self.inconclusive(type="unit", artifact="broken.txt", artifact_sha256=v.digest(self.root / "broken.txt"),
                          passed=0, failed=1, exit_code=1)
        self.task["acceptance"][0].update(requires_runtime=True, requires_negative_control=True)
        self.task["verification"] = "runtime-tested"
        self.assertError("missing failed negative control")

    def test_docs_state_the_exact_meaning(self):
        for relative in ("contracts/README.md", "references/verify.md"):
            with self.subTest(doc=relative):
                self.assertIn(MEANING, re.sub(r"\s+", " ", text(relative)))


class InconclusiveCliTests(Workspace):
    def test_receipt_records_an_inconclusive_run(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        refused = self.receipt(2, "e1", "--claim", "a1", "--status", "inconclusive", "--link", passed=2, failed=1)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertFalse(self.path(3).exists())
        result = self.receipt(2, "e1", "--claim", "a1", "--status", "inconclusive", "--link",
                              "--limitation", "1 of 3 runs failed; settle with 20 runs", passed=2, failed=1, exit_code=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(3))
        self.assertEqual(record["evidence"][-1]["status"], "inconclusive")
        self.assertEqual((record["acceptance"][0]["status"], record["acceptance"][0]["evidence_ids"]),
                         ("inconclusive", ["e1"]))


class DescriptionTests(unittest.TestCase):
    def test_trigger_comes_first(self):
        front = re.match(r"^---\n(.*?)\n---\n", text("SKILL.md"), re.S)[1]
        description = re.search(r"^description: (.+)$", front, re.M)[1]
        self.assertTrue(description.startswith("Use when the user names westack"), description)


class AdoptedGuidanceTests(unittest.TestCase):
    """Each adopted donor mechanism has a home in a module, not in SKILL.md."""
    CASES = {
        "references/verify.md": ["baseline", "by name", "pre-existing", "variable names", "never their values",
                                 "independently of the code under test", "realistic mutation", "still passes",
                                 "tooling error", "blocked", "at most twice", "silently"],
        "references/finish.md": ["auto-merge", "merge queue", "pre-existing"],
        "references/review.md": ["same pattern", "not assessed", "scope it assessed"],
        "references/frame.md": ["recommended answer", "prerequisites", "look it up", "vague quantifier"],
        "references/build.md": ["deferred execution", "CI configuration", "explicit scope"],
        "hosts/README.md": ["MCP", "local commands"],
    }

    def test_guidance_is_in_the_modules(self):
        for relative, phrases in self.CASES.items():
            body = re.sub(r"\s+", " ", text(relative))
            for phrase in phrases:
                with self.subTest(doc=relative, phrase=phrase):
                    self.assertIn(phrase, body)

    def test_codex_permission_surfaces_are_declared(self):
        hosts = {h["name"]: h for h in json.loads(text("hosts/capabilities.json"))["hosts"]}
        surfaces = hosts["Codex"].get("permission_surfaces")
        self.assertIsInstance(surfaces, dict)
        for key in ("local_commands", "mcp_servers_and_connectors", "browser_and_computer_use", "web_search", "network"):
            self.assertIn(key, surfaces)

    def test_skill_md_stays_lean(self):
        self.assertLessEqual(len(text("SKILL.md").split()), 600)


if __name__ == "__main__":
    unittest.main()
