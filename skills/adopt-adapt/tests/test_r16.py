"""r16 candidate checks: ladder and score definitions, verdict thresholds, doubt parity,
one verdict vocabulary, part-level legal flags, fresh recipient path rules,
cwd-independent commands, sibling routing exclusions and the always-loaded budget."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_aa import aa, fixture, SCRIPT

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.0.0-grok-draft.r16"

# What a run actually loads (fourth pass): SKILL.md, routing.md and the generated routing index
# (`aa.py routing-index`), then only the chosen profile, the shared vocabulary that §0.7 makes normative and the
# route's references. The bounded set uses the largest project profile where an edition ships it, else generic.
BOUNDED_PROFILE = "references/profiles/radar.md" if (ROOT / "references/profiles/radar.md").is_file() else "references/profiles/generic.md"
BOUNDED_SET = ("SKILL.md", "references/routing.md", BOUNDED_PROFILE, "references/legal.md",
               "references/narrative-review.md", "references/output-template.md", "references/evidence-vocabulary.md",
               "references/bounded-ledger-template.md")
SKILL_DONOR_SET = ("SKILL.md", "references/routing.md", "references/profiles/coding-workflow.md", "references/legal.md",
                   "references/due-diligence.md", "references/checker-honesty.md", "references/hook-intake.md",
                   "references/transfer.md", "references/narrative-review.md", "references/output-template.md",
                   "references/records.md", "references/evidence-vocabulary.md")
# Budgets equal the measured loaded sets in the full (private) edition; a public edition loads less. Before the
# routing index, routing.md told a run to read every installed profile: 11,902 words bounded and 17,696 for a
# skill donor (third pass, private edition), against the 7,333 / 12,553 the old test counted. Any growth must be a
# deliberate, reviewed change that raises these numbers with evidence (references/evolution.md).
# Fix round after the 2026-10-28 blind comparison: the quick call and the user-statement, write-scope and
# prerequisite rules were paid for by deletions, so every budget went down (was 3,092 / 9,227 / 14,744).
# Round 3 after the 2026-10-29 blind comparison: three rules with no deletion to pay for them (checks inline and
# no writes outside the named folder, claims of work bound to their tool calls, complete DISCARD salvage) add 103
# measured words to SKILL.md, so each budget rose by exactly 103 (was 3,088 / 9,192 / 14,706).
BUDGET_SKILL = 3191
BUDGET_BOUNDED = 9295
BUDGET_SKILL_DONOR = 14809


def loaded(files):
    """Words a run loads for one route: the listed files plus the generated routing index."""
    return sum(words(f) for f in files) + len(re.findall(r"\S+", aa.routing_index()))

ARCHIVE_FILES = {"references/historical-findings.md", "references/legal-research.md",
                 "references/re-source-review-2026-10-10.md"}
NOTE_ID = re.compile(r"\bKP\d+\b|\bgroup[123]\b|catalogue C\d+|build-time source|\b(?:2\.11|3\.0) [\w/.-]+\.md:\d"
                     r"|(?<![\w-])review\.md[:§ ]|(?<![\w-])research\.md\b|missed-sources|process-read|ai-re-trend|anyps5\.md"
                     r"|CHANGELOG-r5|\bP\d+\.[A-Z0-9]|\bP\d-[A-Z]{2}\d")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def words(relative):
    return len(re.findall(r"\S+", read(relative)))


def agent_docs():
    docs = [ROOT / "SKILL.md", *sorted((ROOT / "references").rglob("*.md"))]
    return [p for p in docs if p.relative_to(ROOT).as_posix() not in ARCHIVE_FILES]


def ready(record):
    decision = record["items"][0]["decision"]
    decision["mechanism_value"] = 2
    decision["confidence_level"] = "medium"
    return record


def errors(record, run):
    return " ".join(aa.validate(record, run))


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)
        ready(self.record)
        self.decision = self.record["items"][0]["decision"]
        self.ledger = self.record["items"][0]["ledger"]

    def tearDown(self):
        self.temp.cleanup()


class LadderTests(Case):
    def test_skill_defines_every_ladder_level(self):
        rule = next(line for line in read("SKILL.md").splitlines() if "**Evidence ladder.**" in line)
        for level in ("CLAIMED", "PRESENT", "WIRED", "TESTED", "OBSERVED"):
            self.assertRegex(rule, rf"\*\*{level}\*\* — \S", level)
        self.assertIn("never earns TESTED", rule)

    def test_baseline_fixture_with_integer_value_is_valid(self):
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_tested_needs_an_observed_run(self):
        inventory = self.decision["inventory"]
        for key in ("implemented", "wired", "tested"):
            inventory[key]["state"] = "present"
        self.assertIn("ran in this work", errors(self.record, self.run))
        # Second pass (shared vocabulary): CI text is author-tested, not TESTED; test_r16b covers the accepted form.
        inventory["tested"]["run"] = "CI job 41 log: test_send_retry passed at the pinned revision."
        self.assertIn("author-tested", errors(self.record, self.run))

    def test_observed_needs_an_observed_run(self):
        inventory = self.decision["inventory"]
        inventory["implemented"]["state"] = "present"
        inventory["observed"]["state"] = "present"
        self.assertIn("OBSERVED", errors(self.record, self.run))

    def test_wired_or_tested_without_implementation_rejected(self):
        inventory = self.decision["inventory"]
        inventory["wired"]["state"] = "present"
        self.assertIn("implemented", errors(self.record, self.run))


class ScoreTests(Case):
    def test_legacy_text_value_rejected_with_reassessment_message(self):
        self.decision["mechanism_value"] = "Potential duplicate-effect prevention."
        self.assertIn("mechanism_value must be an integer 0-3", errors(self.record, self.run))

    def test_value_bounds_and_boolean_rejected(self):
        for bad in (4, -1, True, 2.0):
            with self.subTest(bad=bad):
                self.decision["mechanism_value"] = bad
                self.assertIn("mechanism_value must be an integer 0-3", errors(self.record, self.run))

    def test_adapt_needs_value_two(self):
        self.decision["mechanism_value"] = 1
        self.assertIn("mechanism_value >= 2", errors(self.record, self.run))
        self.decision["mechanism_value"] = 2
        self.assertEqual(aa.validate(self.record, self.run), [])

    def adopt(self, components, value=2):
        self.decision.update(whole_tool="ADOPT", result="ADOPT", mechanism_value=value,
                             score={"rubric": "generic", "components": components, "penalty": 0,
                                    "total": sum(components), "rationale": "test"})
        # Fourth pass: ADOPT needs an independent review above level self (SKILL.md §7).
        packet = self.run / "review-packet.md"
        packet.write_text("Ledger and evidence without the verdict.\n", encoding="utf-8")
        self.ledger["review"] = {"level": "fresh-context-same-model", "artifact": "review-packet.md", "checked": True,
                                 "sha256": hashlib.sha256(packet.read_bytes()).hexdigest(), "disconfirming": "None found."}

    def test_adopt_needs_scored_fit_eight_and_value_two(self):
        self.adopt([3, 3, 1, 1])
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.adopt([3, 2, 1, 1])
        self.assertIn("fit >= 8", errors(self.record, self.run))
        self.adopt([3, 3, 1, 1], value=1)
        self.assertIn("mechanism_value >= 2", errors(self.record, self.run))
        self.adopt([3, 3, 1, 1])
        self.decision["score"] = None
        self.decision["score_reason"] = "skipped"
        self.assertIn("fit >= 8", errors(self.record, self.run))

    def test_confidence_level_required(self):
        del self.decision["confidence_level"]
        self.assertIn("confidence_level", errors(self.record, self.run))
        self.decision["confidence_level"] = "sure"
        self.assertIn("confidence_level", errors(self.record, self.run))

    def test_skill_anchors_value_confidence_and_numbers_by_route(self):
        body = read("SKILL.md")
        value = re.search(r"\*\*Mechanism value \(0–3\)\*\*(.+)", body)
        confidence = re.search(r"\*\*Confidence \(low/medium/high\)\*\*(.+)", body)
        self.assertTrue(value and confidence)
        for anchor in ("0:", "1:", "2:", "3:"):
            self.assertIn(anchor, value.group(1))
        for anchor in ("low:", "medium:", "high:"):
            self.assertIn(anchor, confidence.group(1))
        self.assertIn("**Numbers by route.**", body)

    def test_cli_score_accepts_every_validator_rubric(self):
        for rubric in sorted(aa.known_rubrics()):
            with self.subTest(rubric=rubric):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "score", "--rubric", rubric, "--components", "1", "1", "1", "1"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


class DoubtParityTests(Case):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "doubt", *args], capture_output=True, text=True)

    def test_transfer_results_are_full_in_cli(self):
        for verdict in ("ADOPT", "ADAPT", "ADAPT-with-prerequisite"):
            with self.subTest(verdict=verdict):
                self.assertEqual(self.cli(verdict).stdout.strip(), "full")

    def test_salvage_found_flag_matches_validator(self):
        self.assertEqual(self.cli("DISCARD", "--score", "3").stdout.strip(), "light")
        self.assertEqual(self.cli("DISCARD", "--score", "3", "--salvage-found").stdout.strip(), "full")
        self.assertEqual(aa.doubt_depth("DISCARD", 3, salvage_found=True), "full")
        self.decision.update(result="DISCARD", score={"rubric": "generic", "components": [1, 1, 0, 1], "penalty": 0, "total": 3, "rationale": "low"})
        self.decision.pop("transfer"); self.decision.pop("inventory")
        self.ledger["doubt"].update(depth="light", decision_uncertainty=False)
        self.assertIn("doubt route must be full", errors(self.record, self.run))
        for axis in self.ledger["salvage"].values():
            axis["result"] = "none"
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_skill_section_seven_names_the_same_triggers(self):
        section = read("SKILL.md").split("## 7.", 1)[1].split("## 8.", 1)[0]
        for trigger in ("ADAPT-with-prerequisite", "salvage", "5–7", "consequential", "`aa.py doubt`"):
            self.assertIn(trigger, section)


class VerdictVocabularyTests(unittest.TestCase):
    def bold_tokens(self, prefix, text):
        line = next(x for x in text.splitlines() if x.startswith(prefix))
        return set(re.findall(r"\*\*([A-Z][A-Za-z-]+)\*\*", line))

    def test_skill_results_match_validator(self):
        self.assertEqual(self.bold_tokens("Results ", read("SKILL.md")), aa.RESULTS)

    def test_skill_item_states_match_validator(self):
        self.assertEqual(self.bold_tokens("Item states", read("SKILL.md")), set(aa.STATES))

    def test_output_template_verdict_line_matches_validator(self):
        found = re.search(r"VERDICT: <([^>]+)>", read("references/output-template.md"))
        self.assertEqual(set(found.group(1).split("|")), aa.RESULTS)


class LegalPartTests(Case):
    def setUp(self):
        super().setUp()
        self.ledger["legal"].update(flag="RED", route="discard", escalate_to_lawyer=True,
                                    parts=[{"id": "p1", "part": "documented stable request-ID idea", "flag": "GREEN",
                                            "route": "idea-only", "basis": "Idea only; no donor expression copied.",
                                            "patent_signal": "none", "terms_restriction": "none"}])
        self.decision["legal_part"] = "p1"

    def test_whole_tool_red_with_clean_part_transfer_is_recordable(self):
        self.assertEqual(self.decision["whole_tool"], "DISCARD")
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        self.assertIn("Legal basis for transfer: part p1", output)
        self.assertLess(output.index("LEGAL: RED"), output.index("aa:verdict:q1"))

    def test_red_part_still_blocks(self):
        self.ledger["legal"]["parts"][0]["flag"] = "RED"
        self.assertIn("legal RED/UNKNOWN blocks transfer", errors(self.record, self.run))

    def test_whole_tool_must_be_discarded_under_red(self):
        self.decision["whole_tool"] = "ADAPT"
        self.assertIn("whole-tool DISCARD", errors(self.record, self.run))

    def test_unknown_or_missing_part_rejected(self):
        self.decision["legal_part"] = "p9"
        self.assertIn("legal_part", errors(self.record, self.run))
        self.decision["legal_part"] = "p1"
        del self.ledger["legal"]["parts"]
        self.assertIn("legal_part", errors(self.record, self.run))

    def test_yellow_part_requires_prerequisite(self):
        self.ledger["legal"]["parts"][0]["flag"] = "YELLOW"
        self.decision["result"] = "ADAPT"
        self.assertIn("YELLOW legal flag requires ADAPT-with-prerequisite", errors(self.record, self.run))

    def test_red_without_part_still_blocks(self):
        del self.decision["legal_part"]
        self.assertIn("legal RED/UNKNOWN blocks transfer", errors(self.record, self.run))


def synthetic_rules(source=None):
    rules = {"revision": "synthetic-rules-v1", "governed_prefixes": ["src/protected/"], "governed_exact": ["src/exact.ts"],
             "measurement_dependencies": ["metrics/bridge.ts"], "policy_prefixes": [".policy/"],
             "preflight_self": ["tools/preflight.ts"], "documentation_prefixes": ["notes/"], "test_suffixes": [".test.ts"]}
    if source is not None:
        rules["source"] = source
    return rules


class PathRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "tools" / "preflight.ts").write_bytes(b"guard\r\nline\r\n")
        self.pin = {"path": "tools/preflight.ts", "sha256_lf": hashlib.sha256(b"guard\nline\n").hexdigest()}

    def tearDown(self):
        self.temp.cleanup()

    def test_freeze_checker_is_never_safe(self):
        result = aa.recipient_path_class("tools/preflight.ts", synthetic_rules())
        self.assertEqual(result["class"], "freeze-checker")
        self.assertFalse(result["safe_to_change"])

    def test_current_source_classifies_with_lf_normalisation(self):
        report = aa.classify_paths(["notes/a.md", "src/protected/x.ts", "src/x.test.ts"], synthetic_rules(self.pin), self.root)
        self.assertEqual(report["freshness"]["status"], "current")
        classes = [(r["class"], r["safe_to_change"]) for r in report["results"]]
        self.assertEqual(classes, [("docs", True), ("governed", False), ("ungoverned-needs-disposition", False)])

    def test_changed_source_fails_closed_with_warning(self):
        (self.root / "tools" / "preflight.ts").write_bytes(b"guard\nline\nnew rule\n")
        report = aa.classify_paths(["notes/a.md", "src/protected/x.ts"], synthetic_rules(self.pin), self.root)
        self.assertEqual(report["freshness"]["status"], "stale")
        self.assertTrue(report["freshness"]["warning"])
        self.assertTrue(all(r["class"] == "rules-not-current" and r["safe_to_change"] is False for r in report["results"]))
        self.assertEqual([r["pinned_class"] for r in report["results"]], ["docs", "governed"])

    def test_unchecked_or_missing_source_fails_closed(self):
        report = aa.classify_paths(["notes/a.md"], synthetic_rules(self.pin), None)
        self.assertEqual(report["freshness"]["status"], "unchecked")
        self.assertFalse(report["results"][0]["safe_to_change"])
        (self.root / "tools" / "preflight.ts").unlink()
        report = aa.classify_paths(["notes/a.md"], synthetic_rules(self.pin), self.root)
        self.assertEqual(report["freshness"]["status"], "missing")
        self.assertFalse(report["results"][0]["safe_to_change"])

    def test_unpinned_caller_rules_are_attested_not_current(self):
        report = aa.classify_paths(["notes/a.md", "tools/preflight.ts"], synthetic_rules(), None)
        self.assertEqual(report["freshness"]["status"], "caller-attested")
        self.assertEqual([r["safe_to_change"] for r in report["results"]], [True, False])

    def test_malformed_rules_and_paths_refused(self):
        for bad in ("../escape.ts", "/abs.ts", "C:/x.ts"):
            with self.subTest(bad=bad), self.assertRaises(aa.Invalid):
                aa.recipient_path_class(bad, synthetic_rules())
        broken = synthetic_rules(); del broken["test_suffixes"]
        with self.assertRaises(aa.Invalid):
            aa.recipient_path_class("notes/a.md", broken)

    # Bundled-pin cases and the profile branch of the CLI check moved to test_private_profiles.py.

    def test_cli_exit_codes(self):
        missing = subprocess.run([sys.executable, "-B", str(SCRIPT), "classify-path", "docs/a.md"], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        rules = self.root / "rules.json"
        rules.write_text(json.dumps(synthetic_rules(self.pin)), encoding="utf-8")
        current = subprocess.run([sys.executable, "-B", str(SCRIPT), "classify-path", "notes/a.md", "--rules", str(rules), "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertEqual(json.loads(current.stdout)["freshness"]["status"], "current")


class ParsedCommand(BaseException):
    def __init__(self, namespace):
        self.namespace = namespace


AA_PREFIX = 'python -B "<skill-directory>/scripts/aa.py" '


def documented_commands():
    found = []
    for doc in agent_docs():
        text = doc.read_text(encoding="utf-8")
        candidates = re.findall(r"`([^`\n]+)`", text) + [line.strip() for line in text.splitlines()]
        found.extend((doc.name, c) for c in candidates if c.startswith(AA_PREFIX))
    return found


class CommandDocsTests(unittest.TestCase):
    def test_no_cwd_relative_helper_invocations(self):
        pattern = re.compile(r"python3?\s+(?:-[A-Za-z]+\s+)*(?:\"?<skill>/)?scripts/[a-z]+\.py")
        offenders = [f"{doc.relative_to(ROOT)}: {m.group(0)}" for doc in agent_docs()
                     for m in pattern.finditer(doc.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_every_documented_aa_command_parses_without_dispatch(self):
        commands = documented_commands()
        self.assertTrue({"validate", "render", "check-output"} <= {shlex.split(c)[3] for _, c in commands if "SKILL.md" == _})
        original = aa.argparse.ArgumentParser.parse_args

        def intercept(parser, *args, **kwargs):
            raise ParsedCommand(original(parser, *args, **kwargs))

        for doc, command in commands:
            with self.subTest(doc=doc, command=command), mock.patch.object(aa.argparse.ArgumentParser, "parse_args", intercept):
                with self.assertRaises(ParsedCommand):
                    aa.main(shlex.split(command)[3:])


class RoutingDescriptionTests(unittest.TestCase):
    def test_description_routes_siblings_within_limit(self):
        description = next(line for line in read("SKILL.md").splitlines() if line.startswith("description: "))[13:]
        self.assertLessEqual(len(description), 1024)
        self.assertIn("frankenmine", description)
        self.assertIn("reverse-engineer-anything", description)


class ContextDietTests(unittest.TestCase):
    def test_agent_facing_docs_have_no_internal_note_ids(self):
        offenders = [f"{doc.relative_to(ROOT)}: {m.group(0)}" for doc in agent_docs()
                     for m in NOTE_ID.finditer(doc.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_profiles_carry_no_case_verdict_examples(self):
        for profile in (ROOT / "references" / "profiles").glob("*.md"):
            self.assertNotIn("Worked examples", profile.read_text(encoding="utf-8"), profile.name)

    def test_word_budgets(self):
        self.assertLessEqual(words("SKILL.md"), BUDGET_SKILL)
        self.assertLessEqual(loaded(BOUNDED_SET), BUDGET_BOUNDED)
        self.assertLessEqual(loaded(SKILL_DONOR_SET), BUDGET_SKILL_DONOR)

    def test_no_unpinned_install_instruction(self):
        offenders = [f"{doc.name}: {line}" for doc in agent_docs() for line in doc.read_text(encoding="utf-8").splitlines()
                     if "mcp add" in line and "@latest" in line]
        self.assertEqual(offenders, [])


# MaginotScopeTests and test_historical_archive_is_non_default moved to test_private_profiles.py.


class VersionTests(unittest.TestCase):
    def test_candidate_version_everywhere(self):
        self.assertIn(f'version: "{VERSION}"', read("SKILL.md"))
        package = (ROOT / "scripts" / "package.py").read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{VERSION}"', package)
        self.assertTrue(read("CHANGES.md").startswith(f"# adopt-adapt {VERSION}"))


if __name__ == "__main__":
    unittest.main()
