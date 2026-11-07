"""P1 adoption, delegation / handoff / durable / context / memory group: the optional delegation ledger
(`delegates`, HD-17) and `waiting_on` (HD-33) in the task record, the single-writer refusal (HD-15), the
end-state words (HD-50) and the Why clause on every craft rule (CM-35). Both record fields are optional and
additive to schema 1: a record without them is still valid. Every input is synthetic and local."""
import copy
import importlib.util
import shutil
import subprocess
import sys
import threading
import unittest

import test_westack as fixtures
from test_round2 import SCRIPT, Records, Workspace, out, write

v = fixtures.v
ROOT = fixtures.ROOT
REFS = ROOT / "references"


def text(name):
    return (REFS / name).read_text(encoding="utf-8")


class DelegateLedgerTests(Records):
    def delegate(self, **changes):
        item = dict(id="d1", parent=self.task["id"], executor="host subagent", tier="mid",
                    scope="read src/parser and report what parse() returns", status="running", continuable=True)
        item.update(changes)
        return item

    def closed(self, **changes):
        return self.delegate(status="finished", outcome=dict(disposition="landed", ref="notes/parser.md"), **changes)

    def ledger(self, *items):
        self.task["delegates"] = list(items)

    def test_a_record_without_a_ledger_is_valid_and_the_field_is_optional(self):
        self.assertNotIn("delegates", self.task)
        self.assertEqual(self.errors(), [])
        self.assertNotIn("delegates", v.CONTRACT["$defs"]["task"]["required"])

    def test_a_closed_ledger_is_valid(self):
        self.ledger(self.closed(), self.delegate(id="d2", status="crashed", reason="host killed it at 40 turns",
                                                outcome=dict(disposition="discarded", reason="half-edited file, not used")))
        self.assertEqual(self.errors(), [])

    def test_closing_a_run_with_an_open_entry_is_refused_and_names_it(self):
        self.ledger(self.closed(), self.delegate(id="d2"))
        self.assertError("d2: delegate ledger entry still open")
        self.assertFalse([e for e in self.errors() if e.startswith("d1:")])

    def test_a_record_still_in_progress_may_hold_open_entries(self):
        self.in_progress()
        self.ledger(self.delegate(), self.delegate(id="d2", status="finished"))
        self.assertEqual(self.errors(), [])

    def test_a_finished_entry_with_no_outcome_is_still_open(self):
        self.ledger(self.delegate(status="finished"))
        self.assertError("d1: delegate ledger entry still open")

    def test_landed_needs_a_ref_and_discarded_needs_a_reason(self):
        self.ledger(self.delegate(status="finished", outcome=dict(disposition="landed")))
        self.assertError("d1: a landed outcome needs a ref")
        self.ledger(self.delegate(status="finished", outcome=dict(disposition="discarded")))
        self.assertError("d1: a discarded outcome needs a reason")
        self.ledger(self.delegate(status="finished", outcome=dict(disposition="discarded", reason="superseded by d2")))
        self.assertEqual(self.errors(), [])

    def test_every_end_other_than_finished_names_its_reason(self):
        for status in ("budget-exhausted", "crashed", "lost", "declined", "cancelled", "waiting-on-person"):
            with self.subTest(status=status):
                self.in_progress()
                self.ledger(self.delegate(status=status))
                self.assertError("d1: status " + status + " needs a reason")
                self.ledger(self.delegate(status=status, reason="named cause"))
                self.assertEqual(self.errors(), [])

    def test_a_running_or_waiting_entry_cannot_be_closed(self):
        for status, reason in (("running", None), ("waiting-on-person", "needs the user's pick")):
            with self.subTest(status=status):
                extra = {"reason": reason} if reason else {}
                self.ledger(self.delegate(status=status, outcome=dict(disposition="landed", ref="x"), **extra))
                self.assertError("d1: status " + status + " has not ended, so it cannot be closed")

    def test_shape_rejects_free_text_unknown_words_and_unsafe_ids(self):
        self.in_progress()
        self.task["delegates"] = ["will check the parser later"]
        self.assertError("delegates[0]: expected object")
        self.ledger(self.delegate(tier="huge"))
        self.assertError("delegates[0].tier: value outside enum")
        self.ledger(self.delegate(status="done"))
        self.assertError("delegates[0].status: value outside enum")
        self.ledger(self.delegate(outcome=dict(disposition="kept")))
        self.assertError("delegates[0].outcome.disposition: value outside enum")
        for bad in ("../escape", "a/b", "a b", "", "x" * 65, "-lead"):
            with self.subTest(id=bad):
                self.ledger(self.delegate(id=bad))
                self.assertTrue(self.errors(), bad)
        item = self.delegate()
        del item["continuable"]
        self.ledger(item)
        self.assertError("delegates[0]: missing continuable")
        self.ledger(self.delegate(model="x"))
        self.assertError("delegates[0]: unknown key model")

    def test_the_id_is_a_plain_name_so_it_can_key_a_private_worker_folder(self):
        for good in ("d1", "worker-3", "W_7", "a" * 64):
            with self.subTest(id=good):
                self.in_progress()
                self.ledger(self.delegate(id=good))
                self.assertEqual(self.errors(), [])

    def test_duplicate_ids_are_refused(self):
        self.in_progress()
        self.ledger(self.delegate(), self.delegate())
        self.assertError("duplicate IDs in delegates")

    def test_every_parent_chain_reaches_the_task(self):
        self.in_progress()
        self.ledger(self.delegate(), self.delegate(id="d2", parent="d1"))
        self.assertEqual(self.errors(), [])
        self.ledger(self.delegate(parent="ghost"))
        self.assertError("d1: parent chain does not reach the task (ghost)")
        self.ledger(self.delegate(parent="d2"), self.delegate(id="d2", parent="d1"))
        self.assertError("parent chain does not reach the task")
        self.ledger(self.delegate(parent="d1"))
        self.assertError("d1: parent chain does not reach the task (d1)")

    def test_entries_cannot_vanish_change_identity_or_rewrite_a_closed_outcome(self):
        self.in_progress()
        self.ledger(self.closed(), self.delegate(id="d2"))
        previous = copy.deepcopy(self.task)
        self.assertEqual(self.errors(previous=previous), [])
        self.task["delegates"] = previous["delegates"][:1]
        self.assertError("delegate removed: d2", previous=previous)
        self.task["delegates"] = copy.deepcopy(previous["delegates"])
        self.task["delegates"][1]["executor"] = "another model"
        self.assertError("delegate identity changed: d2", previous=previous)
        self.task["delegates"] = copy.deepcopy(previous["delegates"])
        self.task["delegates"][0]["outcome"] = dict(disposition="discarded", reason="changed my mind")
        self.assertError("delegate outcome rewritten: d1", previous=previous)
        self.task["delegates"] = copy.deepcopy(previous["delegates"])
        self.task["delegates"][1].update(status="finished", outcome=dict(disposition="landed", ref="abc123"))
        self.assertEqual(self.errors(previous=previous), [])


