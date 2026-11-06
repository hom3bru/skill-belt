"""DS-7 and DS-8 (dsh-superagent, 2026-10-31): two rules of the ledger and the brief that were prose.

  DS-7  a user's pause or stop is a hold. It is written to the ledger as the record's `waiting_on` (the contract's own field,
        so no new key is needed): `what` reads `hold: pause by user: <why>` (or `stop`), and its check is `person-confirms`,
        the one check kind no event can satisfy. `workers.py ledger` reports `held` and so refuses a resume while the hold
        stands; a CI result, a new clue or a bot comment changes nothing, because only the user's own word lifts it, and the
        next version of the record then drops `waiting_on`. A hold whose check an event could satisfy is `hold-event-check`;
        one that names no user or no reason is `hold-incomplete`.
  DS-8  each `## Done when` item of a brief names its source on its own line: `(source: user <their words>)`,
        `(source: plan <step>)` or `(source: rule <file>)`. An item without one is `unsourced-requirement`: a brief adds no
        requirement the user, the plan or a repository rule does not state.

Run: python -B -m unittest discover -s skills/westack-orchestrate/tests -v
WORKERS_UNDER_TEST=<path> points the suite at another copy. Every rule also runs against a copy of the script with that one
condition edited out; the copy must let the bad input through. Each copy is built before its assertions.
"""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout

import test_workers as base

wk = base.wk
codes = base.codes

HOLD = dict(what="hold: stop by user: wait for the schema review", check=dict(kind="person-confirms", target="the user"),
            next_step="ask the user to lift the hold before any worker starts", expires_at="2999-01-01T00:00:00Z")


class Holds(base.RecordFixture):
    def hold(self, **changes):
        self.task["waiting_on"] = dict(copy.deepcopy(HOLD), **changes)

    def ci_success(self):
        """A passing receipt that arrived after the hold: the CI result the brief's fixture names."""
        receipt = copy.deepcopy(self.task["evidence"][0])
        receipt.update(id="e-ci", claim_id="w1", status="passed")
        self.task["evidence"].append(receipt)

    def test_an_unreleased_hold_is_held_and_refuses_a_resume(self):
        self.hold()
        report = self.ledger()
        self.assertIn("held", codes(report), report)
        self.assertNotIn("still-waiting", codes(report), "a hold is not an ordinary wait")
        self.assertEqual(report["status"], "findings")
        held = next(f for f in report["findings"] if f["code"] == "held")
        self.assertIn("wait for the schema review", held["detail"])
        self.assertIn("only the user", held["detail"])

    def test_a_ci_success_after_the_hold_lifts_nothing(self):
        self.hold()
        self.ci_success()
        report = self.ledger()
        self.assertIn("held", codes(report), report)

    def test_a_pause_is_held_like_a_stop(self):
        self.hold(what="hold: pause by user: reading the plan first")
        self.assertEqual(codes(self.ledger()) & {"held", "hold-incomplete", "hold-event-check"}, {"held"})

    def test_the_user_lifting_it_is_the_record_without_waiting_on(self):
        self.hold()
        self.assertIn("held", codes(self.ledger()))
        del self.task["waiting_on"]
        report = self.ledger()
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)

    def test_an_ordinary_wait_is_still_a_wait_and_not_a_hold(self):
        self.task["waiting_on"] = dict(what="the vendor's verdict", check=dict(kind="verdict-posted", target="PR 12"),
                                       next_step="read the verdict", expires_at="2999-01-01T00:00:00Z")
        self.assertEqual(codes(self.ledger()), {"still-waiting"})

    def test_a_hold_an_event_could_satisfy_is_flagged(self):
        for kind, extra in (("file-exists", {}), ("verdict-posted", {}), ("hash-matches", {"sha256": "0" * 64})):
            with self.subTest(kind=kind):
                self.hold(check=dict({"kind": kind, "target": "ci/result.json"}, **extra))
                report = self.ledger()
                self.assertEqual(codes(report) & {"held", "hold-event-check"}, {"held", "hold-event-check"}, report)

    def test_a_hold_that_names_no_user_or_no_reason_is_incomplete(self):
        for what in ("hold", "hold: wait", "hold: stop by user:", "hold: stop by ci: the build is red",
                     "hold: stop by a bot: reviewing"):
            with self.subTest(what=what):
                self.hold(what=what)
                self.assertEqual(codes(self.ledger()) & {"held", "hold-incomplete"}, {"held", "hold-incomplete"})

    def test_the_cli_exits_1_on_a_hold(self):
        self.hold()
        out = io.StringIO()
        with redirect_stdout(out):
            code = wk.main(["ledger", str(self.save_task()), "--core", str(base.CORE)])
        self.assertEqual(code, 1)
        self.assertIn('"held"', out.getvalue())

    # ---- each condition, then its broken copy -------------------------------------------------------------------
    def test_a_copy_that_does_not_know_a_hold_treats_it_as_any_wait(self):
        self.hold()
        self.ci_success()
        module = base.broken(('    if waiting and HOLD_WORD.match(waiting["what"]):', "    if False:"))
        try:
            self.assertIn("held", codes(self.ledger()))
            seen = codes(self.ledger(module))
        finally:
            module.temp.cleanup()
        self.assertNotIn("held", seen)
        self.assertIn("still-waiting", seen, "the copy reads the hold as an ordinary wait that an event could end")

    def test_a_copy_that_lets_any_check_kind_stand_passes_an_event_checked_hold(self):
        self.hold(check=dict(kind="verdict-posted", target="PR 12"))
        module = base.broken(('        if waiting["check"]["kind"] != "person-confirms":', "        if False:"))
        try:
            self.assertIn("hold-event-check", codes(self.ledger()))
            seen = codes(self.ledger(module))
        finally:
            module.temp.cleanup()
        self.assertNotIn("hold-event-check", seen)

    def test_a_copy_that_does_not_ask_who_and_why_passes_an_incomplete_hold(self):
        self.hold(what="hold: wait")
        module = base.broken(('        if not HOLD.match(waiting["what"]):', "        if False:"))
        try:
            self.assertIn("hold-incomplete", codes(self.ledger()))
            seen = codes(self.ledger(module))
        finally:
            module.temp.cleanup()
        self.assertNotIn("hold-incomplete", seen)


