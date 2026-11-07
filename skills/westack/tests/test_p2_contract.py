"""P2 adoption, contract group (g6): every change is an optional field or an optional object, so schema 1 stays
schema 1 and every older record, including the frozen 0.2.0 fixture, stays valid. A field that is absent never makes
a record fail; where an item asks for a failure that older records would also hit, the check is a note (see the
needs-decision list in the changelog). Every input is synthetic and local; the helper runs nothing.

Coverage by group: receipts (reason codes EV-10, check definition EV-39, producer stamp EV-43), the record chain
(hash links EV-42/HD-39, base revision GS-65, exclusions EV-44, regressions EV-41), work units (done needs passing
evidence EV-50, checkpoint GS-63, never reopened HD-19, one claimant with a lease HD-47), actions (what was shown
GS-15), findings (lapsing waiver GS-16), stops (HD-46), delegates (deadline WA-11), starts (WA-03), and the
decision/observation set (confirmation WB-14, driver and reasons WB-15, lifecycle WB-17, relations WB-18,
follow-ups WB-43, memory snapshot CM-56)."""
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest

import test_westack as fixtures
from test_round2 import Records, Workspace, cli, event, out, sha, write

v = fixtures.v
ROOT = fixtures.ROOT
FUTURE, PAST = "2999-01-01T00:00:00Z", "2020-01-01T00:00:00Z"

NEW_FIELDS = {
    "task": ["previous_sha256", "base_revision", "stop"],
    "work_unit": ["reason", "checkpoint", "retry_of", "claim"],
    "action": ["shown", "request_id", "answered_by", "cause", "phase"],
    "evidence": ["reason", "definition", "producer"],
    "finding": ["waived_patch_id"],
    "decision": ["because", "alternative_reasons", "confirmation", "relations", "cites_memory"],
    "observation": ["entries"],
    "event": ["resolves"],
    "delegate": ["start_by", "deadline_at"],
}


class P2(Records):
    """In-memory record checks with a notes channel."""

    def notes(self, task=None, previous=None):
        found = []
        self.errors(task, previous, notes=found)
        return found

    def assertNote(self, text, **kw):
        found = self.notes(**kw)
        self.assertTrue(any(text in n for n in found), found)

    def assertNoNote(self, text, **kw):
        found = self.notes(**kw)
        self.assertFalse(any(text in n for n in found), found)

    def assertClean(self, **kw):
        self.assertEqual(self.errors(**kw), [])

    def decision(self, **changes):
        item = dict(id="d1", question="Which shape?", choice="object", alternatives=["tuple", "dict"],
                    origin="user", status="active", supersedes=None)
        item.update(changes)
        return item

    def decide(self, *items):
        self.task["decisions"] = list(items)


class CompatTests(P2):
    def test_the_frozen_0_2_0_record_is_still_valid_and_has_none_of_the_new_fields(self):
        folder = ROOT / "tests/fixtures/v1-0.2.0"
        record = v.read_json(folder / "task.json")
        self.assertEqual(v.shape(record, v.CONTRACT["root"]), [])
        self.assertEqual(v.check_task(record, folder, {k: record[k] for k in ("revision", "scope_id", "patch_id")}), [])
        self.assertEqual(v.CONTRACT["schema_version"], 1)
        self.assertEqual(v.CONTRACT["$defs"]["task"]["properties"]["schema_version"]["enum"], [1])

    def test_every_new_field_is_optional_and_exists(self):
        defs = v.CONTRACT["$defs"]
        for name, fields in NEW_FIELDS.items():
            for field in fields:
                with self.subTest(object=name, field=field):
                    self.assertIn(field, defs[name]["properties"])
                    self.assertNotIn(field, defs[name]["required"])

    def test_an_older_record_with_older_style_decisions_and_units_gets_notes_never_errors(self):
        self.in_progress()
        self.decide(self.decision(id="d1", status="superseded"),
                    self.decision(id="d2", origin="assumption", supersedes="d1"))
        self.task["work_units"] = [dict(id="w1", goal="g", depends_on=[], allowed_paths=["src/parser"],
                                        status="blocked")]
        self.assertClean()
        found = self.notes()
        self.assertTrue(any("without a stated driver" in n for n in found), found)

    def test_the_cli_task_report_of_an_older_record_still_passes(self):
        folder = ROOT / "tests/fixtures/v1-0.2.0"
        record = v.read_json(folder / "task.json")
        done = cli("task", folder / "task.json", "--root", folder, "--scope", "local-read-v1", "--revision",
                   "fixture-v1", "--patch", record["patch_id"])
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(out(done)["errors"], [])


class ReasonCodeTests(P2):
    """EV-10: a blocked, not-run or inconclusive receipt carries a fixed reason code, so reasons can be counted."""

    def receipt(self, rid="b1", status="blocked", **changes):
        item = dict(self.task["evidence"][0], id=rid, claim_id="a1", status=status, limitations=["could not run"])
        if status != "inconclusive":
            item.update(collected=0, executed=0, passed=0, failed=0, skipped=0, exit_code=None, expected_exit=None)
        item.update(changes)
        self.task["evidence"].append(item)
        return item

    def test_each_code_validates_on_each_unfinished_status(self):
        for code in ("missing-prerequisite", "denied", "timeout", "crash", "unparseable", "no-oracle", "flaky",
                     "cap-reached"):
            for status in ("blocked", "not-run", "inconclusive"):
                with self.subTest(code=code, status=status):
                    self.task["evidence"] = self.task["evidence"][:1]
                    reason = dict(code=code, observed="130 s", limit="120 s")
                    self.receipt(status=status, reason=reason)
                    self.assertClean()

    def test_the_code_list_is_closed(self):
        self.receipt(reason=dict(code="gave-up"))
        self.assertError("evidence[1].reason.code: value outside enum")
        self.task["evidence"][1]["reason"] = dict(code="denied", why="x")
        self.assertError("evidence[1].reason: unknown key why")
        self.task["evidence"][1]["reason"] = "timeout"
        self.assertError("evidence[1].reason: expected object")

    def test_a_reason_belongs_only_on_a_receipt_that_did_not_finish(self):
        self.task["evidence"][0]["reason"] = dict(code="denied")
        self.assertError("e1: a reason code applies only to blocked, not-run or inconclusive receipts")

    def test_a_timeout_or_cap_records_the_value_seen_and_the_limit(self):
        for code in ("timeout", "cap-reached"):
            with self.subTest(code=code):
                self.task["evidence"] = self.task["evidence"][:1]
                self.receipt(reason=dict(code=code, observed="130 s"))
                self.assertError("b1: a " + code + " reason records the observed value and the limit")
                self.task["evidence"][1]["reason"]["limit"] = "120 s"
                self.assertClean()

    def test_free_text_alone_is_counted_as_no_reason_given_and_stays_outstanding(self):
        self.receipt("b1", reason=dict(code="denied"))
        self.receipt("b2")
        self.receipt("n1", status="not-run")
        tally = v.reason_tally(self.task)
        self.assertEqual({k: sorted(x) for k, x in tally.items()}, {"denied": ["b1"], "no-reason-given": ["b2", "n1"]})
        self.assertClean()
        self.assertNote("reason codes: ")
        self.assertNote("no-reason-given 2 (b2, n1)")

    def test_a_record_with_no_unfinished_receipt_has_no_tally_note(self):
        self.assertEqual(v.reason_tally(self.task), {})
        self.assertNoNote("reason codes")


class ReasonCodeCliTests(Workspace):
    def unfinished(self, n, rid, *extra, status="blocked"):
        return cli("receipt", self.path(n), "--root", self.ev, "--repo", self.repo, "--id", rid, "--claim", "a1",
                   "--type", "unit", "--operation", "node --test", "--environment", "node 24", "--status", status,
                   *extra)

    def test_a_blocked_receipt_with_neither_a_code_nor_text_is_refused(self):
        self.assertEqual(self.init().returncode, 0)
        refused = self.unfinished(1, "b1")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("--reason-code", refused.stdout)
        self.assertFalse(self.path(2).exists())

    def test_a_code_is_recorded_and_tallied(self):
        self.assertEqual(self.init().returncode, 0)
        done = self.unfinished(1, "b1", "--reason-code", "timeout", "--reason-observed", "130 s",
                               "--reason-limit", "120 s")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        receipt = v.read_json(self.path(2))["evidence"][-1]
        self.assertEqual(receipt["reason"], dict(code="timeout", observed="130 s", limit="120 s"))
        notes = out(self.task(2))["notes"]
        self.assertTrue(any("timeout 1 (b1)" in n for n in notes), notes)

    def test_free_text_alone_is_accepted_and_counted_as_no_reason_given(self):
        self.assertEqual(self.init().returncode, 0)
        done = self.unfinished(1, "b1", "--limitation", "node is not installed")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("reason", v.read_json(self.path(2))["evidence"][-1])
        notes = out(self.task(2))["notes"]
        self.assertTrue(any("no-reason-given 1 (b1)" in n for n in notes), notes)

    def test_a_timeout_without_its_numbers_is_refused(self):
        self.assertEqual(self.init().returncode, 0)
        refused = self.unfinished(1, "b1", "--reason-code", "timeout")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("observed value and the limit", refused.stdout)