class WaitingOnTests(Records):
    def wait(self, **changes):
        item = dict(what="the vendor's build to post a verdict on PR 12",
                    check=dict(kind="verdict-posted", target="PR 12 checks"),
                    next_step="merge nothing; read the verdict and re-verify", expires_at="2999-01-01T00:00:00Z")
        item.update(changes)
        self.task["waiting_on"] = item
        return item

    def test_a_record_without_waiting_on_is_valid_and_the_field_is_optional(self):
        self.assertNotIn("waiting_on", self.task)
        self.assertEqual(self.errors(), [])
        self.assertNotIn("waiting_on", v.CONTRACT["$defs"]["task"]["required"])

    def test_each_check_kind_validates(self):
        self.in_progress()
        for check in (dict(kind="file-exists", target="out/result.json"),
                      dict(kind="hash-matches", target="out/result.json", sha256="a" * 64),
                      dict(kind="verdict-posted", target="PR 12 checks"),
                      dict(kind="person-confirms", target="Maria")):
            with self.subTest(kind=check["kind"]):
                self.wait(check=check)
                self.assertEqual(self.errors(), [])

    def test_free_text_does_not_pass_the_shape_check(self):
        self.in_progress()
        self.task["waiting_on"] = "will get back to it"
        self.assertError("waiting_on: expected object")
        self.wait(check="ask later")
        self.assertError("waiting_on.check: expected object")
        item = self.wait()
        del item["next_step"]
        self.assertError("waiting_on: missing next_step")
        item = self.wait()
        del item["expires_at"]
        self.assertError("waiting_on: missing expires_at")
        self.wait(check=dict(kind="sometime", target="x"))
        self.assertError("waiting_on.check.kind: value outside enum")
        self.wait(what="")
        self.assertError("waiting_on.what: empty string")
        self.wait(retry=3)
        self.assertError("waiting_on: unknown key retry")

    def test_a_hash_check_names_the_hash_and_no_other_kind_does(self):
        self.in_progress()
        self.wait(check=dict(kind="hash-matches", target="out/result.json"))
        self.assertError("waiting_on.check: hash-matches needs sha256")
        self.wait(check=dict(kind="hash-matches", target="out/result.json", sha256="XYZ"))
        self.assertError("waiting_on.check.sha256: pattern mismatch")
        self.wait(check=dict(kind="file-exists", target="out/result.json", sha256="a" * 64))
        self.assertError("waiting_on.check: sha256 applies only to hash-matches")

    def test_file_checks_stay_inside_the_repository(self):
        self.in_progress()
        for target in ("../outside.txt", "/etc/passwd", "C:" + "/Users/x", "a\\b"):
            with self.subTest(target=target):
                self.wait(check=dict(kind="file-exists", target=target))
                self.assertError("waiting_on.check.target: a file check needs a portable repository-relative path")

    def test_the_expiry_is_a_timestamp_with_a_timezone(self):
        self.in_progress()
        for bad in ("soon", "2026-10-30", "2026-10-30T10:00:00"):
            with self.subTest(expires_at=bad):
                self.wait(expires_at=bad)
                self.assertError("waiting_on.expires_at: not an ISO timestamp with a timezone")
        self.wait(expires_at="2026-10-30T10:00:00+02:00")
        self.assertEqual(self.errors(), [])

    def test_a_finished_record_cannot_still_be_waiting(self):
        self.wait()
        self.assertError("completion contradicts waiting_on: still waiting on the vendor's build")
        self.in_progress()
        self.assertEqual(self.errors(), [])

    def test_waiting_on_may_come_and_go_between_versions(self):
        self.in_progress()
        previous = copy.deepcopy(self.task)
        self.wait()
        self.assertEqual(self.errors(previous=previous), [])
        waiting = copy.deepcopy(self.task)
        del self.task["waiting_on"]
        self.assertEqual(self.errors(previous=waiting), [])


