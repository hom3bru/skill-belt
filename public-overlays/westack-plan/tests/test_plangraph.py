"""Tests for westack-plan's plangraph.py: the read-only plan-graph checker.

Run from the repo root:  python -m unittest discover -s skills/westack-plan/tests -v
PLANGRAPH_UNDER_TEST=<path> points the suite at another copy (a broken-copy control).
"""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("PLANGRAPH_UNDER_TEST") or HERE.parent / "scripts" / "plangraph.py")
CORE = HERE.parent.parent / "westack"


def load():
    spec = importlib.util.spec_from_file_location("westack_plan_plangraph_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pg = load()

HEAD = """# Plan: euro and pound totals

Goal: totals print in EUR and GBP.
Plan status: draft

## Requirements
- R1: format EUR totals
- R2: format GBP totals
- R3 (withdrawn): format JPY totals

## Decisions
- D1 [implementation, repository]: keep Decimal amounts, as money.py already does

## Milestones
- M1: prefactor — the formatter has one entry point
- M2: currencies — EUR and GBP print correctly

## Slices
"""


def unit(sid, title="slice", milestone="M1", depends="none", delivers="R1", acceptance=None, rollback="revert the commit",
         status="planned", receipts="none", paths="src/money.py"):
    acceptance = [("A1", "automated", "`python -m unittest tests.test_money` passes")] if acceptance is None else acceptance
    lines = ["### %s: %s" % (sid, title)]
    if milestone is not None:
        lines.append("- Milestone: " + milestone)
    lines += ["- Depends on: " + depends, "- Delivers: " + delivers, "- Paths: " + paths]
    if acceptance:
        lines.append("- Acceptance:")
        for aid, kind, text in acceptance:
            lines.append("  - %s%s: %s" % (aid, " (%s)" % kind if kind else "", text))
    if rollback is not None:
        lines.append("- Rollback: " + rollback)
    lines += ["- Status: " + status, "- Receipts: " + receipts, ""]
    return "\n".join(lines)


def clean_plan():
    return HEAD + "\n".join([
        unit("S1", "one entry point", delivers="none"),
        unit("S2", "euro", milestone="M2", depends="S1", delivers="R1"),
        unit("S3", "pound", milestone="M2", depends="S1", delivers="R2"),
    ])


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="plan.md"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def check(self, text, name="plan.md", **kwargs):
        return pg.check_file(self.write(text, name), **kwargs)

    @staticmethod
    def codes(report, key="errors"):
        return sorted({finding["code"] for finding in report[key]})

    def finding(self, report, code, key="errors"):
        found = [f for f in report[key] if f["code"] == code]
        self.assertTrue(found, "%s not in %s" % (code, report[key]))
        return found[0]


class CleanPlanTests(Case):
    def test_a_clean_plan_has_no_findings_and_an_order(self):
        report = self.check(clean_plan())
        self.assertEqual(report["status"], "clean", report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["order"], ["S1", "S2", "S3"])
        self.assertEqual(report["slices"], 3)

    def test_the_ready_set_is_the_slices_whose_dependencies_are_done(self):
        report = self.check(clean_plan())
        self.assertEqual(report["ready"], ["S1"])
        self.assertEqual(report["waiting"], {"S2": ["S1"], "S3": ["S1"]})

    def test_the_report_names_the_plan_by_hash(self):
        path = self.write(clean_plan())
        report = pg.check_file(path)
        self.assertEqual(report["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(report["kind"], "markdown")


class GraphTests(Case):
    def test_a_dependency_on_an_undefined_slice_is_missing(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", depends="S9"))
        self.assertEqual(self.finding(report, "missing-dependency")["slice"], "S1")
        self.assertIn("S9", self.finding(report, "missing-dependency")["detail"])
        self.assertEqual(report["status"], "findings")

    def test_a_dependency_cycle_is_found_and_leaves_no_order(self):
        report = self.check(HEAD + "\n".join([
            unit("S1", delivers="R1", depends="S3"), unit("S2", delivers="R2", depends="S1"), unit("S3", delivers="none", depends="S2")]))
        cycle = self.finding(report, "cycle")
        self.assertEqual(sorted(cycle["members"]), ["S1", "S2", "S3"])
        self.assertIsNone(report["order"])
        self.assertEqual(report["ready"], [])

    def test_a_slice_that_depends_on_itself_is_a_cycle(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", depends="S1"))
        self.assertEqual(self.finding(report, "cycle")["members"], ["S1"])

    def test_duplicate_ids_are_refused(self):
        report = self.check(HEAD + unit("S1", delivers="R1") + unit("S1", delivers="R2"))
        self.assertIn("duplicate-id", self.codes(report))

    def test_a_dependency_in_a_later_milestone_breaks_phase_order(self):
        report = self.check(HEAD + unit("S1", milestone="M2", delivers="R1") + unit("S2", milestone="M1", depends="S1", delivers="R2"))
        self.assertEqual(self.finding(report, "milestone-order")["slice"], "S2")

    def test_an_undefined_milestone_is_refused(self):
        report = self.check(HEAD + unit("S1", milestone="M7", delivers="R1, R2"))
        self.assertIn("unknown-milestone", self.codes(report))


class SliceContentTests(Case):
    def test_a_slice_without_acceptance_is_flagged(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=[]))
        self.assertEqual(self.finding(report, "no-acceptance")["slice"], "S1")

    def test_a_slice_without_rollback_is_flagged(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", rollback=None))
        self.assertEqual(self.finding(report, "no-rollback")["slice"], "S1")

    def test_an_empty_rollback_is_not_a_rollback(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", rollback="none"))
        self.assertIn("no-rollback", self.codes(report))

    def test_acceptance_must_say_automated_or_human(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=[("A1", None, "it works")]))
        self.assertEqual(self.finding(report, "acceptance-without-kind")["acceptance"], "A1")

    def test_an_automated_criterion_without_a_command_is_a_warning(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=[("A1", "automated", "tests pass")]))
        self.assertEqual(report["errors"], [])
        self.assertIn("automated-without-command", self.codes(report, "warnings"))

    def test_a_human_criterion_needs_no_command(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=[("A1", "human", "finance confirms the sample")]))
        self.assertEqual(report["errors"], [])
        self.assertNotIn("automated-without-command", self.codes(report, "warnings"))

    def test_an_unknown_status_is_refused(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", status="finished"))
        self.assertIn("bad-status", self.codes(report))


class CoverageTests(Case):
    def test_an_active_requirement_with_no_slice_is_uncovered(self):
        report = self.check(HEAD + unit("S1", delivers="R1"))
        self.assertEqual(self.finding(report, "uncovered-requirement")["requirement"], "R2")

    def test_a_withdrawn_requirement_needs_no_slice(self):
        report = self.check(clean_plan())
        self.assertNotIn("R3", json.dumps(report["errors"]))

    def test_a_slice_delivering_an_unknown_requirement_is_flagged(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2, R9"))
        self.assertEqual(self.finding(report, "unknown-requirement")["requirement"], "R9")


class DoneComesFromReceiptsTests(Case):
    def test_done_without_a_receipt_is_a_claim_not_done(self):
        report = self.check(HEAD + unit("S1", delivers="R1", status="done") + unit("S2", depends="S1", delivers="R2"))
        self.assertEqual(self.finding(report, "done-without-receipt")["slice"], "S1")
        self.assertEqual(report["claimed_done"], ["S1"])
        self.assertEqual(report["done"], [])
        self.assertNotIn("S2", report["ready"])
        self.assertEqual(report["waiting"]["S2"], ["S1"])

    def test_done_with_a_receipt_for_every_criterion_releases_its_dependants(self):
        text = HEAD + unit("S1", delivers="R1", status="done", receipts="A1=E3 (task record)") + unit("S2", depends="S1", delivers="R2")
        report = self.check(text)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["done"], ["S1"])
        self.assertEqual(report["ready"], ["S2"])

    def test_receipts_may_be_listed_as_sub_items(self):
        text = HEAD + unit("S1", delivers="R1, R2", status="done", receipts="").replace(
            "- Receipts: \n", "- Receipts:\n  - A1: commit 4f2a9c1, `python -m unittest` 8 passed\n")
        report = self.check(text)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["done"], ["S1"])

    def test_one_missing_receipt_keeps_the_slice_claimed(self):
        acceptance = [("A1", "automated", "`pytest` passes"), ("A2", "automated", "`npm run lint` passes")]
        report = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=acceptance, status="done", receipts="A1=E1"))
        self.assertIn("A2", self.finding(report, "done-without-receipt")["detail"])
        self.assertEqual(report["claimed_done"], ["S1"])

    def test_a_human_criterion_needs_a_human_confirmation(self):
        acceptance = [("A1", "human", "finance confirms the sample")]
        agent = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=acceptance, status="done", receipts="A1=E4"))
        self.assertIn("done-without-receipt", self.codes(agent))
        person = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=acceptance, status="done",
                                        receipts="A1=human: Dana, 2026-10-28"))
        self.assertEqual(person["errors"], [])
        self.assertEqual(person["done"], ["S1"])

    def test_a_receipt_for_an_undefined_criterion_is_flagged(self):
        report = self.check(HEAD + unit("S1", delivers="R1, R2", status="done", receipts="A1=E1; A7=E2"))
        self.assertEqual(self.finding(report, "receipt-unknown-acceptance")["acceptance"], "A7")

    def test_a_done_slice_whose_dependency_is_not_done_is_a_warning(self):
        report = self.check(HEAD + unit("S1", delivers="R1") + unit("S2", depends="S1", delivers="R2", status="done", receipts="A1=E1"))
        self.assertIn("done-before-dependency", self.codes(report, "warnings"))

    def test_active_and_blocked_slices_are_not_ready(self):
        report = self.check(HEAD + unit("S1", delivers="R1", status="active") + unit("S2", delivers="R2", status="blocked"))
        self.assertEqual(report["ready"], [])
        self.assertEqual(report["in_progress"], ["S1"])
        self.assertEqual(report["blocked"], ["S2"])