class DefinitionTests(Workspace):
    """EV-39: a receipt records a hash of the check's definition (command, expected exit, the files that define
    it) and the tool version. Changing a definition file makes the receipt stale though the patch is identical."""

    def passed_record(self, *extra):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        done = self.receipt(2, "e1", "--claim", "a1", "--link", "--tool-version", "node 24.1",
                            "--definition-path", "test/add.test.js", *extra)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return v.read_json(self.path(3))

    def test_the_writer_records_the_hash_the_version_and_the_paths(self):
        receipt = self.passed_record()["evidence"][-1]
        files = [("test/add.test.js", sha(self.repo / "test/add.test.js"))]
        self.assertEqual(receipt["definition"], dict(
            sha256=v.definition_hash(receipt["operation"], receipt["expected_exit"], files),
            tool_version="node 24.1", paths=["test/add.test.js"]))

    def test_a_definition_file_edited_outside_the_fingerprint_stales_the_receipt_with_the_patch_unchanged(self):
        record = self.passed_record()
        self.assertEqual(out(self.task(3))["errors"], [])
        write(self.repo, {"test/add.test.js": "// asserts nothing now\n"})
        report = out(self.task(3))
        self.assertTrue(any("e1: check definition changed" in e for e in report["errors"]), report)
        self.assertFalse(any("current host-observed patch_id" in e for e in report["errors"]), report)
        result = cli("refresh", self.path(3), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = v.read_json(self.path(4))
        self.assertEqual(after["patch_id"], record["patch_id"])
        self.assertEqual(after["evidence"][-1]["status"], "stale")
        self.assertEqual(after["acceptance"][0]["status"], "not-run")
        self.assertEqual(out(self.task(4, "--previous", self.path(3)))["errors"], [])

    def test_a_receipt_without_a_definition_is_never_stale_for_that_reason(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--link").returncode, 0)
        write(self.repo, {"test/add.test.js": "// asserts nothing now\n"})
        self.assertEqual(out(self.task(3))["errors"], [])

    def test_without_a_repository_the_definition_is_not_evaluated_and_the_report_says_so(self):
        self.passed_record()
        done = cli("task", self.path(3), "--root", self.ev, "--scope", "s1", "--revision", "no-vcs")
        self.assertTrue(any("definition" in n and "--repo" in n for n in out(done)["notes"]), out(done))

    def test_a_missing_definition_file_reads_as_a_changed_definition(self):
        record = self.passed_record()
        (self.repo / "test/add.test.js").unlink()
        why = v.definition_drift(record["evidence"][-1], self.repo)
        self.assertIn("unreadable", why)

    def test_a_definition_path_must_stay_inside_the_repository(self):
        self.assertEqual(self.init().returncode, 0)
        refused = self.receipt(1, "e1", "--claim", "a1", "--definition-path", "../outside.txt")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertFalse(self.path(2).exists())


class DefinitionRecordTests(P2):
    def test_a_stale_receipt_that_matches_the_patch_needs_a_definition_to_be_stale(self):
        self.in_progress()
        self.task["acceptance"][0]["status"] = "not-run"
        self.task["evidence"][0]["status"] = "stale"
        self.assertError("e1: marked stale but matches the current patch and scope")
        self.task["evidence"][0]["definition"] = dict(sha256="a" * 64, tool_version="node 24", paths=[])
        self.assertClean()

    def test_the_definition_object_is_checked(self):
        self.task["evidence"][0]["definition"] = dict(sha256="XYZ", tool_version="node 24", paths=[])
        self.assertError("evidence[0].definition.sha256: pattern mismatch")
        self.task["evidence"][0]["definition"] = dict(sha256="a" * 64, tool_version="node 24", paths=["../x"])
        self.assertError("e1: nonportable definition path: ../x")
        self.task["evidence"][0]["definition"] = dict(sha256="a" * 64, paths=[])
        self.assertError("evidence[0].definition: missing tool_version")


class ProducerTests(P2):
    """EV-43: a receipt may carry a self-declared producer stamp; it is a claim, not a signature."""

    def setUp(self):
        super().setUp()
        write(self.root, {"review.txt": "Reviewer B read the patch.\n"})
        self.stamp = dict(tool="claude-code", context_id="fresh", requested_model="model-a", observed_model="model-a")
        self.task["evidence"].append(dict(self.task["evidence"][0], id="rev-e", claim_id="rev1", type="review",
                                          raw_output="review.txt", raw_sha256=sha(self.root / "review.txt"),
                                          exit_code=None, expected_exit=None, operation="read review",
                                          producer=self.stamp))
        self.review = dict(id="rev1", author_id=self.task["author_id"], reviewer_id="reviewer-b", context_id="fresh",
                           patch_id=self.task["patch_id"], kind="independent", status="completed",
                           evidence_ids=["rev-e"], finding_ids=[], level="fresh-context-same-model")
        self.task["reviews"] = [self.review]
        self.task["independent_review_required"] = True

    def test_a_stamp_that_matches_the_review_is_accepted(self):
        self.assertClean()

    def test_an_independent_review_receipt_stamped_by_the_author_is_flagged(self):
        self.stamp["context_id"] = self.task["author_id"]
        self.assertError("rev1: independent review backed by receipt rev-e stamped by the author")

    def test_a_stamp_that_names_another_context_than_the_review_is_refused(self):
        self.stamp["context_id"] = "someone-else"
        self.assertError("rev1: receipt rev-e was stamped by context someone-else, not the review's context fresh")

    def test_a_receipt_with_no_stamp_is_never_refused_for_it(self):
        del self.task["evidence"][1]["producer"]
        self.assertClean()

    def test_the_stamp_needs_a_tool_and_a_context(self):
        del self.stamp["tool"]
        self.assertError("evidence[1].producer: missing tool")

    def test_an_unobserved_model_reads_unknown_and_a_substitution_is_reported(self):
        del self.stamp["observed_model"]
        self.assertNote("observed model unknown: rev-e")
        self.stamp["observed_model"] = "model-b"
        self.assertNote("rev-e: requested model-a, observed model-b")
        self.assertNoNote("observed model unknown")


class ProducerCliTests(Workspace):
    def test_the_writer_stamps_the_producer_and_writes_unknown_for_an_unobserved_model(self):
        self.assertEqual(self.init().returncode, 0)
        done = self.receipt(1, "e1", "--claim", "a1", "--producer-tool", "claude-code", "--producer-context", "ctx-7",
                            "--requested-model", "model-a")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        stamp = v.read_json(self.path(2))["evidence"][-1]["producer"]
        self.assertEqual(stamp, dict(tool="claude-code", context_id="ctx-7", requested_model="model-a",
                                     observed_model="unknown"))

    def test_a_context_without_a_tool_is_refused(self):
        self.assertEqual(self.init().returncode, 0)
        refused = self.receipt(1, "e1", "--claim", "a1", "--producer-context", "ctx-7")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("--producer-tool", refused.stdout)


class ChainLinkTests(Workspace):
    """EV-42 and HD-39: each version the helper writes carries the SHA-256 of the version before it."""

    def three(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(self.receipt(1, "e1", "--claim", "a1").returncode, 0)
        self.assertEqual(self.receipt(2, "e2", "--claim", "a1").returncode, 0)

    def test_writers_link_each_version_to_the_bytes_before_it(self):
        self.three()
        self.assertNotIn("previous_sha256", v.read_json(self.path(1)))
        self.assertEqual(v.read_json(self.path(2))["previous_sha256"], sha(self.path(1)))
        self.assertEqual(v.read_json(self.path(3))["previous_sha256"], sha(self.path(2)))
        cli("refresh", self.path(3), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")
        self.assertEqual(v.read_json(self.path(4))["previous_sha256"], sha(self.path(3)))

    def test_an_intact_chain_passes_and_says_what_the_link_cannot_prove(self):
        self.three()
        report = out(self.task(3, "--chain", self.ev))
        self.assertEqual(report["errors"], [])
        text = " ".join(report["notes"])
        self.assertIn("newest version", text)
        self.assertIn("who wrote", text)

    def test_editing_an_earlier_version_breaks_the_chain_at_the_next_one_and_names_it(self):
        self.three()
        edited = v.read_json(self.path(2))
        edited["next_safe_action"] = "edited after version 3 existed"
        self.path(2).write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
        report = out(self.task(3, "--chain", self.ev))
        broken = [e for e in report["errors"] if "previous_sha256" in e]
        self.assertTrue(broken and broken[0].startswith("task.0003.json:") and "task.0002.json" in broken[0], report)

    def test_deleting_the_newest_version_is_not_detected_and_the_report_says_so(self):
        self.three()
        self.path(3).unlink()
        report = out(self.task(2, "--chain", self.ev))
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("newest version" in n for n in report["notes"]), report)

    def test_a_chain_that_never_linked_is_reported_unlinked_and_still_passes(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        self.save(2, record)
        report = out(self.task(2, "--chain", self.ev))
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("no version carries previous_sha256" in n for n in report["notes"]), report)

    def test_a_hand_copied_version_that_repeats_its_predecessors_link_is_unlinked_not_a_break(self):
        self.three()
        copied = v.read_json(self.path(3))
        copied["next_safe_action"] = "hand-written next version"
        self.save(4, copied)
        report = out(self.task(4, "--chain", self.ev))
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("unlinked" in n and "task.0004.json" in n for n in report["notes"]), report)

    def test_previous_checks_the_single_link_too(self):
        self.three()
        self.assertEqual(out(self.task(3, "--previous", self.path(2)))["errors"], [])
        edited = v.read_json(self.path(2))
        edited["next_safe_action"] = "edited later"
        self.path(2).write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
        errors = out(self.task(3, "--previous", self.path(2)))["errors"]
        self.assertTrue(any("previous_sha256" in e for e in errors), errors)

    def test_the_hash_must_be_lowercase_hex(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["previous_sha256"] = "XYZ"
        self.assertTrue(any("previous_sha256: pattern mismatch" in e for e in v.shape(record, v.CONTRACT["root"])))


class BaseRevisionTests(P2):
    """GS-65: the revision the task started from is recorded once and never moves; the ancestry test itself is
    one git command the resumer runs (the helper starts no process)."""

    def test_the_base_revision_cannot_change_or_vanish_between_versions(self):
        self.in_progress()
        self.task["base_revision"] = "a" * 40
        previous = copy.deepcopy(self.task)
        self.assertClean(previous=previous)
        self.task["base_revision"] = "b" * 40
        self.assertError("base_revision changed", previous=previous)
        del self.task["base_revision"]
        self.assertError("base_revision removed", previous=previous)

    def test_it_may_be_added_once_to_a_record_that_never_had_one(self):
        self.in_progress()
        previous = copy.deepcopy(self.task)
        self.task["base_revision"] = "a" * 40
        self.assertClean(previous=previous)


class BaseRevisionCliTests(Workspace):
    def test_init_records_the_starting_revision_and_refresh_keeps_it(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        self.assertEqual(record["base_revision"], record["revision"])
        cli("refresh", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "moved-on")
        after = v.read_json(self.path(2))
        self.assertEqual((after["revision"], after["base_revision"]), ("moved-on", record["base_revision"]))


class ExclusionTests(P2):
    """EV-44: widening what the fingerprint ignores, or narrowing what it observes, is a relaxation."""

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task["fingerprint"] = dict(paths=["src/parser"], exclude=["build"], baseline=self.task["patch_id"])
        self.previous = copy.deepcopy(self.task)

    def test_baseline_pair_is_valid(self):
        self.assertClean(previous=self.previous)

    def test_widening_the_exclusions_within_a_scope_is_refused(self):
        self.task["fingerprint"]["exclude"].append("src/parser/generated")
        self.assertError("fingerprint exclusion widened: src/parser/generated within an unchanged scope",
                         previous=self.previous)

    def test_an_exclusion_already_covered_is_not_widening(self):
        self.task["fingerprint"]["exclude"].extend(["build", "src/build"])
        self.assertClean(previous=self.previous)

    def test_narrowing_the_observed_paths_within_a_scope_is_refused(self):
        self.previous["fingerprint"]["paths"] = ["src/parser", "tests"]
        self.assertError("fingerprint path narrowed: tests within an unchanged scope", previous=self.previous)

    def test_observing_more_is_never_a_relaxation(self):
        self.task["fingerprint"]["paths"] = ["src/parser", "tests"]
        self.assertClean(previous=self.previous)

    def test_the_same_edit_under_a_new_scope_with_a_reasoned_event_passes(self):
        self.task["fingerprint"]["exclude"].append("vendor")
        self.task["scope_id"] = "scope-2"
        for item in self.task["evidence"]:
            item["status"] = "stale"
        self.task["acceptance"][0].update(status="not-run", evidence_ids=[])
        self.assertError("relaxed under a scope change without a history event", previous=self.previous)
        self.task["history"].append(event("h-scope", "implemented", "implemented", self.task,
                                          reason="User allowed vendored files to be ignored"))
        self.assertClean(previous=self.previous)

    def test_observed_paths_that_only_follow_the_allowed_paths_narrow_with_them(self):
        plain = copy.deepcopy(self.task)
        del plain["fingerprint"]
        previous = copy.deepcopy(plain)
        plain["authority"]["allowed_paths"] = ["src/parser/new"]
        self.assertEqual([e for e in self.errors(plain, previous) if "narrowed" in e], [])

    def test_a_record_that_gains_a_fingerprint_equal_to_the_default_is_not_a_relaxation(self):
        plain = copy.deepcopy(self.task)
        del plain["fingerprint"]
        previous = copy.deepcopy(plain)
        paths, excludes = v.definition(plain)
        plain["fingerprint"] = dict(paths=paths, exclude=excludes)
        self.assertEqual(self.errors(plain, previous), [])


class ExclusionCliTests(Workspace):
    def test_refresh_refuses_to_widen_the_exclusions_without_a_scope_change(self):
        self.assertEqual(self.init().returncode, 0)
        refused = cli("refresh", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                      "--exclude", "src/util.js")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("--scope", refused.stdout)
        self.assertFalse(self.path(2).exists())
        allowed = cli("refresh", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                      "--exclude", "src/util.js", "--scope", "s2", "--reason", "User excluded the generated util")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)


class RegressionTests(Workspace):
    """EV-41: a criterion that passed earlier and now fails is regressed; the report names the last passing
    receipt and the files changed since."""

    def regressed_chain(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--link").returncode, 0)
        write(self.repo, {"src/add.js": "module.exports=(a,b)=>a-b;\n"})
        self.assertEqual(cli("refresh", self.path(3), "--root", self.ev, "--repo", self.repo,
                             "--revision", "no-vcs").returncode, 0)
        failed = self.receipt(4, "e2", "--claim", "a1", "--link", "--status", "failed", passed=0, failed=1,
                              exit_code=1)
        self.assertEqual(failed.returncode, 0, failed.stdout + failed.stderr)

    def test_the_chain_report_names_the_last_passing_receipt_and_the_files_changed_since(self):
        self.regressed_chain()
        notes = out(self.task(5, "--chain", self.ev))["notes"]
        hit = [n for n in notes if n.startswith("a1 regressed")]
        self.assertTrue(hit, notes)
        self.assertIn("e1", hit[0])
        self.assertIn("task.0003.json", hit[0])
        self.assertIn("src/add.js", hit[0])

    def test_a_plain_failure_with_no_earlier_pass_is_not_called_regressed(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--link", "--status", "failed", passed=0, failed=1,
                                      exit_code=1).returncode, 0)
        notes = out(self.task(3, "--chain", self.ev))["notes"]
        self.assertFalse([n for n in notes if "regressed" in n], notes)

    def test_a_flip_between_two_versions_on_the_same_patch_is_regressed_with_no_files_changed(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--link").returncode, 0)
        self.assertEqual(self.receipt(3, "e2", "--claim", "a1", "--link", "--status", "failed", passed=0, failed=1,
                                      exit_code=1).returncode, 0)
        notes = out(self.task(4, "--previous", self.path(3)))["notes"]
        hit = [n for n in notes if n.startswith("a1 regressed")]
        self.assertTrue(hit and "no files changed" in hit[0], notes)


class UnitEvidenceTests(P2):
    """EV-50: a work unit reads done only when every criterion tied to it passes."""

    def unit(self, **changes):
        item = dict(id="w1", goal="parser", depends_on=[], allowed_paths=["src/parser"], status="done",
                    acceptance_ids=["a1"])
        item.update(changes)
        self.task["work_units"] = [item]
        return item

    def test_a_done_unit_tied_to_a_passing_criterion_is_valid(self):
        self.unit()
        self.assertClean()

    def test_a_done_unit_tied_to_a_criterion_that_does_not_pass_is_refused(self):
        self.in_progress()
        self.unit()
        for status in ("not-run", "failed", "blocked", "inconclusive"):
            with self.subTest(status=status):
                self.task["acceptance"][0]["status"] = status
                self.assertError("w1: marked done but acceptance a1 is " + status)

    def test_a_unit_that_is_not_done_may_wait_on_its_criteria(self):
        self.in_progress()
        self.unit(status="active")
        self.task["acceptance"][0]["status"] = "not-run"
        self.assertClean()

    def test_a_done_unit_with_no_tied_criteria_is_unchanged(self):
        self.unit(acceptance_ids=[])
        self.assertClean()
        del self.task["work_units"][0]["acceptance_ids"]
        self.assertClean()

    def test_every_tied_criterion_must_pass(self):
        self.in_progress()
        self.task["acceptance"].append(dict(self.task["acceptance"][0], id="a2", status="not-run", evidence_ids=[]))
        self.unit(acceptance_ids=["a1", "a2"])
        self.assertError("w1: marked done but acceptance a2 is not-run")

    def test_a_blocked_unit_without_a_reason_is_a_note_and_a_reason_silences_it(self):
        self.in_progress()
        self.unit(status="blocked", acceptance_ids=[])
        self.assertClean()
        self.assertNote("w1: blocked without a reason")
        self.task["work_units"][0]["reason"] = "waiting on the vendor's fix"
        self.assertNoNote("blocked without a reason")


class UnitLifecycleTests(P2):
    """HD-19: a finished unit is never reopened; the retry is a new unit that names the old one."""

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task["work_units"] = [dict(id="w1", goal="parser", depends_on=[], allowed_paths=["src/parser"],
                                        status="done")]
        self.previous = copy.deepcopy(self.task)

    def test_a_done_unit_going_back_to_active_is_refused(self):
        for status in ("active", "planned", "blocked"):
            with self.subTest(status=status):
                self.task["work_units"][0]["status"] = status
                self.assertError("work unit w1 was done and cannot be reopened", previous=self.previous)

    def test_a_new_unit_naming_the_old_one_is_accepted(self):
        self.task["work_units"].append(dict(id="w1b", goal="parser, second attempt", depends_on=[],
                                            allowed_paths=["src/parser"], status="active", retry_of="w1"))
        self.assertClean(previous=self.previous)

    def test_retry_of_must_name_another_unit_of_the_record(self):
        self.task["work_units"].append(dict(id="w1b", goal="g", depends_on=[], allowed_paths=["src/parser"],
                                            status="active", retry_of="ghost"))
        self.assertError("w1b: retry_of names no work unit: ghost")
        self.task["work_units"][1]["retry_of"] = "w1b"
        self.assertError("w1b: retry_of names itself")

    def test_a_unit_that_was_not_done_may_change_freely(self):
        self.previous["work_units"][0]["status"] = "active"
        self.task["work_units"][0]["status"] = "planned"
        self.assertClean(previous=self.previous)

    def test_the_checkpoint_is_a_recorded_pre_state(self):
        self.task["work_units"][0].update(rollback="git reset --hard to the checkpoint", checkpoint="a" * 40)
        self.assertClean()
        self.task["work_units"][0]["checkpoint"] = ""
        self.assertError("work_units[0].checkpoint: empty string")


class ClaimTests(P2):
    """HD-47: a unit has at most one claimant with a lease; an expired lease prompts inspection, it does not
    prove the worker stopped, and only an inspected unit goes back to the queue."""

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.claim = dict(owner="worker-1", state="claimed", expires_at=FUTURE)
        self.unit = dict(id="w1", goal="parser", depends_on=[], allowed_paths=["src/parser"], status="active",
                         claim=self.claim)
        self.task["work_units"] = [self.unit]

    def test_a_live_claim_is_valid_and_silent(self):
        self.assertClean()
        self.assertNoNote("lease")

    def test_an_expired_lease_is_a_note_that_asks_for_inspection(self):
        self.claim["expires_at"] = PAST
        self.assertClean()
        self.assertNote("w1: lease held by worker-1 expired at " + PAST)
        self.assertNote("does not show the worker stopped")

    def test_a_claimed_or_lapsed_unit_cannot_sit_in_the_queue(self):
        self.unit["status"] = "planned"
        for state in ("claimed", "lapsed"):
            with self.subTest(state=state):
                self.claim["state"] = state
                self.assertError("w1: a claimed unit is not queued")

    def test_an_inspected_claim_says_what_was_inspected_and_may_be_queued(self):
        self.unit["status"] = "planned"
        self.claim["state"] = "inspected"
        self.assertError("w1: claim inspected without saying what was inspected")
        self.claim["inspection"] = "read the worker's branch; no commit landed"
        self.assertClean()

    def test_dropping_the_claim_does_not_skip_the_inspection(self):
        previous = copy.deepcopy(self.task)
        previous["work_units"][0]["claim"]["state"] = "lapsed"
        self.unit["status"] = "planned"
        del self.unit["claim"]
        self.assertError("w1: returned to planned without inspecting the claimant's target", previous=previous)

    def test_a_finished_unit_may_drop_its_claim(self):
        previous = copy.deepcopy(self.task)
        self.unit["status"] = "done"
        del self.unit["claim"]
        self.assertClean(previous=previous)

    def test_the_claim_shape_is_one_object_with_a_closed_state_list(self):
        self.unit["claim"] = [self.claim]
        self.assertError("work_units[0].claim: expected object")
        self.unit["claim"] = dict(owner="w", state="running", expires_at=FUTURE)
        self.assertError("work_units[0].claim.state: value outside enum")
        self.unit["claim"] = dict(owner="w", state="claimed", expires_at="soon")
        self.assertError("w1: claim.expires_at: not an ISO timestamp with a timezone")


class ActionShownTests(P2):
    """GS-15: an approval records the text the person was shown, and it must contain the pinned target."""

    def action(self, **changes):
        item = dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                    scope_id=self.task["scope_id"], occurrence="o1", decision="pending", outcome="not-applied",
                    evidence_ids=[])
        item.update(changes)
        self.task["actions"] = [item]
        return item

    def test_the_recorded_text_must_contain_the_target(self):
        self.in_progress()
        self.action(shown="Write src/parser/a.py (cwd repo, env names: none)", request_id="r-9", answered_by="user")
        self.assertClean()
        self.task["actions"][0]["shown"] = "Write the file"
        self.assertError("act-1: the text shown to the person does not contain the pinned target")

    def test_an_action_with_no_shown_text_is_unchanged(self):
        self.in_progress()
        self.action(decision="approved")
        self.assertClean()

    def test_open_approvals_are_listed_for_the_handoff(self):
        self.in_progress()
        self.action(request_id="r-9")
        self.assertNote("open approval act-1 (local-write src/parser/a.py, request r-9)")
        self.task["actions"][0].update(decision="approved", outcome="applied", answered_by="user")
        self.assertNoNote("open approval")

    def test_an_action_with_no_stable_target_cannot_be_recorded_at_all(self):
        self.in_progress()
        self.action(target_hash="not-a-hash")
        self.assertError("actions[0].target_hash: pattern mismatch")
        del self.task["actions"][0]["target_hash"]
        self.assertError("actions[0]: missing target_hash")


class ActionCauseTests(P2):
    """HD-35: a started step with no confirmed result is `uncertain` with a cause and a phase, so a resume lists the
    unmatched steps first and lets the cause pick the retry. The outcome words are unchanged."""

    def action(self, **changes):
        item = dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                    scope_id=self.task["scope_id"], occurrence="o1", decision="approved", outcome="uncertain",
                    evidence_ids=[])
        item.update(changes)
        self.task["actions"] = [item]
        return item

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.before = copy.deepcopy(self.task)

    def test_the_cause_list_is_closed_and_the_outcome_words_are_unchanged(self):
        props = v.CONTRACT["$defs"]["action"]["properties"]
        self.assertEqual(props["cause"]["enum"], ["cancelled", "failed", "truncated", "refused", "abandoned"])
        self.assertEqual(props["outcome"]["enum"], ["not-applied", "applied", "uncertain", "denied"])
        self.action(cause="truncated", phase="mid-edit")
        self.assertClean()
        self.action(cause="gave-up")
        self.assertError("actions[0].cause: value outside enum")
        self.action(phase="")
        self.assertError("actions[0].phase: empty string")

    def test_an_uncertain_step_without_a_cause_is_a_note_never_an_error_on_its_own(self):
        self.action()
        self.assertClean()
        self.assertNote("uncertain steps without a cause: act-1")

    def test_resume_lists_the_unmatched_steps_with_their_cause_and_phase(self):
        self.action(cause="truncated", phase="mid-edit")
        self.assertNote("unmatched steps (inspect each without replaying it): act-1 (cause truncated, phase mid-edit)")
        self.assertNoNote("without a cause")
        self.action(outcome="applied")
        self.assertNoNote("unmatched steps")

    def test_a_step_that_newly_ends_uncertain_must_say_why(self):
        self.action()
        self.assertError("act-1: a step that ended without a confirmed result records why it ended (cause)",
                         previous=self.before)
        self.action(cause="cancelled")
        self.assertClean(previous=self.before)

    def test_moving_to_uncertain_from_another_outcome_must_say_why_too(self):
        self.action(outcome="not-applied")
        previous = copy.deepcopy(self.task)
        self.task["actions"][0]["outcome"] = "uncertain"
        self.assertError("act-1: a step that ended without a confirmed result", previous=previous)

    def test_a_step_that_was_already_uncertain_in_an_older_record_is_not_newly_refused(self):
        self.action()
        previous = copy.deepcopy(self.task)
        self.assertClean(previous=previous)

    def test_the_cause_survives_reconciliation(self):
        self.action(cause="truncated", phase="mid-edit")
        previous = copy.deepcopy(self.task)
        self.task["actions"][0]["outcome"] = "applied"
        errors = self.errors(previous=previous)
        self.assertFalse([e for e in errors if "cause" in e], errors)
        self.assertEqual(self.task["actions"][0]["cause"], "truncated")


class WaiverTests(P2):
    """GS-16: a deferred finding stores the patch it was accepted at; the waiver holds only while it matches."""

    def finding(self, **changes):
        item = dict(id="f1", claim="slow path", location="src/parser/a.py:3", consequence="slow on big input",
                    evidence_ids=[], severity="low", severity_rationale="rare", correction="cache it",
                    adjudication="deferred", rationale="user accepted the cost", verification_ids=[])
        item.update(changes)
        self.task["findings"] = [item]
        return item

    def test_a_waiver_that_matches_the_patch_holds(self):
        self.finding(waived_patch_id=self.task["patch_id"])
        self.assertClean()
        self.assertNoNote("waiver lapsed")

    def test_after_an_edit_the_waiver_lapses_and_a_final_record_cannot_carry_it(self):
        self.finding(waived_patch_id="e" * 64)
        self.assertError("f1: waiver lapsed (accepted at eeeeeeeeeeee..., patch is now")

    def test_in_progress_the_lapse_is_a_note(self):
        self.in_progress()
        self.finding(waived_patch_id="e" * 64)
        self.assertClean()
        self.assertNote("f1: waiver lapsed")

    def test_a_deferred_finding_without_a_snapshot_is_a_note_not_an_error(self):
        self.finding()
        self.assertClean()
        self.assertNote("deferred findings without a waiver snapshot: f1")

    def test_a_snapshot_belongs_only_on_a_deferred_finding(self):
        self.finding(adjudication="rejected", waived_patch_id=self.task["patch_id"])
        self.assertError("f1: a waiver snapshot applies only to a deferred finding")

    def test_a_malformed_snapshot_is_refused_and_so_cannot_hold_a_waiver(self):
        self.finding(waived_patch_id="XYZ")
        self.assertError("findings[0].waived_patch_id: pattern mismatch")


class StopTests(P2):
    """HD-46: stopped on purpose (do not resume) is recorded apart from interrupted (resume me)."""

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task.update(state="partial", completion="partial", history=fixtures.history(
            self.task["patch_id"], "framed", "inspected", "authorized-work", "implemented", "partial",
            scope=self.task["scope_id"]))

    def stop(self, kind="on-purpose", reason="User withdrew the request"):
        self.task["stop"] = dict(kind=kind, reason=reason)

    def test_a_stopped_record_is_valid_and_reports_what_resume_must_do(self):
        self.stop()
        self.assertClean()
        self.assertNote("stopped on purpose: do not resume without the user's say-so (User withdrew the request)")
        self.stop("interrupted", "host crashed mid-edit")
        self.assertNote("interrupted: host crashed mid-edit; resume from next_safe_action")

    def test_a_stopped_record_cannot_be_final(self):
        self.stop("interrupted", "host crashed")
        self.task.update(state="verified", completion="open", verification="runtime-tested")
        self.assertError("completion contradicts stop")

    def test_the_kind_list_is_closed_and_a_reason_is_required(self):
        self.task["stop"] = dict(kind="paused", reason="x")
        self.assertError("stop.kind: value outside enum")
        self.task["stop"] = dict(kind="interrupted")
        self.assertError("stop: missing reason")

    def test_a_stopped_on_purpose_marker_is_not_overwritten_by_a_routine_update(self):
        self.stop()
        previous = copy.deepcopy(self.task)
        self.assertClean(previous=previous)
        del self.task["stop"]
        self.assertError("stop marker (on purpose) changed or removed within an unchanged scope", previous=previous)
        self.stop("interrupted", "different")
        self.assertError("stop marker (on purpose) changed or removed", previous=previous)

    def test_the_user_can_resume_under_a_new_scope_with_a_reasoned_event(self):
        self.stop()
        previous = copy.deepcopy(self.task)
        del self.task["stop"]
        self.task["scope_id"] = "scope-2"
        for item in self.task["evidence"]:
            item["status"] = "stale"
        self.task["acceptance"][0].update(status="not-run", evidence_ids=[])
        self.task["history"].append(event("h-resume", "partial", "partial", self.task,
                                          reason="User said to resume after all"))
        self.assertClean(previous=previous)

    def test_an_interrupted_marker_clears_on_resume_without_ceremony(self):
        self.stop("interrupted", "host crashed")
        previous = copy.deepcopy(self.task)
        del self.task["stop"]
        self.assertClean(previous=previous)


class DeadlineTests(P2):
    """WA-11: the deadline is an absolute time fixed when the work starts; a resume cannot extend it."""

    def entry(self, **changes):
        item = dict(id="d1", parent=self.task["id"], executor="host subagent", tier="mid", scope="read src",
                    status="running", continuable=True)
        item.update(changes)
        self.task["delegates"] = [item]
        return item

    def test_the_clocks_validate(self):
        self.in_progress()
        self.entry(start_by="2999-01-01T00:00:00Z", deadline_at="2999-01-02T00:00:00Z")
        self.assertClean()
        self.entry(deadline_at="tomorrow")
        self.assertError("d1: deadline_at: not an ISO timestamp with a timezone")
        self.entry(start_by="2999-01-03T00:00:00Z", deadline_at="2999-01-02T00:00:00Z")
        self.assertError("d1: start_by is after deadline_at")

    def test_a_running_delegate_past_its_deadline_reads_budget_exhausted(self):
        self.in_progress()
        self.entry(deadline_at=PAST)
        self.assertClean()
        self.assertNote("d1: deadline_at passed (" + PAST + ") while still running: read it as budget-exhausted")

    def test_a_delegate_that_has_ended_is_not_reported_past_its_deadline(self):
        self.in_progress()
        self.entry(deadline_at=PAST, status="finished", outcome=dict(disposition="landed", ref="x"))
        self.assertNoNote("deadline_at passed")

    def test_a_resume_cannot_extend_or_drop_the_deadline(self):
        self.in_progress()
        self.entry(deadline_at="2999-01-02T00:00:00Z")
        previous = copy.deepcopy(self.task)
        self.assertClean(previous=previous)
        self.task["delegates"][0]["deadline_at"] = "2999-01-09T00:00:00Z"
        self.assertError("delegate d1: deadline_at moved later", previous=previous)
        del self.task["delegates"][0]["deadline_at"]
        self.assertError("delegate d1: deadline_at removed", previous=previous)
        self.task["delegates"][0]["deadline_at"] = "2999-01-01T12:00:00Z"
        self.assertClean(previous=previous)

    def test_the_same_id_with_another_scope_names_both(self):
        self.in_progress()
        self.entry()
        previous = copy.deepcopy(self.task)
        self.task["delegates"][0]["scope"] = "write src"
        self.assertError("delegate identity changed: d1 (scope was 'read src', now 'write src')", previous=previous)


class StartIdempotenceTests(Workspace):
    """WA-03: a start is keyed by its task id. A repeated start returns the open record; the same id with another
    goal is an error naming both goals; an ended record frees the id."""

    def start(self, goal="Add numbers", path=None, task_id="new-task"):
        return cli("init", path or self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                   "--goal", goal, "--scope", "s1", "--author", "agent-a", "--task-id", task_id,
                   "--allow-path", "src")

    def test_a_repeated_start_returns_the_first_record_and_writes_nothing(self):
        self.assertEqual(self.start().returncode, 0)
        first = self.path(1).read_bytes()
        again = self.start()
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        report = out(again)
        self.assertEqual((report["status"], pathlib_name(report["path"])), ("existing-open", "task.0001.json"))
        self.assertEqual(report["sha256"], sha(self.path(1)))
        self.assertEqual(self.path(1).read_bytes(), first)
        self.assertFalse(self.path(2).exists())

    def test_the_same_id_with_another_goal_is_an_error_naming_both_goals(self):
        self.assertEqual(self.start().returncode, 0)
        first = self.path(1).read_bytes()
        clash = self.start("Delete numbers")
        self.assertEqual(clash.returncode, 1, clash.stdout)
        self.assertIn("'Add numbers'", clash.stdout)
        self.assertIn("'Delete numbers'", clash.stdout)
        self.assertEqual(self.path(1).read_bytes(), first)

    def test_another_path_in_the_same_folder_finds_the_open_record(self):
        self.assertEqual(self.start().returncode, 0)
        again = self.start(path=self.ev / "elsewhere.0001.json")
        self.assertEqual(out(again)["status"], "existing-open")
        self.assertFalse((self.ev / "elsewhere.0001.json").exists())

    def test_a_different_task_id_is_a_different_task(self):
        self.assertEqual(self.start().returncode, 0)
        other = self.start("Other work", path=self.ev / "other.0001.json", task_id="other-task")
        self.assertEqual(other.returncode, 0, other.stdout + other.stderr)

    def test_an_ended_record_frees_its_id(self):
        self.assertEqual(self.start().returncode, 0)
        record = v.read_json(self.path(1))
        record.update(state="delivered", completion="complete")
        self.path(1).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        fresh = self.start("A new goal for the same id", path=self.ev / "again.0001.json")
        self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)
        self.assertEqual(out(fresh)["status"], "created-incomplete")

    def test_the_latest_version_decides_whether_the_record_is_open(self):
        self.assertEqual(self.start().returncode, 0)
        record = v.read_json(self.path(1))
        self.assertEqual(self.start().returncode, 0)
        record.update(state="delivered", completion="complete")
        self.save(2, record)
        fresh = self.start("Add numbers", path=self.ev / "again.0001.json")
        self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)
        self.assertEqual(out(fresh)["status"], "created-incomplete")


