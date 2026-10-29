"""r16 candidate, second pass: recipient-neutral contract, shared evidence vocabulary (TESTED = ran in
this work), bias controls, idea-only legal checks, profile-driven path rules and outcome-ready history."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_aa import aa, fixture, SCRIPT

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_SHA256 = "bde4fc984f4455223956fd9f32f29f61a986ebc9213f5b800a20bf5583debbd2"  # skill-belt shared/evidence-vocabulary.md v3 (v2 was b905e2c3...; v3 only renames the recipient skill to westack)
PRIVATE_TERMS = re.compile(r"(?i:\b(?:rss-radar|radar|eddie|maginot)\b)|\bMatt\b|Kolkin|CANDO|egressFetch|intel\.sqlite"
                           r"|isPathAuthoritativeGoverned|gbatch_|LAPTOP-|Users[/\\]Matt|antigravity|Astra")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def contract_item(number):
    section = read("SKILL.md").split("## 0.", 1)[1].split("## 1.", 1)[0]
    return next(line for line in section.splitlines() if line.startswith(f"{number}. "))


def neutral_scope():
    """Files an agent loads by default or the helpers ship, minus profile-owned and archived text."""
    files = [ROOT / "SKILL.md", ROOT / "agents" / "openai.yaml", *sorted((ROOT / "scripts").glob("*.py"))]
    for path in sorted((ROOT / "references").rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if path.is_file() and not rel.startswith("references/profiles/") and rel != "references/historical-findings.md":
            files.append(path)
    return files


def execution_module():
    spec = importlib.util.spec_from_file_location("r16b_execution", Path(aa.__file__).with_name("execution.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recipient_run(run, record, subject="target"):
    """An owned check run in this work (default: against the recipient snapshot); returns its evidence ID."""
    revision = record["recipients"][0]["revision"] if subject == "target" else record["sources"][0]["revision"]
    work = run / f"check-{subject}"
    work.mkdir()
    script = work / "check.py"
    script.write_text('import json\nprint(json.dumps({"checks": [{"id": "send", "kind": "positive", "status": "pass", "detail": "owned"},'
                      ' {"id": "broken-copy", "kind": "negative-control", "status": "pass", "detail": "disconnected copy rejected"}]}))\n', encoding="utf-8")
    evidence = execution_module().execute(run, [sys.executable, "-B", str(script)], work, [script], [], "Owned recipient check authorized by this test", 20, [],
                                          subject=subject, revision=revision)
    evidence["read_scope"] = "Receipt, stdout and control reviewed"
    record["evidence"].append(evidence)
    return evidence["id"]


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)
        self.decision = self.record["items"][0]["decision"]
        self.legal = self.record["items"][0]["ledger"]["legal"]

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return " ".join(aa.validate(self.record, self.run))


class ContractTests(unittest.TestCase):
    def test_contract_items_reworded_as_approved(self):
        self.assertIn("need that profile's checks", contract_item(2))
        five = contract_item(5)
        self.assertIn("CANCELLED", five)
        self.assertIn("INCONCLUSIVE", five)
        self.assertIn("result", five)
        self.assertIn("confirms the published report equals the validated rendering", contract_item(6))
        nine = contract_item(9)
        self.assertIn("as its profile records", nine)
        self.assertIn("no magic word is required", nine)
        ten = contract_item(10)
        self.assertNotIn("Astra", ten)
        self.assertIn("cheapest model that can do the job", ten)
        self.assertIn("any model tier the user allows", ten)

    def test_ladder_matches_shared_vocabulary(self):
        vocabulary = ROOT / "references" / "evidence-vocabulary.md"
        self.assertEqual(hashlib.sha256(vocabulary.read_bytes()).hexdigest(), VOCABULARY_SHA256)
        ladder = contract_item(7)
        self.assertIn("(references/evidence-vocabulary.md)", ladder)
        self.assertIn("ran in this work", ladder)
        self.assertIn("**author-tested**", ladder)
        self.assertIn("no higher than WIRED", ladder)
        self.assertNotIn("CI result", ladder)
        package = (ROOT / "scripts" / "package.py").read_text(encoding="utf-8")
        self.assertIn('"references/evidence-vocabulary.md"', package)

    def test_bias_controls_are_instructions(self):
        body = read("SKILL.md")
        bounded = body.split("### Bounded mechanism review", 1)[1].split("## 2.", 1)[0]
        self.assertIn("refutation targets", bounded)
        doubt = body.split("## 7.", 1)[1].split("## 8.", 1)[0]
        self.assertIn("independent reviewer", doubt)
        self.assertIn("not the verdict", doubt)
        publish = body.split("## 8.", 1)[1]
        self.assertIn("Outcome log", publish)
        self.assertIn("never an input to a fresh judgment", publish)

    def test_legal_reference_states_idea_only_rules(self):
        legal = read("references/legal.md")
        self.assertIn("GREEN(idea-only)", legal)
        self.assertIn("patent-signal check", legal)


class NeutralityTests(unittest.TestCase):
    def test_private_recipient_terms_live_only_in_profiles(self):
        offenders = []
        for path in neutral_scope():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if path.name == "SKILL.md" and (line.startswith("description: ") or line.startswith("license: ")):
                    continue
                if PRIVATE_TERMS.search(line):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{number}: {PRIVATE_TERMS.search(line).group(0)}")
        self.assertEqual(offenders, [])

    def test_profiles_carry_their_own_routing_signals(self):
        for path in (ROOT / "references" / "profiles").glob("*.md"):
            if path.stem not in {"generic", "self"}:
                self.assertIn("## Routing signals", path.read_text(encoding="utf-8"), path.name)

    def test_known_profiles_come_from_installed_profile_files(self):
        stems = {p.stem for p in (ROOT / "references" / "profiles").glob("*.md")}
        self.assertTrue(stems | {"unspecified", "tooling"} <= aa.known_profiles())
        self.assertNotIn("not-installed-profile", aa.known_profiles())


class LadderEvidenceTests(Case):
    def mark_tested(self, run):
        inventory = self.decision["inventory"]
        for key in ("implemented", "wired", "tested"):
            inventory[key]["state"] = "present"
        inventory["tested"]["run"] = run
        # Fourth pass: a plan over a capability already implemented and wired must say it augments or replaces it.
        self.decision["transfer"]["relation"] = "augments"

    def test_author_tested_ci_text_is_not_tested(self):
        self.mark_tested("Donor CI job 41 passed at the pinned revision (not run in this work).")
        self.assertIn("ran in this work", self.errors())

    def test_recipient_run_in_this_work_earns_tested(self):
        self.mark_tested(recipient_run(self.run, self.record))
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_source_side_run_cannot_support_recipient_tested(self):
        self.mark_tested(recipient_run(self.run, self.record, subject="s1"))
        self.assertIn("ran in this work", self.errors())


class IdeaOnlyLegalTests(Case):
    def idea_only(self, flag="GREEN", **fields):
        self.legal.pop("patent_signal", None)  # the r16 fourth-pass fixture records it for its permissive route
        self.legal.update(flag=flag, route="idea-only", ladder_steps_tried=["permissive-alternative", "idea-only"], **fields)

    def test_green_idea_only_needs_both_checks(self):
        self.idea_only()
        self.assertIn("patent_signal", self.errors())
        self.idea_only(patent_signal="none", terms_restriction="none")
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_terms_restriction_or_patent_hit_cannot_be_green(self):
        self.idea_only(patent_signal="none", terms_restriction="present")
        self.assertIn("GREEN(idea-only)", self.errors())
        self.idea_only(patent_signal="hit", terms_restriction="none")
        self.assertIn("GREEN(idea-only)", self.errors())

    def test_patent_hit_is_yellow_with_counsel(self):
        self.idea_only(flag="YELLOW", patent_signal="hit", terms_restriction="none")
        self.legal["escalate_to_lawyer"] = False
        self.assertIn("counsel", self.errors())
        self.legal["escalate_to_lawyer"] = True
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_idea_only_part_is_checked_too(self):
        self.legal.update(flag="RED", route="discard", escalate_to_lawyer=True,
                          parts=[{"id": "p1", "part": "documented idea", "flag": "GREEN", "route": "idea-only", "basis": "ideas only"}])
        self.decision["legal_part"] = "p1"
        self.assertIn("patent_signal", self.errors())
        self.legal["parts"][0].update(patent_signal="none", terms_restriction="none")
        self.assertEqual(aa.validate(self.record, self.run), [])


class HelperTests(Case):
    def test_history_event_carries_value_and_confidence(self):
        path = self.run / "run.json"; aa.save(path, self.record)
        report = self.run / "report.md"
        subprocess.run([sys.executable, "-B", str(SCRIPT), "render", str(path), "--output", str(report)], check=True, capture_output=True, text=True)
        ledger = self.root / "history.jsonl"
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "history", str(path), "--ledger", str(ledger), "--published-report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])["decisions"][0]
        self.assertEqual((decision["mechanism_value"], decision["confidence_level"], decision["item"]), (2, "medium", "q1"))

    # test_classify_path_by_profile_fails_closed_without_root moved to test_private_profiles.py.


if __name__ == "__main__":
    unittest.main()