class WaitingNotesTests(Records):
    """What resume reports for a waiting record: the helper re-checks the local kinds and dispatches nothing."""

    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.task["waiting_on"] = dict(what="the export job to write out/result.json",
                                       check=dict(kind="file-exists", target="out/result.json"),
                                       next_step="read out/result.json and re-run the cheapest check",
                                       expires_at="2999-01-01T00:00:00Z")

    def notes(self, repo=True):
        return v.waiting_notes(self.task, self.repo if repo else None)

    def test_no_waiting_on_means_no_notes(self):
        del self.task["waiting_on"]
        self.assertEqual(self.notes(), [])

    def test_a_false_check_reports_waiting_and_says_to_dispatch_nothing(self):
        notes = self.notes()
        self.assertTrue(notes[0].startswith("waiting: the export job to write out/result.json"), notes)
        self.assertIn("never re-dispatch", notes[0])
        self.assertTrue(any("check is false" in n and "dispatch nothing" in n for n in notes), notes)
        self.assertFalse(any("wait is over" in n for n in notes), notes)

    def test_a_true_check_says_the_wait_is_over(self):
        write(self.repo, {"out/result.json": "{}\n"})
        notes = self.notes()
        self.assertTrue(any("check is true" in n and "wait is over" in n for n in notes), notes)
        self.assertFalse(any("check is false" in n for n in notes), notes)

    def test_a_hash_check_compares_the_bytes(self):
        write(self.repo, {"out/result.json": "{}\n"})
        good = v.digest(self.repo / "out/result.json")
        self.task["waiting_on"]["check"] = dict(kind="hash-matches", target="out/result.json", sha256=good)
        self.assertTrue(any("check is true" in n for n in self.notes()), self.notes())
        self.task["waiting_on"]["check"]["sha256"] = "0" * 64
        self.assertTrue(any("check is false" in n and "differs" in n for n in self.notes()), self.notes())

    def test_a_target_that_escapes_the_repository_is_not_followed(self):
        write(self.root, {"outside.txt": "x\n"})
        self.task["waiting_on"]["check"]["target"] = "../outside.txt"
        notes = self.notes()
        self.assertTrue(any("not a safe repository path" in n for n in notes), notes)
        self.assertFalse(any("check is true" in n for n in notes), notes)

    def test_kinds_the_helper_cannot_see_are_left_to_the_resumer(self):
        for check in (dict(kind="verdict-posted", target="PR 12 checks"), dict(kind="person-confirms", target="Maria")):
            with self.subTest(kind=check["kind"]):
                self.task["waiting_on"]["check"] = check
                notes = self.notes()
                self.assertTrue(any("does not evaluate " + check["kind"] + " checks" in n for n in notes), notes)

    def test_without_a_repository_the_local_check_is_not_evaluated(self):
        notes = self.notes(repo=False)
        self.assertTrue(any("--repo" in n and "not evaluated" in n for n in notes), notes)

    def test_an_expired_wait_goes_back_to_the_user(self):
        self.task["waiting_on"]["expires_at"] = "2020-01-01T00:00:00Z"
        notes = self.notes()
        self.assertTrue(any("expired" in n and "ask the user" in n for n in notes), notes)