def pathlib_name(path):
    return re.split(r"[\\/]", path)[-1]


class DecisionSetTests(P2):
    """WB-15: a decision cites the driver it satisfies and keeps a reason for each rejected alternative."""

    def test_because_and_a_reason_for_each_alternative_validate(self):
        self.decide(self.decision(because="Callers already destructure objects",
                                  alternative_reasons=[dict(alternative="tuple", reason="Position-coupled"),
                                                       dict(alternative="dict", reason="Duplicates the object keys")]))
        self.assertClean()
        self.assertNoNote("without a stated driver")

    def test_an_older_decision_is_reported_incomplete_in_a_note(self):
        self.decide(self.decision())
        self.assertClean()
        self.assertNote("decisions without a stated driver: d1")
        self.assertNote("alternatives without a reason: d1 (tuple, dict)")

    def test_a_reason_must_name_a_listed_alternative_once(self):
        self.decide(self.decision(alternative_reasons=[dict(alternative="list", reason="x")]))
        self.assertError("d1: alternative_reasons names an alternative that is not listed: list")
        self.decide(self.decision(alternative_reasons=[dict(alternative="tuple", reason="x"),
                                                       dict(alternative="tuple", reason="y")]))
        self.assertError("d1: alternative_reasons repeats tuple")

    def test_an_empty_driver_or_reason_is_refused_by_shape(self):
        self.decide(self.decision(because=""))
        self.assertError("decisions[0].because: empty string")
        self.decide(self.decision(alternative_reasons=[dict(alternative="tuple", reason="")]))
        self.assertError("decisions[0].alternative_reasons[0].reason: empty string")

    def test_a_proposal_must_be_complete_before_the_user_is_asked(self):
        self.decide(self.decision(status="proposed"))
        self.assertError("d1: a proposed decision states its driver (because)")
        self.assertError("d1: a proposed decision gives a reason for each alternative (missing: tuple, dict)")
        self.decide(self.decision(status="proposed", because="x",
                                  alternative_reasons=[dict(alternative="tuple", reason="a"),
                                                       dict(alternative="dict", reason="b")]))
        self.assertClean()

    def test_a_proposal_with_no_alternatives_needs_only_its_driver(self):
        self.decide(self.decision(status="proposed", alternatives=[], because="only one way"))
        self.assertClean()