class DecisionTests(Case):
    def test_open_product_decisions_are_listed(self):
        text = clean_plan().replace("## Milestones", "- D2 [product, open]: show the symbol before or after? Recommended: after\n\n## Milestones")
        report = self.check(text)
        self.assertEqual(report["open_decisions"], ["D2"])
        self.assertEqual(report["errors"], [])

    def test_an_approved_plan_cannot_carry_an_open_product_decision(self):
        text = clean_plan().replace("Plan status: draft", "Plan status: approved (the user, 2026-10-28)").replace(
            "## Milestones", "- D2 [product, open]: show the symbol before or after? Recommended: after\n\n## Milestones")
        report = self.check(text)
        self.assertEqual(self.finding(report, "approved-with-open-decision")["decision"], "D2")


class PreviousTests(Case):
    def test_a_stable_rerun_has_no_identity_warnings(self):
        old = self.write(clean_plan(), "old.md")
        report = self.check(clean_plan(), previous=old)
        self.assertEqual([w for w in report["warnings"] if w["code"].endswith("-slice")], [])

    def test_a_removed_unfinished_slice_and_a_retitled_one_are_reported(self):
        old = self.write(clean_plan(), "old.md")
        new = HEAD + unit("S1", "one entry point", delivers="none") + unit("S2", "euro and pound", milestone="M2", depends="S1", delivers="R1, R2")
        report = self.check(new, previous=old)
        self.assertEqual(self.finding(report, "removed-slice", "warnings")["slice"], "S3")
        self.assertEqual(self.finding(report, "retitled-slice", "warnings")["slice"], "S2")

    def test_a_removed_requirement_is_reported(self):
        old = self.write(clean_plan(), "old.md")
        new = clean_plan().replace("- R2: format GBP totals\n", "").replace("- Delivers: R2", "- Delivers: none")
        report = self.check(new, previous=old)
        self.assertEqual(self.finding(report, "removed-requirement", "warnings")["requirement"], "R2")