class WaitingResumeCliTests(Workspace):
    """The task command is what resume runs: a waiting record reports it and exits 0 (waiting is not an error)."""

    def waiting_record(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["waiting_on"] = dict(what="the export job to write out/result.json",
                                    check=dict(kind="file-exists", target="out/result.json"),
                                    next_step="read out/result.json", expires_at="2999-01-01T00:00:00Z")
        self.save(2, record)

    def test_resume_reports_waiting_while_the_check_is_false_and_the_wait_over_once_it_is_true(self):
        self.waiting_record()
        report = out(self.task(2))
        self.assertEqual((report["status"], report["errors"]), ("passed", []), report)
        self.assertTrue(any(n.startswith("waiting:") for n in report["notes"]), report)
        self.assertTrue(any("check is false" in n for n in report["notes"]), report)
        write(self.repo, {"out/result.json": "{}\n"})
        report = out(self.task(2))
        self.assertTrue(any("wait is over" in n for n in report["notes"]), report)

    def test_a_record_that_is_not_waiting_prints_no_waiting_note(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertFalse([n for n in out(self.task(1))["notes"] if n.startswith("waiting")])


class BrokenCopyControls(Records):
    """Each new gate fires on the real validator and stays silent on a copy of the core with that one gate
    removed, so the tests above are shown to detect the mechanism rather than pass by accident."""

    copies = 0

    def broken(self, old, new):
        BrokenCopyControls.copies += 1
        core = self.root / ("broken-core-%d" % BrokenCopyControls.copies)
        for folder in ("scripts", "contracts"):
            shutil.copytree(ROOT / folder, core / folder, ignore=shutil.ignore_patterns("__pycache__"))
        source = (core / "scripts/record.py").read_bytes().decode("utf-8")
        self.assertEqual(source.count(old), 1, "the control must remove exactly one statement")
        (core / "scripts/record.py").write_bytes(source.replace(old, new).encode("utf-8"))
        spec = importlib.util.spec_from_file_location("broken_validate_%d" % BrokenCopyControls.copies,
                                                      core / "scripts/validate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def errors_of(self, module, previous=None):
        context = {k: self.task[k] for k in ("revision", "scope_id", "patch_id")}
        return module.check_task(self.task, self.root, context, previous)

    def assert_gate(self, text, old, new="pass", previous=None):
        self.assertTrue(any(text in e for e in self.errors_of(v, previous)), "the real validator must fire")
        self.assertFalse(any(text in e for e in self.errors_of(self.broken(old, new), previous)),
                         "the copy without the gate must stay silent")

    def entry(self, **changes):
        item = dict(id="d1", parent=self.task["id"], executor="host subagent", tier="mid", scope="read src/parser",
                    status="running", continuable=True)
        item.update(changes)
        return item

    def test_the_open_entry_gate(self):
        self.task["delegates"] = [self.entry()]
        self.assert_gate("d1: delegate ledger entry still open",
                         'errors.append(name + ": delegate ledger entry still open '
                         '(land it with a ref or discard it with a reason)")')

    def test_the_parent_chain_gate(self):
        self.in_progress()
        self.task["delegates"] = [self.entry(parent="ghost")]
        self.assert_gate("d1: parent chain does not reach the task",
                         'errors.append(name + ": parent chain does not reach the task (" + entry["parent"] + ")")')

    def test_the_end_state_reason_gate(self):
        self.in_progress()
        self.task["delegates"] = [self.entry(status="budget-exhausted")]
        self.assert_gate("d1: status budget-exhausted needs a reason",
                         'errors.append(name + ": status " + entry["status"] + " needs a reason")')

    def test_the_removed_entry_gate(self):
        self.in_progress()
        self.task["delegates"] = [self.entry()]
        previous = copy.deepcopy(self.task)
        self.task["delegates"] = []
        self.assert_gate("delegate removed: d1", 'errors.append("delegate removed: " + old["id"])', previous=previous)

    def test_the_still_waiting_gate(self):
        self.task["waiting_on"] = dict(what="the vendor's build", check=dict(kind="verdict-posted", target="PR 12"),
                                       next_step="read the verdict", expires_at="2999-01-01T00:00:00Z")
        self.assert_gate("completion contradicts waiting_on",
                         'errors.append("completion contradicts waiting_on: still waiting on " + waiting["what"])')

    def test_resume_reports_a_false_check_as_waiting_and_a_copy_that_skips_the_check_does_not(self):
        repo = self.root / "repo"
        repo.mkdir()
        self.task["waiting_on"] = dict(what="the export job", check=dict(kind="file-exists", target="out/result.json"),
                                       next_step="read it", expires_at="2999-01-01T00:00:00Z")
        real = v.waiting_notes(self.task, repo)
        self.assertTrue(any("check is false" in n and "dispatch nothing" in n for n in real), real)
        skipped = self.broken('holds, detail = False, target + " is not there"',
                              'holds, detail = True, target + " is not there"').waiting_notes(self.task, repo)
        self.assertFalse(any("check is false" in n for n in skipped), skipped)
        self.assertTrue(any("wait is over" in n for n in skipped), skipped)


class SingleWriterTests(Workspace):
    """HD-15: the coordinator is the record's only writer. A second process creating the same next version is
    refused, never merged or overwritten; the control is a copy of the helpers whose writer overwrites."""

    def race(self, script):
        self.assertEqual(self.init().returncode, 0)
        (self.ev / "art.txt").write_text("tested file\n", encoding="utf-8")
        codes = []

        def work(rid):
            raw = self.raw(rid + ".txt", "# pass 1\n# fail 0\n")
            done = subprocess.run(
                [sys.executable, "-B", str(script), "receipt", str(self.path(1)), "--root", str(self.ev),
                 "--repo", str(self.repo), "--revision", "no-vcs", "--id", rid, "--claim", "a1", "--type", "unit",
                 "--operation", "node --test", "--environment", "node 24", "--raw", str(raw),
                 "--artifact", str(self.ev / "art.txt"), "--passed", "1", "--failed", "0", "--exit", "0",
                 "--expected-exit", "0"], capture_output=True, text=True, timeout=60)
            codes.append(done.returncode)
        threads = [threading.Thread(target=work, args=(rid,)) for rid in ("e1", "e2")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return sorted(codes)

    def test_exactly_one_of_two_racing_writers_succeeds_and_the_other_is_refused(self):
        self.assertEqual(self.race(SCRIPT), [0, 1])
        record = v.read_json(self.path(2))
        self.assertEqual(len(record["evidence"]), 1, "the survivor holds one receipt; the other was not merged in")
        self.assertFalse(self.path(3).exists())

    def test_control_a_writer_that_overwrites_lets_both_succeed(self):
        core = self.base / "overwriting-core"
        for folder in ("scripts", "contracts"):
            shutil.copytree(ROOT / folder, core / folder, ignore=shutil.ignore_patterns("__pycache__"))
        # HD-40: the final step links the finished temporary file to its name (and fails if the name exists);
        # copying over the name instead of linking is the overwriting writer (no rename, so no Windows file lock).
        patches = {"evidence.py": ("os.link(temp, path)", "path.write_bytes(temp.read_bytes())"),
                   "record.py": ("if os.path.lexists(target):", "if False:")}
        for name, (old, new) in patches.items():
            source = (core / "scripts" / name).read_bytes().decode("utf-8")
            self.assertEqual(source.count(old), 1, name)
            (core / "scripts" / name).write_bytes(source.replace(old, new).encode("utf-8"))
        self.assertEqual(self.race(core / "scripts" / "validate.py"), [0, 0])


class EndStateWordsTests(unittest.TestCase):
    """HD-50: one set of end-state words for runs and delegates, mapped onto the evidence results rather than
    added to them."""

    def test_durable_names_every_end_state_the_ledger_allows(self):
        statuses = v.CONTRACT["$defs"]["delegate"]["properties"]["status"]["enum"]
        self.assertIn("running", statuses)
        for word in statuses:
            if word != "running":
                self.assertIn("`" + word + "`", text("durable.md"))

    def test_the_end_states_are_not_added_to_the_shared_evidence_vocabulary(self):
        vocabulary = text("evidence-vocabulary.md")
        for word in ("budget-exhausted", "crashed", "declined", "waiting-on-person"):
            self.assertNotIn(word, vocabulary)


class CraftWhyTests(unittest.TestCase):
    """CM-35: every craft rule ends with the failure or model weakness it answers; one with no reason is a
    removal candidate."""

    @staticmethod
    def rules_without_a_reason(body):
        return [line for line in body.splitlines() if line.startswith("- ") and "Why:" not in line]

    def test_every_craft_rule_names_the_failure_it_answers(self):
        self.assertEqual(self.rules_without_a_reason(text("craft.md")), [])

    def test_control_a_planted_rule_without_a_reason_is_flagged(self):
        planted = text("craft.md") + "- Wrap every call in a retry helper.\n"
        self.assertEqual(self.rules_without_a_reason(planted), ["- Wrap every call in a retry helper."])


class ContractDocsTests(unittest.TestCase):
    def test_the_field_table_lists_the_ledger_and_the_wait(self):
        readme = (ROOT / "contracts/README.md").read_text(encoding="utf-8")
        self.assertRegex(readme, r"\| task \|[^\n]*\| [^\n]*resume_check, delegates, waiting_on \|")
        self.assertRegex(readme, r"\| delegate \| id, parent, executor, tier \(small/mid/top\), scope, status \(")
        self.assertRegex(readme, r"\| waiting_on \| what, check, next_step, expires_at \|")
        self.assertIn("`delegates[]`", readme)
        self.assertIn("`waiting_on`", readme)

    def test_the_references_name_the_fields_they_rely_on(self):
        self.assertIn("`delegates`", text("delegation.md"))
        self.assertIn("`waiting_on`", text("handoff.md"))
        self.assertIn("`waiting_on`", text("durable.md"))


if __name__ == "__main__":
    unittest.main()