class DecisionLifecycleTests(P2):
    """WB-17: proposed, rejected and deprecated beside active and superseded, moving forward only; the user's
    answer is a history event that resolves the decision."""

    def proposed(self, **changes):
        return self.decision(status="proposed", because="x", alternatives=[], **changes)

    def setUp(self):
        super().setUp()
        self.in_progress()

    def test_the_status_words(self):
        enum = v.CONTRACT["$defs"]["decision"]["properties"]["status"]["enum"]
        self.assertEqual(sorted(enum), ["active", "deprecated", "proposed", "rejected", "superseded"])

    def test_the_forward_table(self):
        self.assertEqual({k: sorted(x) for k, x in v.DECISION_NEXT.items()},
                         {"proposed": ["active", "rejected"], "active": ["deprecated", "superseded"],
                          "deprecated": ["superseded"], "rejected": [], "superseded": []})

    def test_a_proposal_becomes_active_only_with_an_event_that_resolves_it(self):
        self.decide(self.proposed())
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "active"
        self.assertError("decision d1 moved from proposed to active without a history event that resolves it",
                         previous=previous)
        self.task["history"].append(event("h-accept", "implemented", "implemented", self.task,
                                          reason="User accepted d1", resolves=["d1"]))
        self.assertClean(previous=previous)

    def test_a_rejection_needs_the_same_event(self):
        self.decide(self.proposed())
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "rejected"
        self.assertError("decision d1 moved from proposed to rejected without a history event that resolves it",
                         previous=previous)
        self.task["history"].append(event("h-no", "implemented", "implemented", self.task,
                                          reason="User declined d1", resolves=["d1"]))
        self.assertClean(previous=previous)

    def test_the_event_must_give_a_reason_and_name_real_decisions(self):
        self.decide(self.proposed())
        self.task["history"].append(event("h-x", "implemented", "implemented", self.task, resolves=["d1"]))
        self.assertError("h-x: resolves needs a reason")
        self.task["history"][-1].update(reason="User answered", resolves=["ghost"])
        self.assertError("h-x: resolves names no decision: ghost")

    def test_nothing_moves_backward(self):
        for old, new in (("rejected", "active"), ("rejected", "proposed"), ("superseded", "active"),
                         ("deprecated", "active"), ("active", "proposed"), ("deprecated", "proposed")):
            with self.subTest(move=old + "->" + new):
                self.decide(self.decision(status=old, because="x", alternatives=[]))
                previous = copy.deepcopy(self.task)
                self.task["decisions"][0]["status"] = new
                self.assertError("decision d1 status cannot move from " + old + " to " + new, previous=previous)

    def test_active_may_be_deprecated_and_a_deprecated_one_may_be_superseded(self):
        self.decide(self.decision(because="x", alternatives=[]))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "deprecated"
        self.assertClean(previous=previous)
        later = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "superseded"
        self.task["decisions"].append(self.decision(id="d2", supersedes="d1", because="y", alternatives=[]))
        self.assertClean(previous=later)

    def test_a_draft_may_be_edited_until_it_moves_and_not_after(self):
        self.decide(self.proposed())
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["choice"] = "array"
        self.assertClean(previous=previous)
        self.task["decisions"][0].update(status="active")
        self.task["history"].append(event("h-accept", "implemented", "implemented", self.task,
                                          reason="User accepted d1", resolves=["d1"]))
        self.assertError("decision d1 rewritten", previous=previous)

    def test_a_decision_is_never_removed_even_while_proposed(self):
        self.decide(self.proposed())
        previous = copy.deepcopy(self.task)
        self.decide()
        self.assertError("decision d1 removed", previous=previous)

    def test_an_assumption_written_active_is_a_note_not_an_error_for_now(self):
        previous = copy.deepcopy(self.task)
        self.decide(self.decision(origin="assumption", because="x", alternatives=[]))
        self.assertClean(previous=previous)
        self.assertNote("decision d1: an assumption written as active", previous=previous)

    def test_a_user_or_repository_decision_may_start_active_without_a_note(self):
        previous = copy.deepcopy(self.task)
        self.decide(self.decision(origin="user", because="x", alternatives=[]))
        self.assertNoNote("an assumption written as active", previous=previous)

    def test_a_proposal_is_reported_as_binding_nothing(self):
        self.decide(self.proposed())
        self.assertNote("decision d1 is proposed: it binds nothing until the user accepts it")