class RetryOfTests(Case):
    """A retry slice (`Retry of: S2`, HD-19) is for a slice that was done with receipts and whose check later failed. A
    slice marked done without receipts was never done: it keeps its id and its status is set back, so a retry that
    cites it duplicates unfinished work under a new id (the first measurement's plan runs answered NEXT: S4 for S2)."""

    @staticmethod
    def plan(s2_status="done", s2_receipts="none", retry="field"):
        s4 = unit("S4", "Retry of S2: dot check" if retry == "title" else "dot check", milestone="M2", depends="S1",
                  delivers="R1")
        if retry == "field":
            s4 = s4.replace("- Depends on:", "- Retry of: S2\n- Depends on:")
        return HEAD + "\n".join([unit("S1", "entry point", delivers="none", status="done", receipts="A1=E1"),
                                 unit("S2", "euro", milestone="M2", depends="S1", delivers="R1", status=s2_status,
                                      receipts=s2_receipts),
                                 unit("S3", "pound", milestone="M2", depends="S2", delivers="R2"), s4])

    def check_rules(self, module):
        claimed = module.check_file(self.write(self.plan()))
        found = [e for e in claimed["errors"] if e["code"] == "retry-of-unreceipted"]
        self.assertEqual([(e["slice"], e["retries"]) for e in found], [("S4", "S2")], claimed["errors"])
        self.assertIn("keep its id", found[0]["detail"])
        titled = module.check_file(self.write(self.plan(retry="title"), "titled.md"))
        self.assertIn("retry-of-unreceipted", self.codes(titled))
        unfinished = module.check_file(self.write(self.plan(s2_status="active"), "active.md"))
        self.assertIn("retry-of-unreceipted", self.codes(unfinished))

    def test_a_retry_of_a_slice_only_claimed_done_is_an_error(self):
        self.check_rules(pg)

    def test_a_retry_of_a_slice_done_with_receipts_is_the_convention_and_clean(self):
        report = self.check(self.plan(s2_receipts="A1=E2"))
        self.assertNotIn("retry-of-unreceipted", self.codes(report))
        self.assertEqual(report["errors"], [])
        self.assertIn("S4", report["ready"])

    def test_a_copy_without_the_check_lets_the_claimed_retry_through(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "if target and target in first and target not in finished:"
        self.assertEqual(source.count(old), 1)
        path = self.dir / "plangraph_without_retry_check.py"
        path.write_text(source.replace(old, "if False:"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("westack_plan_plangraph_no_retry", path)
        broken = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broken)
        with self.assertRaises(AssertionError):
            self.check_rules(broken)

    def test_a_task_record_retry_of_is_read_the_same_way(self):
        if not (CORE / "scripts" / "record.py").is_file():
            self.skipTest("the westack core is not beside this skill")
        task = TaskRecordTests.record(self)
        task["work_units"].append({"id": "w4", "goal": "pound again", "depends_on": ["w2"], "allowed_paths": ["src/parser"],
                                   "status": "planned", "acceptance_ids": ["a2"], "rollback": "revert", "retry_of": "w3"})
        report = self.check(json.dumps(task), "task.0001.json", core=CORE)
        self.assertEqual([(e["slice"], e["retries"]) for e in report["errors"] if e["code"] == "retry-of-unreceipted"],
                         [("w4", "w3")])
        task["work_units"][3]["retry_of"] = "w1"  # w1 is done with evidence
        report = self.check(json.dumps(task), "task.0002.json", core=CORE)
        self.assertNotIn("retry-of-unreceipted", self.codes(report))


@unittest.skipUnless((CORE / "scripts" / "record.py").is_file(), "the westack core is not beside this skill")
class TaskRecordTests(Case):
    def record(self):
        task = json.loads((CORE / "examples" / "task.json").read_text(encoding="utf-8"))
        task["work_units"] = [
            {"id": "w1", "goal": "one entry point", "depends_on": [], "allowed_paths": ["src/parser"], "status": "done",
             "acceptance_ids": ["a1"], "rollback": "revert"},
            {"id": "w2", "goal": "euro", "depends_on": ["w1"], "allowed_paths": ["src/parser"], "status": "planned",
             "acceptance_ids": ["a2"], "rollback": "revert"},
            {"id": "w3", "goal": "pound", "depends_on": ["w2"], "allowed_paths": ["src/parser"], "status": "done",
             "acceptance_ids": ["a2"], "rollback": None},
        ]
        task["acceptance"].append({"id": "a2", "claim": "EUR prints", "required": True, "requires_runtime": True,
                                   "requires_negative_control": False, "evidence_ids": [], "status": "not-run"})
        return task

    def test_a_task_record_is_read_through_the_core_contract(self):
        report = self.check(json.dumps(self.record()), "task.0001.json", core=CORE)
        self.assertEqual(report["kind"], "task-record")
        self.assertEqual(report["done"], ["w1"])
        self.assertEqual(report["ready"], ["w2"])
        self.assertEqual(report["claimed_done"], ["w3"])
        self.assertIn("no-rollback", self.codes(report))
        self.assertIn("done-without-receipt", self.codes(report))

    def test_a_unit_without_acceptance_ids_is_flagged(self):
        task = self.record()
        del task["work_units"][1]["acceptance_ids"]
        report = self.check(json.dumps(task), "task.0001.json", core=CORE)
        self.assertEqual(self.finding(report, "no-acceptance")["slice"], "w2")

    def test_a_record_that_breaks_the_contract_is_reported(self):
        task = self.record()
        task["work_units"][0]["status"] = "finished"
        report = self.check(json.dumps(task), "task.0001.json", core=CORE)
        self.assertIn("contract-shape", self.codes(report))

    def test_a_record_cycle_is_found(self):
        task = self.record()
        task["work_units"][0]["depends_on"] = ["w3"]
        report = self.check(json.dumps(task), "task.0001.json", core=CORE)
        self.assertIn("cycle", self.codes(report))


class OverlappingPathsTests(Case):
    """HD-14: two slices that nothing orders and that claim the same paths are a plan defect to fix before dispatch."""

    @staticmethod
    def two_parallel(a_paths, b_paths, **b):
        return HEAD + "\n".join([
            unit("S1", "entry point", delivers="none", paths="src/other.py"),
            unit("S2", "euro", milestone="M2", depends="S1", delivers="R1", paths=a_paths),
            unit("S3", "pound", milestone="M2", depends="S1", delivers="R2", paths=b_paths, **b)])

    def overlaps(self, module, a_paths, b_paths, **b):
        report = module.check_file(self.write(self.two_parallel(a_paths, b_paths, **b)))
        self.assertEqual(report["errors"], [], "an overlap is a warning, never an error")
        return [w for w in report["warnings"] if w["code"] == "overlapping-paths"]

    def check_rules(self, module):
        found = self.overlaps(module, "src/money.py", "src/money.py")
        self.assertEqual(len(found), 1, found)
        self.assertEqual(sorted([found[0]["slice"], found[0]["with"]]), ["S2", "S3"])
        self.assertIn("src/money.py", found[0]["detail"])
        self.assertEqual(len(self.overlaps(module, "src/", "src/money.py")), 1, "a folder contains its files")
        self.assertEqual(len(self.overlaps(module, "src/*.py", "src/money.py")), 1, "a glob reaches the file it matches")
        self.assertEqual(len(self.overlaps(module, "src/money.py (replace)", "src/money.py (extend)")), 1)
        self.assertIn("replace", self.overlaps(module, "src/money.py (replace)", "src/money.py (extend)")[0]["detail"])
        self.assertEqual(self.overlaps(module, "src/money.py", "src/pound.py"), [])
        self.assertEqual(self.overlaps(module, "src/money", "src/money2.py"), [], "a text prefix is not a path prefix")
        self.assertEqual(self.overlaps(module, "src/a/", "tests/a/"), [])
        self.assertEqual(self.overlaps(module, "src/money.py", "src/money.py", status="done", receipts="A1=E1"), [],
                         "a finished slice is no longer dispatched")

    def test_unordered_slices_that_claim_the_same_paths_are_warned(self):
        self.check_rules(pg)

    def test_a_copy_without_the_check_fails_the_same_assertions(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "warnings.extend(overlapping(first, nodes, edges))"
        self.assertEqual(source.count(old), 1)
        path = self.dir / "plangraph_without_overlap_check.py"
        path.write_text(source.replace(old, "pass"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("westack_plan_plangraph_broken", path)
        broken = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broken)
        with self.assertRaises(AssertionError):
            self.check_rules(broken)

    def test_slices_ordered_by_a_dependency_may_share_a_path(self):
        # S3 -> S2 -> S1: S3 and S1 are ordered through S2 even though S3 names only S2
        chain = HEAD + "\n".join([unit("S1", delivers="none"), unit("S2", milestone="M2", depends="S1", delivers="R1"),
                                  unit("S3", milestone="M2", depends="S2", delivers="R2")])
        report = pg.check_file(self.write(chain))
        self.assertEqual([w for w in report["warnings"] if w["code"] == "overlapping-paths"], [])

    def test_siblings_that_depend_on_the_same_slice_are_still_unordered(self):
        report = self.check(clean_plan())  # S2 and S3 both depend on S1 and share src/money.py
        names = [sorted([w["slice"], w["with"]]) for w in report["warnings"] if w["code"] == "overlapping-paths"]
        self.assertEqual(names, [["S2", "S3"]])

    def test_a_task_record_is_checked_the_same_way(self):
        core = HERE.parent.parent / "westack"
        if not (core / "scripts" / "record.py").is_file():
            self.skipTest("the westack core is not beside this skill")
        task = json.loads((core / "examples" / "task.json").read_text(encoding="utf-8"))
        unit_ = lambda uid, deps, paths: {"id": uid, "goal": uid, "depends_on": deps, "allowed_paths": paths,
                                          "status": "planned", "acceptance_ids": ["a1"], "rollback": "revert"}
        task["work_units"] = [unit_("w1", [], ["src/parser"]), unit_("w2", [], ["src/parser/x.py"]),
                              unit_("w3", ["w1"], ["src/parser"])]
        report = self.check(json.dumps(task), "task.0001.json", core=core)
        pairs = sorted(sorted([w["slice"], w["with"]]) for w in report["warnings"] if w["code"] == "overlapping-paths")
        self.assertEqual(pairs, [["w1", "w2"], ["w2", "w3"]])


class GateLintTests(Case):
    """SS-45: read an automated criterion's command for tautologies before trusting it. The lint is a pre-check; it
    never replaces a broken-copy run, and it reads the plan's text only (it runs nothing)."""

    @staticmethod
    def gate_plan(criterion):
        return HEAD + unit("S1", "one entry point", delivers="R1, R2", acceptance=[("A1", "automated", criterion)])

    def run_with(self, script, criterion):
        path = self.write(self.gate_plan(criterion), "gate.md")
        done = subprocess.run([sys.executable, "-B", str(script), str(path)], capture_output=True, text=True, timeout=120)
        return done.returncode, json.loads(done.stdout)

    def broken_copy(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "for code, level, detail in gate_problems(criterion[\"text\"]):"
        self.assertEqual(source.count(old), 1)
        path = self.dir / "plangraph_without_gate_lint.py"
        path.write_text(source.replace(old, "for code, level, detail in []:"), encoding="utf-8")
        return path

    def test_a_fixed_output_command_is_an_error_and_exits_1(self):
        code, report = self.run_with(SCRIPT, "`echo ok` shows ok")
        self.assertEqual(code, 1)
        found = [e for e in report["errors"] if e["code"] == "fixed-output"]
        self.assertEqual([(e["slice"], e["acceptance"]) for e in found], [("S1", "A1")])
        self.assertIn("echo ok", found[0]["detail"])

    def test_a_real_test_command_exits_0(self):
        code, report = self.run_with(SCRIPT, "`python -m unittest tests.test_money -v` shows test_euro_suffix passing")
        self.assertEqual(code, 0, report["errors"])
        self.assertEqual([w for w in report["warnings"] if w["code"] in ("fixed-output", "weak-expectation", "path-as-regex")], [])

    def test_a_copy_without_the_lint_exits_0_on_the_echo(self):
        code, report = self.run_with(self.broken_copy(), "`echo ok` shows ok")
        self.assertEqual(code, 0, "the control must lose the finding, or the lint protects nothing")
        self.assertEqual(report["errors"], [])

    def test_every_shape_of_a_gate_that_cannot_fail_is_an_error(self):
        for command in ("echo done", "printf '%s' ok", "true && echo ok", "exit 0", "pytest -q; echo ok", "pytest -q || true",
                        "echo ok | grep -q ok", "python -c \"print('ok')\"", "node -e \"console.log('ok')\""):
            with self.subTest(command=command):
                report = self.check(self.gate_plan("`%s` shows ok" % command))
                self.assertIn("fixed-output", self.codes(report), command)

    def test_a_command_that_can_fail_is_not_flagged(self):
        for command in ("pytest -q && echo ok", "pytest -q", "python -m unittest tests.test_money", "grep -c euro src/money.py",
                        "printf", "echo", "make test"):
            with self.subTest(command=command):
                report = self.check(self.gate_plan("`%s` shows euro" % command))
                self.assertNotIn("fixed-output", self.codes(report), command)

    def test_only_the_first_backticked_span_is_the_command(self):
        report = self.check(self.gate_plan("in `tests/test_money.py`, `echo ok` is printed"))
        self.assertNotIn("fixed-output", self.codes(report))

    def test_a_weak_expectation_or_a_path_used_as_a_regex_is_a_warning(self):
        weak = self.check(self.gate_plan("`grep -q ok out.txt` finds a line"))
        self.assertEqual(weak["errors"], [])
        self.assertIn("weak-expectation", self.codes(weak, "warnings"))
        path = self.check(self.gate_plan("`grep -q src/money.py README.md` finds a line"))
        self.assertEqual(path["errors"], [])
        self.assertIn("path-as-regex", self.codes(path, "warnings"))
        fine = self.check(self.gate_plan("`grep -q 'def total' src/money.py` finds a line"))
        self.assertEqual([c for c in self.codes(fine, "warnings") if c in ("weak-expectation", "path-as-regex")], [])

    def test_a_human_criterion_and_text_with_no_command_are_not_linted(self):
        human = self.check(HEAD + unit("S1", delivers="R1, R2", acceptance=[("A1", "human", "`echo ok` the owner confirms")]))
        self.assertNotIn("fixed-output", self.codes(human))
        self.assertEqual(pg.gate_problems("the claim of a task-record criterion has no backticks"), [])


class CommandLineTests(Case):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=120)

    def test_exit_codes(self):
        clean = self.write(clean_plan(), "clean.md")
        dirty = self.write(HEAD + unit("S1", delivers="R1", depends="S9"), "dirty.md")
        empty = self.write("# Notes\n\nNothing to plan here.\n", "empty.md")
        self.assertEqual(self.run_cli(clean).returncode, 0)
        self.assertEqual(self.run_cli(dirty).returncode, 1)
        self.assertEqual(self.run_cli(empty).returncode, 2)
        self.assertEqual(self.run_cli(self.dir / "absent.md").returncode, 2)
        self.assertEqual(self.run_cli().returncode, 64)

    def test_the_output_is_json_with_the_format(self):
        done = self.run_cli(self.write(clean_plan()))
        report = json.loads(done.stdout)
        self.assertEqual(report["format"], "westack-plan-graph-1")
        self.assertIn("not their truth", report["note"])

    def test_it_writes_nothing(self):
        path = self.write(clean_plan())
        before = {p.name: p.read_bytes() for p in self.dir.iterdir()}
        self.run_cli(path, "--previous", path)
        self.assertEqual({p.name: p.read_bytes() for p in self.dir.iterdir()}, before)

    def test_the_source_runs_nothing_and_opens_no_network(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for module in ("subprocess", "socket", "urllib", "http", "shutil"):
            self.assertIsNone(re.search(r"^\s*(?:import|from)\s+%s\b" % module, source, re.M), module)
        self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