def item(text, source=None):
    return text + (" (source: %s)" % source if source else "")


class Sources(base.Fixture):
    def set_items(self, wid="w1", *items):
        self.bodies[wid] = base.body(wid, items=items)

    def test_items_sourced_to_the_user_a_plan_step_or_a_rule_pass(self):
        self.set_items("w1", item("D1: the unit tests for the module pass", 'user "run the unit tests"'),
                       item("D2: the change is described in the report", "plan S3"),
                       item("D3: no new lint findings", "rule AGENTS.md"))
        report = self.plan()
        self.assertNotIn("unsourced-requirement", codes(report), report["findings"])

    def test_an_item_with_no_source_is_an_unsourced_requirement(self):
        self.set_items("w1", item("D1: the unit tests pass", "user run them"), "D2: the module is also renamed")
        report = self.plan()
        found = [f for f in report["findings"] if f["code"] == "unsourced-requirement"]
        self.assertEqual([(f["worker"], f["detail"].split()[0]) for f in found], [("w1", "D2")], report["findings"])
        self.assertEqual(report["status"], "findings")

    def test_a_source_must_be_the_user_a_plan_step_or_a_rule_with_something_after_it(self):
        for bad in ("guess", "router", "user", "plan", "rule ", "the coordinator thought of it", ""):
            with self.subTest(source=bad):
                self.set_items("w1", item("D1: the unit tests pass", bad), item("D2: reported", "plan S1"))
                found = [f for f in self.plan()["findings"] if f["code"] == "unsourced-requirement"]
                self.assertEqual([f["detail"].split()[0] for f in found], ["D1"])

    def test_the_word_source_may_be_capitalised(self):
        self.set_items("w1", "D1: the unit tests pass (Source: Rule AGENTS.md)", "D2: reported (SOURCE: user hello)")
        self.assertNotIn("unsourced-requirement", codes(self.plan()))

    def test_every_worker_is_checked(self):
        self.set_items("w2", "D1: unsourced")
        self.set_items("w1", item("D1: ok", "plan S1"), item("D2: ok", "plan S2"))
        self.set_items("w3", item("D1: ok", "plan S1"), item("D2: ok", "plan S2"))
        found = [f for f in self.plan()["findings"] if f["code"] == "unsourced-requirement"]
        self.assertEqual([f["worker"] for f in found], ["w2"])

    def test_a_copy_without_the_source_check_passes_an_unsourced_item(self):
        self.set_items("w1", item("D1: the unit tests pass", "user run them"), "D2: the module is also renamed")
        module = base.broken(('        if match and not SOURCED.search(line):', "        if False:"))
        try:
            self.assertIn("unsourced-requirement", codes(self.plan()))
            seen = codes(self.plan(module))
        finally:
            module.temp.cleanup()
        self.assertNotIn("unsourced-requirement", seen)

    def test_a_copy_that_takes_any_source_word_passes_a_source_nobody_stated(self):
        self.set_items("w1", item("D1: the unit tests pass", "guess"), item("D2: reported", "plan S1"))
        module = base.broken(('SOURCED = re.compile(r"\\(source:\\s*(?:user|plan|rule)\\s+[^)\\s][^)]*\\)", re.I)',
                              'SOURCED = re.compile(r"\\(source:", re.I)'))
        try:
            self.assertIn("unsourced-requirement", codes(self.plan()))
            seen = codes(self.plan(module))
        finally:
            module.temp.cleanup()
        self.assertNotIn("unsourced-requirement", seen)


if __name__ == "__main__":
    unittest.main()