class DecisionRelationTests(P2):
    """WB-18: supersedes may name several; typed relations are stored once, in the later record; the reverse
    view is derived."""

    def setUp(self):
        super().setUp()
        self.in_progress()

    def base(self):
        return [self.decision(id="d1", status="superseded"), self.decision(id="d2", status="superseded"),
                self.decision(id="d3", supersedes=["d1", "d2"])]

    def test_supersedes_accepts_null_a_string_or_a_list(self):
        for value in (None, "d1", ["d1"], ["d1", "d2"]):
            with self.subTest(value=value):
                self.decide(self.decision(id="d1", status="superseded"), self.decision(id="d2", status="superseded"),
                            self.decision(id="d3", supersedes=value))
                self.assertClean()
        self.decide(self.decision(supersedes=3))
        self.assertError("decisions[0].supersedes: expected string/array/null")

    def test_one_decision_may_supersede_two(self):
        self.decide(*self.base())
        self.assertClean()

    def test_every_superseded_target_must_be_superseded_and_exist(self):
        base = self.base()
        base[1]["status"] = "active"
        self.decide(*base)
        self.assertError("d3: superseded decision missing/still active")
        base[1]["status"] = "superseded"
        base[2]["supersedes"] = ["d1", "ghost"]
        self.decide(*base)
        self.assertError("d3: superseded decision missing/still active")

    def test_a_supersession_cycle_through_a_list_is_found(self):
        self.decide(self.decision(id="d1", status="superseded", supersedes=["d2"]),
                    self.decision(id="d2", status="superseded", supersedes=["d3", "d1"]),
                    self.decision(id="d3", status="superseded", supersedes=["d1"]))
        self.assertError("supersession cycle")

    def test_a_superseded_decision_that_no_successor_names_is_a_note_for_now(self):
        self.decide(self.decision(id="d1", status="superseded"))
        self.assertClean()
        self.assertNote("decision d1 is superseded but no decision names it in supersedes")

    def test_naming_a_superseded_decision_silences_that_note(self):
        self.decide(*self.base())
        self.assertNoNote("is superseded but no decision names it")

    def test_a_proposed_successor_does_not_force_the_old_decision_out_yet(self):
        self.decide(self.decision(id="d1"), self.decision(id="d2", status="proposed", because="x", alternatives=[],
                                                          supersedes="d1"))
        self.assertClean()

    def test_relations_name_a_known_other_decision(self):
        self.decide(self.decision(id="d1"), self.decision(id="d2", relations=[dict(type="amends", target="d1")]))
        self.assertClean()
        self.decide(self.decision(id="d1"), self.decision(id="d2", relations=[dict(type="amends", target="ghost")]))
        self.assertError("d2: relations targets unknown decision ghost")
        self.decide(self.decision(id="d2", relations=[dict(type="clarifies", target="d2")]))
        self.assertError("d2: relations targets itself")
        self.decide(self.decision(id="d1"), self.decision(id="d2", relations=[dict(type="blocks", target="d1")]))
        self.assertError("decisions[1].relations[0].type: value outside enum")

    def test_the_reverse_view_is_derived_from_the_later_record_only(self):
        self.decide(self.decision(id="d1"), self.decision(id="d2", relations=[dict(type="amends", target="d1")]),
                    self.decision(id="d3", relations=[dict(type="depends-on", target="d2")]))
        links = v.decision_links(self.task)
        self.assertEqual(links, {"d1": [("amended by", "d2")], "d2": [("depended on by", "d3")]})
        self.assertNote("decision links (derived): d1 amended by d2; d2 depended on by d3")
        self.assertNotIn("amended_by", v.CONTRACT["$defs"]["decision"]["properties"])

    def test_a_string_turning_into_a_one_item_list_is_not_a_rewrite(self):
        self.decide(self.decision(id="d1", status="superseded"), self.decision(id="d2", supersedes="d1"))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][1]["supersedes"] = ["d1"]
        self.assertClean(previous=previous)
        self.task["decisions"][1]["supersedes"] = None
        self.assertError("decision d2 rewritten", previous=previous)

    def test_recorded_relations_and_reasons_are_append_only(self):
        self.decide(self.decision(id="d1"), self.decision(id="d2", because="x", relations=[dict(type="amends",
                                                                                                   target="d1")]))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][1]["because"] = "something else"
        self.assertError("decision d2 rewritten", previous=previous)
        self.task["decisions"][1]["because"] = "x"
        self.task["decisions"][1]["relations"] = []
        self.assertError("decision d2 rewritten", previous=previous)
        self.task["decisions"][1]["relations"] = [dict(type="amends", target="d1"),
                                                  dict(type="clarifies", target="d1")]
        self.assertClean(previous=previous)


class ConfirmationTests(P2):
    """WB-14: a decision may name the check that confirms it; until a passing receipt covers that check it reads
    decided but unconfirmed. The status of the decision never decides it."""

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task["acceptance"][0]["status"] = "not-run"
        self.decide(self.decision(because="x", alternatives=[],
                                  confirmation=dict(check="no module imports the old parser")))

    def receipt(self, rid="e2", claim="d1", **changes):
        item = dict(self.task["evidence"][0], id=rid, claim_id=claim)
        item.update(changes)
        self.task["evidence"].append(item)
        return item

    def test_without_a_citing_receipt_it_is_decided_but_unconfirmed(self):
        self.assertClean()
        self.assertNote("decision d1: decided but unconfirmed (check: no module imports the old parser)")
        self.assertNote("not implemented")

    def test_a_passing_receipt_that_names_the_decision_confirms_it(self):
        self.receipt()
        self.assertNote("decision d1: confirmed by e2")
        self.assertNoNote("unconfirmed")

    def test_a_receipt_may_name_it_among_several_claims(self):
        self.receipt(claim="a1", claim_ids=["a1", "d1"])
        self.assertNote("decision d1: confirmed by e2")

    def test_a_receipt_that_did_not_pass_or_is_stale_confirms_nothing(self):
        self.receipt(status="failed", passed=0, failed=1, exit_code=1)
        self.receipt("e3", patch_id="e" * 64, status="stale")
        self.assertNote("decision d1: decided but unconfirmed")

    def test_a_passing_acceptance_criterion_named_by_the_decision_confirms_it(self):
        self.task["decisions"][0]["confirmation"]["acceptance_id"] = "a1"
        self.assertNote("decided but unconfirmed")
        self.task["acceptance"][0]["status"] = "passed"
        self.assertNote("decision d1: confirmed by acceptance a1")

    def test_the_named_criterion_must_exist(self):
        self.task["decisions"][0]["confirmation"]["acceptance_id"] = "ghost"
        self.assertError("d1: confirmation.acceptance_id names no acceptance criterion: ghost")

    def test_a_confirmed_flag_cannot_be_written_into_the_record(self):
        self.task["decisions"][0]["confirmation"]["confirmed"] = True
        self.assertError("decisions[0].confirmation: unknown key confirmed")
        del self.task["decisions"][0]["confirmation"]["confirmed"]
        self.task["decisions"][0]["confirmed"] = True
        self.assertError("decisions[0]: unknown key confirmed")

    def test_a_proposed_decision_is_not_yet_decided_so_it_is_not_reported_unconfirmed(self):
        self.task["decisions"][0].update(status="proposed")
        self.assertNoNote("decided but unconfirmed")

    def test_the_confirmation_is_fixed_once_recorded(self):
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["confirmation"]["check"] = "nothing at all"
        self.assertError("decision d1 rewritten", previous=previous)

    def test_a_decision_id_is_an_ordinary_claim_so_the_writer_needs_no_change(self):
        self.assertIn("claim_id", v.CONTRACT["$defs"]["evidence"]["properties"])
        self.assertEqual(v.CONTRACT["$defs"]["evidence"]["properties"]["claim_id"], dict(type="string", minLength=1))
        self.assertTrue(v.supports(dict(claim_id="d1"), "d1"))
        self.assertTrue(v.supports(dict(claim_id="a1", claim_ids=["a1", "d1"]), "d1"))


class ConfirmationCliTests(Workspace):
    def test_receipt_claim_may_name_a_decision_id_end_to_end(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["decisions"] = [dict(id="d1", question="Shape?", choice="object", alternatives=[], origin="user",
                                    status="active", supersedes=None, because="callers destructure",
                                    confirmation=dict(check="parser tests pass"))]
        self.save(2, record)
        unconfirmed = [n for n in out(self.task(2))["notes"] if n.startswith("decision d1")]
        self.assertTrue(unconfirmed and "unconfirmed" in unconfirmed[0], unconfirmed)
        done = self.receipt(2, "e1", "--claim", "d1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        confirmed = [n for n in out(self.task(3))["notes"] if n.startswith("decision d1")]
        self.assertTrue(confirmed and "confirmed by e1" in confirmed[0], confirmed)

    def test_link_on_a_decision_id_says_why_nothing_was_linked(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["decisions"] = [dict(id="d1", question="Shape?", choice="object", alternatives=[], origin="user",
                                    status="active", supersedes=None)]
        self.save(2, record)
        done = self.receipt(2, "e1", "--claim", "d1", "--link")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        notes = out(done)["notes"]
        self.assertTrue(any("d1 is a decision" in n for n in notes), notes)
        self.assertFalse(any("is not an acceptance criterion" in n for n in notes), notes)


class ObservationTests(P2):
    """WB-43 and CM-56: a follow-up kind keeps 'noticed, not touched' in the record; a memory-read observation
    holds the snapshot of host memory taken once at the start, and decisions cite entries from it."""

    def observe(self, *items):
        self.task["observations"] = list(items)

    def test_a_follow_up_needs_no_receipt_but_ruled_out_and_confirmed_still_do(self):
        self.observe(dict(id="o1", kind="follow-up", text="Why did no check catch the stale cache path?",
                          evidence_ids=[]))
        self.assertClean()
        self.observe(dict(id="o1", kind="ruled-out", text="not the cache", evidence_ids=[]))
        self.assertError("o1: a ruled-out observation cites the evidence behind it")
        self.observe(dict(id="o1", kind="confirmed", text="the cache", evidence_ids=[]))
        self.assertError("o1: a confirmed observation cites the evidence behind it")

    def test_the_kinds(self):
        enum = v.CONTRACT["$defs"]["observation"]["properties"]["kind"]["enum"]
        self.assertEqual(sorted(enum), ["confirmed", "follow-up", "memory-read", "ruled-out", "surprise"])

    def memory(self, entries, oid="m1"):
        return dict(id=oid, kind="memory-read", text="host memory read once at task start", evidence_ids=[],
                    entries=entries)

    def test_a_memory_read_lists_what_was_read_names_and_hashes(self):
        self.observe(self.memory([dict(name="feedback_testing.md", sha256="a" * 64)]))
        self.assertClean()
        self.observe(self.memory([]))
        self.assertClean()
        item = self.memory([])
        del item["entries"]
        self.observe(item)
        self.assertError("m1: a memory-read observation lists the entries it read")
        self.observe(self.memory([dict(name="a.md", sha256="XYZ")]))
        self.assertError("observations[0].entries[0].sha256: pattern mismatch")

    def test_entries_belong_only_to_a_memory_read(self):
        self.observe(dict(id="o1", kind="surprise", text="odd", evidence_ids=[], entries=[]))
        self.assertError("o1: entries apply only to a memory-read observation")

    def test_an_entry_is_listed_once(self):
        self.observe(self.memory([dict(name="a.md", sha256="a" * 64), dict(name="a.md", sha256="b" * 64)]))
        self.assertError("m1: memory entry a.md is listed twice")

    def test_a_decision_may_cite_only_entries_in_the_snapshot(self):
        self.observe(self.memory([dict(name="feedback_testing.md", sha256="a" * 64)]))
        self.decide(self.decision(cites_memory=["feedback_testing.md"]))
        self.assertClean()
        self.decide(self.decision(cites_memory=["saved_later.md"]))
        self.assertError("d1: cites memory entry saved_later.md that is not in the recorded memory snapshot")

    def test_a_citation_with_no_snapshot_cannot_be_audited(self):
        self.decide(self.decision(cites_memory=["feedback_testing.md"]))
        self.assertError("d1: cites memory entry feedback_testing.md but the record holds no memory-read"
                         " observation (the citation cannot be audited)")

    def test_a_record_with_no_snapshot_and_no_citation_is_unchanged(self):
        self.decide(self.decision())
        self.assertClean()

    def test_the_snapshot_cannot_be_rewritten_so_a_later_save_is_never_assumed_in_it(self):
        self.in_progress()
        self.observe(self.memory([dict(name="a.md", sha256="a" * 64)]))
        previous = copy.deepcopy(self.task)
        self.task["observations"][0]["entries"].append(dict(name="saved_later.md", sha256="b" * 64))
        self.assertError("observation rewritten: m1", previous=previous)
        self.task["observations"][0]["entries"].pop()
        self.task["observations"].append(self.memory([dict(name="saved_later.md", sha256="b" * 64)], "m2"))
        self.assertClean(previous=previous)


class ReadmeTests(unittest.TestCase):
    def test_each_new_field_is_in_the_contract_readme(self):
        readme = (ROOT / "contracts/README.md").read_text(encoding="utf-8")
        for name, fields in NEW_FIELDS.items():
            for field in fields:
                with self.subTest(field=name + "." + field):
                    self.assertRegex(readme, r"\b" + field + r"\b")

    def test_the_readme_states_the_gates_a_resumer_must_know(self):
        flat = re.sub(r"\s+", " ", (ROOT / "contracts/README.md").read_text(encoding="utf-8"))
        for phrase in ("no-reason-given", "calls hand-copied versions unlinked", "proves continuity",
                       "done unit is never reopened", "not proof the worker stopped",
                       "decided but unconfirmed", "no gate fails a record for lacking a new field"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, flat)

    def test_the_readme_states_the_compatibility_rule(self):
        flat = re.sub(r"\s+", " ", (ROOT / "contracts/README.md").read_text(encoding="utf-8"))
        self.assertRegex(flat, r"from 1\.0\.0-alpha\.5")
        self.assertIn("Records without them stay valid", flat)


def broken_core(base, name, patches):
    """A copy of the core's scripts and contract with exactly one statement replaced per patch, as (file, old, new)."""
    core = base / name
    for folder in ("scripts", "contracts"):
        shutil.copytree(ROOT / folder, core / folder, ignore=shutil.ignore_patterns("__pycache__"))
    for filename, old, new in patches:
        source = (core / "scripts" / filename).read_bytes().decode("utf-8")
        if source.count(old) != 1:
            raise AssertionError("the control must replace exactly one statement in " + filename + ": " + old[:70])
        (core / "scripts" / filename).write_bytes(source.replace(old, new).encode("utf-8"))
    return core


class ControlBase(P2):
    """Each new record gate reports on the real helper and stays silent on a copy of the core with that one
    statement removed, so the tests above are shown to detect the mechanism rather than pass by accident."""

    copies = 0

    def broken(self, old, new="pass", filename="record.py"):
        ControlBase.copies += 1
        core = broken_core(self.root, "broken-%d" % ControlBase.copies, [(filename, old, new)])
        spec = importlib.util.spec_from_file_location("broken_p2_%d" % ControlBase.copies,
                                                      core / "scripts/validate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def reports(self, module, text, previous=None, notes=False):
        context = {k: self.task[k] for k in ("revision", "scope_id", "patch_id")}
        found = []
        errors = module.check_task(copy.deepcopy(self.task), self.root, context, copy.deepcopy(previous), found)
        return any(text in x for x in (found if notes else errors))

    def assert_gate(self, text, old, new="pass", previous=None, notes=False):
        self.assertTrue(self.reports(v, text, previous, notes), "the real helper must report: " + text)
        self.assertFalse(self.reports(self.broken(old, new), text, previous, notes),
                         "the copy without the gate must stay silent about: " + text)

    def entry(self, **changes):
        item = dict(id="d1", parent=self.task["id"], executor="host subagent", tier="mid", scope="read src",
                    status="running", continuable=True)
        item.update(changes)
        return item

    def unit(self, **changes):
        item = dict(id="w1", goal="parser", depends_on=[], allowed_paths=["src/parser"], status="done")
        item.update(changes)
        self.task["work_units"] = [item]
        return item


class BrokenCopyControls(ControlBase):
    def test_reason_codes(self):
        base = dict(self.task["evidence"][0])
        self.task["evidence"][0]["reason"] = dict(code="denied")
        self.assert_gate("e1: a reason code applies only to blocked, not-run or inconclusive receipts",
                         'errors.append(label + ": a reason code applies only to blocked, not-run or inconclusive receipts")')
        self.task["evidence"][0] = dict(base, id="e1", status="blocked", collected=0, executed=0, passed=0, failed=0,
                                        skipped=0, exit_code=None, expected_exit=None, limitations=["x"],
                                        reason=dict(code="timeout"))
        self.task["acceptance"][0].update(status="not-run", evidence_ids=[])
        self.in_progress()
        self.assert_gate("e1: a timeout reason records the observed value and the limit",
                         'elif reason and reason["code"] in NEEDS_NUMBERS and not (reason.get("observed") and reason.get("limit")):',
                         "elif False:")

    def test_the_tally_note(self):
        self.task["evidence"].append(dict(self.task["evidence"][0], id="b1", status="blocked", collected=0, executed=0,
                                          passed=0, failed=0, skipped=0, exit_code=None, expected_exit=None,
                                          limitations=["x"]))
        self.assert_gate("no-reason-given 1 (b1)", 'item.get("reason", {}).get("code", "no-reason-given")',
                         'item.get("reason", {}).get("code", "timeout")', notes=True)

    def producer_scenario(self, context):
        write(self.root, {"review.txt": "Reviewer B read the patch.\n"})
        self.task["evidence"].append(dict(self.task["evidence"][0], id="rev-e", claim_id="rev1", type="review",
                                          raw_output="review.txt", raw_sha256=sha(self.root / "review.txt"),
                                          exit_code=None, expected_exit=None, operation="read review",
                                          producer=dict(tool="claude-code", context_id=context)))
        self.task["reviews"] = [dict(id="rev1", author_id=self.task["author_id"], reviewer_id="reviewer-b",
                                     context_id="fresh", patch_id=self.task["patch_id"], kind="independent",
                                     status="completed", evidence_ids=["rev-e"], finding_ids=[],
                                     level="fresh-context-same-model")]
        self.task["independent_review_required"] = True

    def test_the_producer_gates(self):
        self.producer_scenario("someone-else")
        self.assert_gate("rev1: receipt rev-e was stamped by context someone-else",
                         'if stamp and stamp["context_id"] != review["context_id"]:', "if False:")
        self.task["evidence"] = self.task["evidence"][:1]
        self.producer_scenario(self.task["author_id"])
        self.assert_gate("rev1: independent review backed by receipt rev-e stamped by the author",
                         'if stamp and review["kind"] == "independent" and stamp["context_id"] == review["author_id"]:',
                         "if False:")

    def test_exclusions_and_the_regression_note(self):
        self.in_progress()
        self.task["fingerprint"] = dict(paths=["src/parser"], exclude=["build"], baseline=self.task["patch_id"])
        previous = copy.deepcopy(self.task)
        self.task["fingerprint"]["exclude"].append("vendor")
        self.assert_gate("fingerprint exclusion widened: vendor",
                         'relaxed.extend("fingerprint exclusion widened: " + item for item in new_excludes if not covers(old_excludes, item))',
                         "pass", previous=previous)
        self.task["fingerprint"]["exclude"] = ["build"]
        self.task["fingerprint"]["paths"] = ["src/parser"]
        previous["fingerprint"]["paths"] = ["src/parser", "tests"]
        self.assert_gate("fingerprint path narrowed: tests",
                         "if explicit and portable(item) and not within(item, new_paths))", "if False)", previous=previous)

    def test_the_regression_note(self):
        self.in_progress()
        previous = copy.deepcopy(self.task)
        self.task["acceptance"][0]["status"] = "failed"
        self.assert_gate("a1 regressed", 'if was and criterion["status"] == "failed":', "if False:",
                         previous=previous, notes=True)

    def test_the_done_unit_gate(self):
        self.in_progress()
        self.unit(acceptance_ids=["a1"])
        self.task["acceptance"][0]["status"] = "not-run"
        self.assert_gate("w1: marked done but acceptance a1 is not-run",
                         'if aid in criteria and criteria[aid]["status"] != "passed")', "if False)")

    def test_the_reopen_and_claim_gates(self):
        self.in_progress()
        self.unit()
        previous = copy.deepcopy(self.task)
        self.task["work_units"][0]["status"] = "active"
        self.assert_gate("work unit w1 was done and cannot be reopened",
                         'if old["status"] == "done" and new["status"] != "done":', "if False:", previous=previous)
        self.unit(status="planned", claim=dict(owner="w", state="claimed", expires_at=FUTURE))
        self.assert_gate("w1: a claimed unit is not queued",
                         'if unit["status"] == "planned" and claim["state"] in {"claimed", "lapsed"}:', "if False:")
        previous = copy.deepcopy(self.task)
        previous["work_units"][0].update(status="active")
        del self.task["work_units"][0]["claim"]
        self.assert_gate("w1: returned to planned without inspecting the claimant's target",
                         'if (old.get("claim", {}).get("state") in {"claimed", "lapsed"} and new["status"] == "planned"',
                         'if (False and new["status"] == "planned"', previous=previous)

    def test_the_shown_gate(self):
        self.in_progress()
        self.task["actions"] = [dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                                     scope_id=self.task["scope_id"], occurrence="o1", decision="pending",
                                     outcome="not-applied", evidence_ids=[], shown="Write the file")]
        self.assert_gate("act-1: the text shown to the person does not contain the pinned target",
                         'if "shown" in action and action["target"] not in action["shown"]:', "if False:")

    def test_the_new_uncertain_step_gate(self):
        self.in_progress()
        previous = copy.deepcopy(self.task)
        self.task["actions"] = [dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                                     scope_id=self.task["scope_id"], occurrence="o1", decision="approved",
                                     outcome="uncertain", evidence_ids=[])]
        self.assert_gate("act-1: a step that ended without a confirmed result records why it ended (cause)",
                         'for item in current["actions"] if item["outcome"] == "uncertain" and "cause" not in item',
                         'for item in current["actions"] if False and "cause" not in item', previous=previous)

    def test_the_lapsed_waiver_gate(self):
        self.task["findings"] = [dict(id="f1", claim="slow", location="a:1", consequence="slow", evidence_ids=[],
                                      severity="low", severity_rationale="rare", correction="cache",
                                      adjudication="deferred", rationale="accepted", verification_ids=[],
                                      waived_patch_id="e" * 64)]
        self.assert_gate("f1: waiver lapsed", "(errors if final else notes).append(", "notes.append(")

    def test_the_stop_gates(self):
        self.in_progress()
        self.task.update(state="partial", completion="partial", history=fixtures.history(
            self.task["patch_id"], "framed", "inspected", "authorized-work", "implemented", "partial",
            scope=self.task["scope_id"]))
        self.task["stop"] = dict(kind="on-purpose", reason="withdrawn")
        previous = copy.deepcopy(self.task)
        del self.task["stop"]
        self.assert_gate("stop marker (on purpose) changed or removed",
                         'if previous.get("stop", {}).get("kind") == "on-purpose" and current.get("stop") != previous["stop"]:',
                         "if False:", previous=previous)
        self.task["stop"] = dict(kind="interrupted", reason="crashed")
        self.task.update(state="verified", completion="open")
        self.assert_gate("completion contradicts stop", "if stop and final:", "if False:")

    def test_the_deadline_gate(self):
        self.in_progress()
        self.task["delegates"] = [self.entry(deadline_at="2999-01-02T00:00:00Z")]
        previous = copy.deepcopy(self.task)
        self.task["delegates"][0]["deadline_at"] = "2999-01-09T00:00:00Z"
        self.assert_gate("delegate d1: deadline_at moved later",
                         'if timestamp(new["deadline_at"]) > timestamp(old["deadline_at"]):', "if False:",
                         previous=previous)

    def test_the_base_revision_gate(self):
        self.in_progress()
        self.task["base_revision"] = "a" * 40
        previous = copy.deepcopy(self.task)
        self.task["base_revision"] = "b" * 40
        self.assert_gate("base_revision changed",
                         'if "base_revision" in previous and current.get("base_revision") != previous["base_revision"]:',
                         "if False:", previous=previous)

    def test_the_decision_gates(self):
        self.in_progress()
        self.decide(self.decision(status="proposed", alternatives=[]))
        self.assert_gate("d1: a proposed decision states its driver (because)",
                         'errors.append(label + ": a proposed decision states its driver (because)")')
        self.decide(self.decision(status="proposed", because="x", alternatives=[]))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "active"
        self.assert_gate("moved from proposed to active without a history event that resolves it",
                         'elif old["status"] == "proposed" and old["id"] not in resolved:', "elif False:",
                         previous=previous)
        self.decide(self.decision(status="rejected", because="x", alternatives=[]))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["status"] = "active"
        self.assert_gate("decision d1 status cannot move from rejected to active",
                         '"deprecated": {"superseded"}, "rejected": set(), "superseded": set()}',
                         '"deprecated": {"superseded"}, "rejected": {"active"}, "superseded": set()}',
                         previous=previous)

    def test_supersedes_may_name_several_and_each_is_checked(self):
        self.decide(self.decision(id="d1", status="superseded"), self.decision(id="d2"),
                    self.decision(id="d3", supersedes=["d1", "d2"]))
        self.assert_gate("d3: superseded decision missing/still active", "else list(value)", "else list(value)[:1]")

    def test_the_relation_and_memory_gates(self):
        self.decide(self.decision(id="d1"), self.decision(id="d2", relations=[dict(type="amends", target="ghost")]))
        self.assert_gate("d2: relations targets unknown decision ghost", 'elif relation["target"] not in ids:',
                         "elif False:")
        self.decide(self.decision(cites_memory=["saved_later.md"]))
        self.task["observations"] = [dict(id="m1", kind="memory-read", text="read once", evidence_ids=[],
                                          entries=[dict(name="a.md", sha256="a" * 64)])]
        self.assert_gate("d1: cites memory entry saved_later.md that is not in the recorded memory snapshot",
                         "elif name not in known:", "elif False:")
        self.task["observations"][0].pop("entries")
        self.decide(self.decision())
        self.assert_gate("m1: a memory-read observation lists the entries it read",
                         'errors.append(label + ": a memory-read observation lists the entries it read (an empty list says it found none)")')

    def test_the_confirmation_is_not_a_status_field(self):
        self.in_progress()
        self.task["acceptance"][0]["status"] = "not-run"
        self.decide(self.decision(because="x", alternatives=[], confirmation=dict(check="no module imports it")))
        self.assertTrue(self.reports(v, "decided but unconfirmed", notes=True))
        counting_any_receipt = self.broken('if e["status"] == "passed" and supports(e, label) and same_content(e, task)]',
                                           "if True]")
        self.assertFalse(self.reports(counting_any_receipt, "decided but unconfirmed", notes=True))
        self.assertTrue(self.reports(counting_any_receipt, "decision d1: confirmed by e1", notes=True))

    def test_a_follow_up_needs_no_receipt_and_a_copy_that_demands_one_refuses_it(self):
        self.task["observations"] = [dict(id="o1", kind="follow-up", text="Why did no check catch this?",
                                          evidence_ids=[])]
        self.assertFalse(self.reports(v, "o1: a follow-up observation cites the evidence behind it"))
        demanding = self.broken('if observation["kind"] in {"ruled-out", "confirmed"} and not observation["evidence_ids"]:',
                                'if observation["kind"] in {"ruled-out", "confirmed", "follow-up"} and not observation["evidence_ids"]:')
        self.assertTrue(self.reports(demanding, "o1: a follow-up observation cites the evidence behind it"))


class MoreControls(ControlBase):
    """The remaining record gates and notes, one statement removed at a time."""

    def test_receipt_definition_path_and_the_stale_exemption(self):
        self.task["evidence"][0]["definition"] = dict(sha256="a" * 64, tool_version="v", paths=["../x"])
        self.assert_gate("e1: nonportable definition path: ../x", 'if not portable(path) or path == ".")', "if False)")
        self.in_progress()
        self.task["acceptance"][0]["status"] = "not-run"
        self.task["evidence"][0].update(status="stale", definition=dict(sha256="a" * 64, tool_version="v", paths=[]))
        text = "e1: marked stale but matches the current patch and scope"
        self.assertFalse(self.reports(v, text))
        self.assertTrue(self.reports(self.broken('and current(receipt) and "definition" not in receipt:',
                                                 "and current(receipt):"), text))

    def test_the_unit_notes_and_retry_gates(self):
        self.in_progress()
        self.unit(status="blocked")
        self.assert_gate("w1: blocked without a reason", 'if unit["status"] == "blocked" and "reason" not in unit:',
                         "if False:", notes=True)
        self.unit(retry_of="w1")
        self.assert_gate("w1: retry_of names itself", 'if unit.get("retry_of") == label:', "if False:")
        self.unit(retry_of="ghost")
        self.assert_gate("w1: retry_of names no work unit: ghost",
                         'elif "retry_of" in unit and unit["retry_of"] not in indexes["work_units"]:', "elif False:")

    def test_the_claim_gates(self):
        self.in_progress()
        self.unit(status="active", claim=dict(owner="w", state="inspected", expires_at=FUTURE))
        self.assert_gate("w1: claim inspected without saying what was inspected",
                         'if claim["state"] == "inspected" and "inspection" not in claim:', "if False:")
        self.unit(status="active", claim=dict(owner="w", state="claimed", expires_at=PAST))
        self.assert_gate("w1: lease held by w expired at", 'if claim["state"] == "claimed" and expired:', "if False:",
                         notes=True)

    def test_the_action_notes(self):
        self.in_progress()
        self.task["actions"] = [dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                                     scope_id=self.task["scope_id"], occurrence="o1", decision="pending",
                                     outcome="not-applied", evidence_ids=[], request_id="r-9")]
        self.assert_gate("open approval act-1 (local-write src/parser/a.py, request r-9)",
                         'if action["decision"] == "pending":', "if False:", notes=True)
        self.task["actions"][0].update(decision="approved", outcome="uncertain")
        self.assert_gate("uncertain steps without a cause: act-1", "if bare:\n            notes.append(\"uncertain steps",
                         "if False:\n            notes.append(\"uncertain steps", notes=True)

    def test_the_waiver_snapshot_belongs_to_a_deferred_finding(self):
        self.task["findings"] = [dict(id="f1", claim="slow", location="a:1", consequence="slow", evidence_ids=[],
                                      severity="low", severity_rationale="rare", correction="cache",
                                      adjudication="rejected", rationale="not a defect", verification_ids=[],
                                      waived_patch_id=self.task["patch_id"])]
        self.assert_gate("f1: a waiver snapshot applies only to a deferred finding",
                         'if snapshot_patch is not None and finding["adjudication"] != "deferred":', "if False:")

    def test_the_delegate_clock_gates(self):
        self.in_progress()
        self.task["delegates"] = [self.entry(start_by="2999-01-03T00:00:00Z", deadline_at="2999-01-02T00:00:00Z")]
        self.assert_gate("d1: start_by is after deadline_at",
                         'if len(times) == 2 and times["start_by"] > times["deadline_at"]:', "if False:")
        self.task["delegates"] = [self.entry(deadline_at=PAST)]
        self.assert_gate("d1: deadline_at passed", 'if entry["status"] == "running" and "deadline_at" in times and times["deadline_at"] <= now:',
                         "if False:", notes=True)
        self.task["delegates"] = [self.entry(deadline_at="2999-01-02T00:00:00Z")]
        previous = copy.deepcopy(self.task)
        del self.task["delegates"][0]["deadline_at"]
        self.assert_gate("delegate d1: deadline_at removed",
                         'errors.append("delegate " + old["id"] + ": deadline_at removed (it is fixed when the work starts)")',
                         "pass", previous=previous)

    def test_the_resolves_event_gates(self):
        self.in_progress()
        self.decide(self.decision(status="proposed", because="x", alternatives=[]))
        self.task["history"].append(event("h-x", "implemented", "implemented", self.task, resolves=["ghost"]))
        self.assert_gate("h-x: resolves names no decision: ghost", "if name not in indexes[\"decisions\"])", "if False)")
        self.assert_gate("h-x: resolves needs a reason", 'if event.get("resolves") and not event.get("reason"):',
                         "if False:")

    def test_the_proposal_gates(self):
        self.in_progress()
        self.decide(self.decision(status="proposed", because="x"))
        self.assert_gate("d1: a proposed decision gives a reason for each alternative (missing: tuple, dict)",
                         'errors.append(label + ": a proposed decision gives a reason for each alternative (missing: "\n                              + ", ".join(missing) + ")")',
                         "pass")
        self.decide(self.decision(alternative_reasons=[dict(alternative="list", reason="x"),
                                                       dict(alternative="tuple", reason="a"),
                                                       dict(alternative="tuple", reason="b")]))
        self.assert_gate("d1: alternative_reasons names an alternative that is not listed: list",
                         "for name in dict.fromkeys(reasons) if name not in item[\"alternatives\"])",
                         "for name in dict.fromkeys(reasons) if False)")
        self.assert_gate("d1: alternative_reasons repeats tuple", "if reasons.count(name) > 1)", "if False)")
        self.decide(self.decision(status="proposed", because="x", alternatives=[]))
        self.assert_gate("decision d1 is proposed: it binds nothing", 'if status == "proposed":\n            notes.append',
                         'if False:\n            notes.append', notes=True)

    def test_a_draft_may_be_edited_and_a_recorded_part_may_not(self):
        self.in_progress()
        self.decide(self.decision(status="proposed", because="x", alternatives=[]))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["choice"] = "array"
        self.assertFalse(self.reports(v, "decision d1 rewritten", previous))
        strict = self.broken('elif old["status"] == "proposed" == new["status"]:', "elif False:")
        self.assertTrue(self.reports(strict, "decision d1 rewritten", previous))
        self.decide(self.decision(because="x", alternatives=[], relations=[dict(type="amends", target="d9")],
                                  id="d2"), self.decision(id="d9"))
        previous = copy.deepcopy(self.task)
        self.task["decisions"][0]["relations"] = []
        self.assert_gate("decision d2 rewritten", "if any(item not in new.get(key, []) for item in old[key]):",
                         "if False:", previous=previous)

    def test_the_assumption_note_and_the_successor_note(self):
        self.in_progress()
        previous = copy.deepcopy(self.task)
        self.decide(self.decision(origin="assumption", because="x", alternatives=[]))
        self.assert_gate("decision d1: an assumption written as active",
                         'if item["origin"] == "assumption" and item["status"] == "active"', "if False",
                         previous=previous, notes=True)
        self.decide(self.decision(status="superseded"))
        self.assert_gate("decision d1 is superseded but no decision names it",
                         'if status == "superseded" and label not in named:', "if False:", notes=True)

    def test_the_relation_self_target_and_the_cycle_through_a_list(self):
        self.decide(self.decision(relations=[dict(type="clarifies", target="d1")]))
        self.assert_gate("d1: relations targets itself", 'if relation["target"] == label:', "if False:")
        self.decide(self.decision(id="d1", status="superseded", supersedes=["d2"]),
                    self.decision(id="d2", status="superseded", supersedes=["d1"]))
        self.assert_gate("supersession cycle", 'if cursor == item["id"]:', "if False:")

    def test_the_observation_gates(self):
        self.task["observations"] = [dict(id="o1", kind="surprise", text="odd", evidence_ids=[], entries=[])]
        self.assert_gate("o1: entries apply only to a memory-read observation", 'if "entries" in observation:',
                         "if False:")
        self.task["observations"] = [dict(id="m1", kind="memory-read", text="read once", evidence_ids=[],
                                          entries=[dict(name="a.md", sha256="a" * 64),
                                                   dict(name="a.md", sha256="b" * 64)])]
        self.assert_gate("m1: memory entry a.md is listed twice", "if names.count(name) > 1)", "if False)")
        self.decide(self.decision(cites_memory=["a.md"]))
        self.task["observations"] = []
        self.assert_gate("the citation cannot be audited", "if not snapshots:", "if False:")

    def test_the_confirmation_criterion_must_exist(self):
        self.decide(self.decision(because="x", alternatives=[],
                                  confirmation=dict(check="c", acceptance_id="ghost")))
        self.assert_gate("d1: confirmation.acceptance_id names no acceptance criterion: ghost",
                         "if wanted is not None and wanted not in criteria:", "if False:")

    def test_the_producer_notes(self):
        self.task["evidence"][0]["producer"] = dict(tool="claude-code", context_id="c", requested_model="m1",
                                                    observed_model="m2")
        self.assert_gate("e1: requested m1, observed m2", 'stamp.get("observed_model") not in', 'stamp.get("observed_model") in',
                         notes=True)
        del self.task["evidence"][0]["producer"]["observed_model"]
        self.assert_gate("observed model unknown: e1", "if unknown:", "if False:", notes=True)

    def test_the_stop_note_and_the_open_unit_tally(self):
        self.in_progress()
        self.task["stop"] = dict(kind="interrupted", reason="crashed")
        self.assert_gate("interrupted: crashed; resume from next_safe_action", "if stop:\n        notes.append",
                         "if False:\n        notes.append", notes=True)


class CliControls(Workspace):
    """The same idea for gates that live in the writers and the command line: run the scenario through the real
    core and through a copy missing one statement, and compare."""

    copies = 0

    def core(self, *patches):
        CliControls.copies += 1
        return broken_core(self.base, "cli-broken-%d" % CliControls.copies, patches) / "scripts" / "validate.py"

    def go(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)], capture_output=True, text=True,
                              timeout=60)

    def real(self):
        return ROOT / "scripts" / "validate.py"

    def unfinished(self, script, n, *extra):
        return self.go(script, "receipt", self.path(n), "--root", self.ev, "--repo", self.repo, "--id", "b1",
                       "--claim", "a1", "--type", "unit", "--operation", "node --test", "--environment", "node 24",
                       "--status", "blocked", *extra)

    def test_the_blocked_receipt_must_say_why(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(self.unfinished(self.real(), 1).returncode, 1)
        loose = self.core(("record.py", "if args.status in UNFINISHED and not reason_code and not limits:", "if False:"))
        done = self.unfinished(loose, 1)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("reason", v.read_json(self.path(2))["evidence"][-1])

    def test_a_repeated_start_returns_the_record_and_a_copy_that_overwrites_changes_it(self):
        self.assertEqual(self.init().returncode, 0)
        first = sha(self.path(1))
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(sha(self.path(1)), first)
        overwriting = self.core(("record.py", "for path, held in open_records(target, args.task_id):",
                                 "for path, held in []:"),
                                ("evidence.py", "os.link(temp, path)", "path.write_bytes(temp.read_bytes())"))
        again = self.go(overwriting, "init", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision",
                        "no-vcs", "--goal", "Add numbers", "--scope", "s1", "--author", "agent-b", "--task-mode",
                        "repair", "--allow-path", "src")
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertNotEqual(sha(self.path(1)), first, "the copy rewrote the first record, which the real core never does")

    def test_a_chain_link_catches_an_edit_a_copy_that_writes_no_link_misses(self):
        def scenario(script):
            for item in self.ev.iterdir():
                if item.is_file():
                    item.unlink()
            self.assertEqual(cli("init", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision",
                                 "no-vcs", "--goal", "Add numbers", "--scope", "s1", "--author", "agent-a",
                                 "--allow-path", "src").returncode, 0)
            for n, rid in ((1, "e1"), (2, "e2")):
                raw = self.raw(rid + ".txt", "# pass 1\n# fail 0\n")
                done = self.go(script, "receipt", self.path(n), "--root", self.ev, "--repo", self.repo, "--id", rid,
                               "--claim", "a1", "--type", "unit", "--operation", "node --test", "--environment",
                               "node 24", "--raw", raw, "--artifact", self.repo / "src/add.js", "--passed", 1,
                               "--failed", 0, "--exit", 0, "--expected-exit", 0)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            edited = v.read_json(self.path(2))
            edited["next_safe_action"] = "edited after version 3 existed"
            self.path(2).write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
            return out(self.go(script, "task", self.path(3), "--root", self.ev, "--repo", self.repo, "--scope", "s1",
                               "--revision", "no-vcs", "--chain", self.ev))["errors"]
        self.assertTrue(any("previous_sha256" in e for e in scenario(self.real())))
        unlinked = self.core(("record.py", 'record["previous_sha256"] = digest(source)', "pass"))
        self.assertFalse(any("previous_sha256" in e for e in scenario(unlinked)))
        blind = self.core(("record.py", 'if state == "broken":', "if False:"))
        self.assertFalse(any("previous_sha256" in e for e in scenario(blind)))

    def test_another_goal_under_the_same_id_is_an_error_and_a_copy_without_the_check_returns_the_record(self):
        self.assertEqual(self.init().returncode, 0)
        args = ("init", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs", "--goal",
                "Delete numbers", "--scope", "s1", "--author", "agent-a", "--allow-path", "src")
        self.assertEqual(self.go(self.real(), *args).returncode, 1)
        blind = self.core(("record.py", 'if str(held.get("goal")).strip() != args.goal.strip():', "if False:"))
        silent = self.go(blind, *args)
        self.assertEqual(silent.returncode, 0, silent.stdout)
        self.assertEqual(out(silent)["status"], "existing-open")

    def test_a_hand_copied_version_is_unlinked_and_a_copy_without_that_rule_calls_it_a_break(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(self.receipt(1, "e1", "--claim", "a1").returncode, 0)
        self.assertEqual(self.receipt(2, "e2", "--claim", "a1").returncode, 0)
        copied = v.read_json(self.path(3))
        copied["next_safe_action"] = "hand-written next version"
        self.save(4, copied)
        args = ("task", self.path(4), "--root", self.ev, "--repo", self.repo, "--scope", "s1", "--revision", "no-vcs",
                "--chain", self.ev)
        self.assertEqual(out(self.go(self.real(), *args))["errors"], [])
        strict = self.core(("record.py", 'if link is None or link == before.get("previous_sha256"):', "if link is None:"))
        self.assertTrue(any("previous_sha256" in e for e in out(self.go(strict, *args))["errors"]))

    def test_the_chain_regression_note(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--link").returncode, 0)
        write(self.repo, {"src/add.js": "module.exports=(a,b)=>a-b;\n"})
        self.assertEqual(cli("refresh", self.path(3), "--root", self.ev, "--repo", self.repo,
                             "--revision", "no-vcs").returncode, 0)
        self.assertEqual(self.receipt(4, "e2", "--claim", "a1", "--link", "--status", "failed", passed=0, failed=1,
                                      exit_code=1).returncode, 0)
        args = ("task", self.path(5), "--root", self.ev, "--repo", self.repo, "--scope", "s1", "--revision", "no-vcs",
                "--chain", self.ev)
        self.assertTrue(any(n.startswith("a1 regressed") for n in out(self.go(self.real(), *args))["notes"]))
        blind = self.core(("record.py", "if number == final_number:", "if False:"))
        self.assertFalse(any(n.startswith("a1 regressed") for n in out(self.go(blind, *args))["notes"]))

    def test_the_single_link_check_under_previous(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(self.receipt(1, "e1", "--claim", "a1").returncode, 0)
        self.assertEqual(self.receipt(2, "e2", "--claim", "a1").returncode, 0)
        edited = v.read_json(self.path(2))
        edited["next_safe_action"] = "edited later"
        self.path(2).write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
        args = ("task", self.path(3), "--root", self.ev, "--repo", self.repo, "--scope", "s1", "--revision", "no-vcs",
                "--previous", self.path(2))
        self.assertTrue(any("previous_sha256" in e for e in out(self.go(self.real(), *args))["errors"]))
        blind = self.core(("record.py", 'if isinstance(before, dict) and link_state(task, before, args.previous) == "broken":',
                           "if False:"))
        self.assertFalse(any("previous_sha256" in e for e in out(self.go(blind, *args))["errors"]))

    def definition_chain(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        done = self.receipt(2, "e1", "--claim", "a1", "--link", "--tool-version", "node 24.1",
                            "--definition-path", "test/add.test.js")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        write(self.repo, {"test/add.test.js": "// asserts nothing now\n"})

    def test_a_changed_definition_is_reported_and_a_copy_that_ignores_it_is_silent(self):
        self.definition_chain()
        args = ("task", self.path(3), "--root", self.ev, "--repo", self.repo, "--scope", "s1", "--revision", "no-vcs")
        self.assertTrue(any("check definition changed" in e for e in out(self.go(self.real(), *args))["errors"]))
        blind = self.core(("record.py", 'return None if now == stored["sha256"] else "stored " + short(stored["sha256"]) + ", now " + short(now)',
                           "return None"))
        self.assertFalse(any("check definition changed" in e for e in out(self.go(blind, *args))["errors"]))

    def test_refresh_stales_the_receipt_and_a_copy_that_ignores_the_definition_does_not(self):
        self.definition_chain()
        done = self.go(self.real(), "refresh", self.path(3), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(v.read_json(self.path(4))["evidence"][-1]["status"], "stale")
        self.path(4).unlink()
        blind = self.core(("record.py", "or definition_drift(receipt, args.repo))", "or False)"))
        done = self.go(blind, "refresh", self.path(3), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(v.read_json(self.path(4))["evidence"][-1]["status"], "passed")

    def test_the_exclusion_precheck(self):
        self.assertEqual(self.init().returncode, 0)
        args = ("refresh", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs", "--exclude",
                "src/util.js")
        self.assertEqual(self.go(self.real(), *args).returncode, 1)
        self.assertFalse(self.path(2).exists())
        loose = self.core(("record.py", "if widened and not scope_changed:", "if False:"))
        self.go(loose, *args)
        self.assertTrue(self.path(2).exists())


if __name__ == "__main__":
    unittest.main()
