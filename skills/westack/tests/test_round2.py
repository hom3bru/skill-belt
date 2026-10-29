"""Round-2 review regressions: monotone finish conditions, record write helpers,
the stored fingerprint definition, content-bound staleness, matched controls,
stale-receipt rules, mismatch reporting, review independence levels and the
lower-priority fixes. Every input is synthetic and local; nothing is executed
except the validator itself."""
import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest

import test_westack as fixtures

v = fixtures.v
ROOT = fixtures.ROOT
SCRIPT = ROOT / "scripts" / "validate.py"
HEX40 = "0123456789abcdef0123456789abcdef01234567"
OTHER40 = "f" * 40
sys.path.insert(0, str(pathlib.Path(__file__).parent))


def cli(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=60)


def out(result):
    return json.loads(result.stdout)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write(base, files):
    base = pathlib.Path(base)
    for relative, text in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return base


def event(eid, a, b, task, **extra):
    return dict(id=eid, **{"from": a, "to": b}, scope_id=task["scope_id"], patch_id=task["patch_id"], **extra)


class Records(unittest.TestCase):
    """make_task-based records checked in memory."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-round2-")
        self.root = pathlib.Path(self.temp.name)
        self.task = fixtures.make_task(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def errors(self, task=None, previous=None, context=None, notes=None):
        task = self.task if task is None else task
        context = context or {k: task[k] for k in ("revision", "scope_id", "patch_id")}
        return v.check_task(task, self.root, context, previous, **({} if notes is None else {"notes": notes}))

    def assertError(self, text, task=None, previous=None):
        errors = self.errors(task, previous)
        self.assertTrue(any(text in e for e in errors), errors)

    def in_progress(self, task=None):
        task = self.task if task is None else task
        task.update(state="implemented", completion="open", delivery="none", verification="unverified",
                    history=fixtures.history(task["patch_id"], "framed", "inspected", "authorized-work",
                                             "implemented", scope=task["scope_id"]))
        return task


class MonotoneFinishTests(Records):
    """Within an unchanged scope, nothing that gates completion may weaken."""

    def criterion(self, cid, **changes):
        result = dict(id=cid, claim="CLI path works for " + cid, required=True, requires_runtime=True,
                      requires_negative_control=True, evidence_ids=[], status="not-run")
        result.update(changes)
        return result

    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task["acceptance"].append(self.criterion("a2"))
        self.task["work_units"] = [dict(id="w1", goal="parser", depends_on=[], allowed_paths=["src/parser"], status="done"),
                                   dict(id="w2", goal="cli", depends_on=["w1"], allowed_paths=["src/parser"], status="planned")]
        self.task["reviews"] = [dict(id="rev1", author_id=self.task["author_id"], reviewer_id="reviewer-b",
                                     context_id="fresh", patch_id=self.task["patch_id"], kind="independent",
                                     status="not-run", evidence_ids=[], finding_ids=[])]
        self.task["independent_review_required"] = True
        self.task["decisions"] = [dict(id="d1", question="Shape", choice="object", alternatives=["tuple"],
                                       origin="assumption", status="active", supersedes=None)]
        self.previous = copy.deepcopy(self.task)

    def test_baseline_pair_is_valid(self):
        self.assertEqual(self.errors(previous=self.previous), [])

    def test_acceptance_cannot_be_removed(self):
        self.task["acceptance"].pop()
        self.assertError("acceptance a2 removed", previous=self.previous)

    def test_acceptance_cannot_become_optional(self):
        self.task["acceptance"][1]["required"] = False
        self.assertError("acceptance a2 cannot be weakened", previous=self.previous)

    def test_requirement_flags_cannot_be_dropped(self):
        for flag in ("requires_negative_control", "requires_runtime"):
            with self.subTest(flag=flag):
                task = copy.deepcopy(self.task)
                task["acceptance"][1][flag] = False
                self.assertError("acceptance a2 cannot be weakened", task, self.previous)

    def test_acceptance_claim_is_fixed(self):
        self.task["acceptance"][1]["claim"] = "Something easier"
        self.assertError("acceptance a2 cannot be weakened", previous=self.previous)

    def test_independent_review_requirement_cannot_be_dropped(self):
        self.task["independent_review_required"] = False
        self.assertError("independent_review_required cannot be dropped", previous=self.previous)

    def test_unfinished_work_unit_cannot_be_removed(self):
        self.task["work_units"].pop()
        self.assertError("unfinished work unit w2 removed", previous=self.previous)

    def test_finished_work_unit_may_be_removed(self):
        self.task["work_units"] = [dict(self.task["work_units"][1], depends_on=[])]
        self.assertEqual(self.errors(previous=self.previous), [])

    def test_review_cannot_be_removed(self):
        self.task["reviews"] = []
        self.assertError("review rev1 removed", previous=self.previous)

    def test_forbidden_actions_and_non_goals_cannot_shrink(self):
        self.task["authority"]["forbidden_actions"].remove("push")
        self.task["non_goals"] = []
        errors = self.errors(previous=self.previous)
        self.assertTrue(any("forbidden action push removed" in e for e in errors), errors)
        self.assertTrue(any("non-goal removed" in e for e in errors), errors)

    def test_allowed_action_removal_is_a_scope_change(self):
        self.task["authority"]["allowed_actions"].remove("local-write")
        self.assertError("removing allowed action local-write is a scope change", previous=self.previous)

    def test_allowed_action_grant_needs_a_history_event(self):
        self.task["authority"]["allowed_actions"].append("commit")
        self.assertError("allowed action commit added without a history event", previous=self.previous)
        self.task["history"].append(event("h-grant", "implemented", "implemented", self.task,
                                          reason="User approved a local commit", grants=["commit"]))
        self.assertEqual(self.errors(previous=self.previous), [])

    def test_self_loop_event_needs_a_reason(self):
        self.task["history"].append(event("h-note", "implemented", "implemented", self.task))
        self.assertError("h-note: illegal state transition", previous=self.previous)

    def test_scope_change_with_reason_may_relax(self):
        self.task["scope_id"] = "narrowed-v2"
        for item in self.task["evidence"]:
            item["status"] = "stale"
        self.task["acceptance"] = [dict(self.task["acceptance"][0], status="not-run", evidence_ids=[])]
        self.task["independent_review_required"] = False
        self.task["reviews"] = []
        self.task["work_units"] = self.task["work_units"][:1]
        relaxed = copy.deepcopy(self.task)
        self.assertError("relaxed under a scope change without a history event", relaxed, self.previous)
        self.task["history"].append(event("h-scope", "implemented", "implemented", self.task,
                                          reason="User dropped the CLI criterion and independent review"))
        self.assertEqual(self.errors(previous=self.previous), [])

    def test_decisions_follow_the_requirement_rule(self):
        cases = {"removed": lambda t: t.update(decisions=[]),
                 "rewritten": lambda t: t["decisions"][0].update(choice="tuple", origin="user")}
        for label, mutate in cases.items():
            with self.subTest(case=label):
                task = copy.deepcopy(self.task)
                mutate(task)
                self.assertError("decision d1", task, self.previous)
        moved = copy.deepcopy(self.task)
        moved["decisions"][0]["status"] = "superseded"
        self.assertEqual(self.errors(moved, self.previous), [])
        back = copy.deepcopy(self.task)
        self.assertError("decision d1 status cannot move from superseded to active", back, moved)

    def test_weakened_record_cannot_finish(self):
        # The reviewer's weaken-to-finish sequence: drop the unmet criterion, the
        # unfinished unit and the review requirement, then claim completion.
        self.task["acceptance"].pop()
        self.task["work_units"].pop()
        self.task["independent_review_required"] = False
        self.task["history"] = fixtures.history(self.task["patch_id"], "framed", "inspected", "authorized-work",
                                                "implemented", "verified")
        self.task.update(state="verified", completion="complete")
        errors = self.errors(previous=self.previous)
        for text in ("acceptance a2 removed", "unfinished work unit w2 removed",
                     "independent_review_required cannot be dropped"):
            self.assertTrue(any(text in e for e in errors), errors)


class ContentContextTests(Records):
    """Staleness follows patch and scope; a moved revision alone is information."""

    def test_revision_only_change_is_a_note_not_an_error(self):
        notes = []
        moved = {"revision": "after-commit", "scope_id": self.task["scope_id"], "patch_id": self.task["patch_id"]}
        self.assertEqual(self.errors(context=moved, notes=notes), [])
        self.assertTrue(any("revision" in n and "after-commit" in n for n in notes), notes)

    def test_receipt_from_other_revision_with_same_patch_still_counts(self):
        self.task["evidence"][0]["revision"] = "before-commit"
        self.assertEqual(self.errors(), [])

    def test_patch_change_is_still_an_error_with_values(self):
        errors = self.errors(context=dict(revision=self.task["revision"], scope_id=self.task["scope_id"],
                                          patch_id="f" * 64))
        hit = [e for e in errors if "host-observed patch_id" in e]
        self.assertTrue(hit, errors)
        self.assertIn(self.task["patch_id"][:12], hit[0])
        self.assertIn("ffffffffffff", hit[0])


class MatchedControlTests(Records):
    def setUp(self):
        super().setUp()
        write(self.root, {"good.js": "good\n", "broken.js": "broken\n"})
        e1 = self.task["evidence"][0]
        e1.update(type="unit", artifact="good.js", artifact_sha256=sha(self.root / "good.js"),
                  operation="node --test test/add.test.js", negative_control="c1")
        self.control = dict(e1, id="c1", status="failed", passed=0, failed=1, exit_code=1,
                            artifact="broken.js", artifact_sha256=sha(self.root / "broken.js"), negative_control=None)
        self.task["evidence"].append(self.control)
        self.task["acceptance"][0].update(requires_runtime=True, requires_negative_control=True)
        self.task.update(verification="runtime-tested")

    def test_matched_control_is_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_unrelated_command_is_rejected(self):
        self.control["operation"] = "node -e process.exit(1)"
        self.assertError("operation differs")

    def test_different_type_is_rejected(self):
        self.control["type"] = "integration"
        self.assertError("type differs")

    def test_different_collected_count_is_rejected(self):
        self.control.update(collected=2, executed=2, failed=2)
        self.assertError("collected count differs")

    def test_red_run_on_the_pre_fix_patch_serves_as_control(self):
        self.control.update(patch_id="e" * 64, revision="before-fix")
        self.assertEqual(self.errors(), [])

    def test_control_from_another_scope_is_rejected(self):
        self.control["scope_id"] = "other-scope"
        self.assertError("missing failed negative control")


class StaleRuleTests(Records):
    def setUp(self):
        super().setUp()
        self.in_progress()
        self.task["acceptance"][0]["status"] = "not-run"

    def test_current_receipt_cannot_be_marked_stale(self):
        self.task["evidence"][0]["status"] = "stale"
        self.assertError("e1: marked stale but matches the current patch and scope")

    def test_stale_receipt_for_an_old_patch_is_accepted(self):
        self.task["evidence"][0].update(status="stale", patch_id="e" * 64)
        self.assertEqual(self.errors(), [])

    def test_stale_receipts_must_stay_well_formed(self):
        junk = dict(self.task["evidence"][0], id="junk", status="stale", patch_id="e" * 64,
                    recorded_at="not a time", collected=5)
        self.task["evidence"].append(junk)
        errors = self.errors()
        self.assertTrue(any("junk: malformed timestamp" in e for e in errors), errors)
        self.assertTrue(any("junk: collected/executed/skipped mismatch" in e for e in errors), errors)

    def test_stale_receipt_keeps_its_files(self):
        self.task["evidence"][0].update(status="stale", patch_id="e" * 64)
        (self.root / "output.txt").unlink()
        self.assertError("e1: missing or changed raw_output")


class ReviewLevelTests(Records):
    def setUp(self):
        super().setUp()
        write(self.root, {"review.txt": "Reviewer B read the patch.\n"})
        self.task["evidence"].append(dict(self.task["evidence"][0], id="rev-e", claim_id="rev1", type="review",
                                          raw_output="review.txt", raw_sha256=sha(self.root / "review.txt"),
                                          exit_code=None, expected_exit=None, operation="read review"))
        self.review = dict(id="rev1", author_id=self.task["author_id"], reviewer_id="reviewer-b",
                           context_id="fresh", patch_id=self.task["patch_id"], kind="independent",
                           status="completed", evidence_ids=["rev-e"], finding_ids=[])
        self.task["reviews"] = [self.review]
        self.task["independent_review_required"] = True

    def test_required_review_needs_a_recorded_level(self):
        self.assertError("independence level")
        self.review["level"] = "fresh-context-same-model"
        self.assertEqual(self.errors(), [])

    def test_independent_review_cannot_be_level_self(self):
        self.review["level"] = "self"
        self.assertError("rev1: independent review recorded at level self")

    def test_self_review_cannot_claim_a_higher_level(self):
        self.review.update(kind="self", reviewer_id=self.task["author_id"], level="human")
        self.task["independent_review_required"] = False
        self.assertError("rev1: self review cannot record level human")

    def test_unknown_level_is_rejected(self):
        self.review["level"] = "senior"
        self.assertError("value outside enum")


class FinishPathTests(Records):
    def setUp(self):
        super().setUp()
        e1 = self.task["evidence"][0]
        e1.update(type="unit")
        self.task.update(mode="repair", verification="runtime-tested")
        self.task["acceptance"][0]["requires_runtime"] = True

    def test_repair_cannot_finish_from_inspected(self):
        self.assertError("build/repair needs a verified event after implemented")

    def test_repair_must_reverify_after_returning_to_implemented(self):
        self.task["history"] = fixtures.history(self.task["patch_id"], "framed", "inspected", "authorized-work",
                                                "implemented", "verified", "implemented", "partial", "delivered")
        self.assertError("build/repair needs a verified event after implemented")

    def test_repair_through_verified_is_accepted(self):
        self.task["history"] = fixtures.history(self.task["patch_id"], "framed", "inspected", "authorized-work",
                                                "implemented", "verified", "delivered")
        self.assertEqual(self.errors(), [])


class SmallFixTests(Records):
    def action(self, **changes):
        result = dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                      scope_id=self.task["scope_id"], occurrence="o1", decision="approved", outcome="uncertain",
                      evidence_ids=[])
        result.update(changes)
        return result

    def test_reconcile_flags_effects_applied_without_approval(self):
        self.assertEqual(v.reconcile(self.action(decision="pending", outcome="not-applied"), "applied"),
                         "report-unauthorized-effect")
        self.assertEqual(v.reconcile(self.action(decision="denied", outcome="denied"), "applied"),
                         "report-unauthorized-effect")
        self.assertEqual(v.reconcile(self.action(decision="denied", outcome="denied"), "not-applied"), "stop-denied")
        self.assertEqual(v.reconcile(self.action(), "applied"), "do-not-replay")

    def test_only_symlink_and_junction_reparse_tags_are_links(self):
        cloud = types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400, st_reparse_tag=0x9000001A)
        junction = types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400,
                                         st_reparse_tag=0xA0000003)
        symlink = types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400,
                                        st_reparse_tag=0xA000000C)
        self.assertFalse(v.is_link(cloud))
        self.assertTrue(v.is_link(junction))
        self.assertTrue(v.is_link(symlink))


class FrontMatterRound2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-round2-fm-")
        self.package = pathlib.Path(self.temp.name) / "westack"
        shutil.copytree(ROOT, self.package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.skill = self.package / "SKILL.md"
        self.text = self.skill.read_text(encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def with_line(self, line):
        self.skill.write_text(self.text.replace("\n---\n", "\n" + line + "\n---\n", 1), encoding="utf-8", newline="\n")
        return v.check_package(self.package)

    def test_compatibility_key_is_accepted_and_bounded(self):
        self.assertEqual(self.with_line("compatibility: Optional validator needs Python 3.10+"), [])
        errors = self.with_line("compatibility: " + "x" * 501)
        self.assertTrue(any("compatibility" in e for e in errors), errors)

    def test_leading_utf8_bom_is_accepted(self):
        self.skill.write_bytes(b"\xef\xbb\xbf" + self.text.encode("utf-8"))
        self.assertEqual(v.check_package(self.package), [])


class Workspace(unittest.TestCase):
    """CLI flows against a small repository and an evidence root outside it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-round2-ws-")
        self.base = pathlib.Path(self.temp.name)
        self.repo = write(self.base / "repo", {"src/add.js": "module.exports=(a,b)=>a+b;\n",
                                               "src/util.js": "module.exports={};\n",
                                               "test/add.test.js": "// asserts add(2,3)===5\n"})
        self.ev = self.base / "ev"
        self.ev.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def path(self, n):
        return self.ev / ("task.%04d.json" % n)

    def init(self, *extra):
        return cli("init", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                   "--goal", "Add numbers", "--scope", "s1", "--author", "agent-a", "--task-mode", "repair",
                   "--allow-path", "src", "--allow-action", "read", "--allow-action", "local-write", *extra)

    def raw(self, name, text):
        path = self.ev / "raw" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def receipt(self, n, rid, *extra, artifact=None, passed=1, failed=0, exit_code=0):
        raw = self.raw(rid + ".txt", "# pass %d\n# fail %d\n" % (passed, failed))
        return cli("receipt", self.path(n), "--root", self.ev, "--repo", self.repo, "--id", rid,
                   "--type", "unit", "--operation", "node --test test/add.test.js", "--environment", "node 24",
                   "--raw", raw, "--artifact", artifact or self.repo / "src/add.js", "--passed", passed,
                   "--failed", failed, "--exit", exit_code, "--expected-exit", 0, *extra)

    def save(self, n, record):
        self.path(n).write_text(json.dumps(record, indent=2), encoding="utf-8")

    def task(self, n, *extra):
        return cli("task", self.path(n), "--root", self.ev, "--repo", self.repo, "--scope", "s1",
                   "--revision", "no-vcs", *extra)

    def with_acceptance(self, n=2, **changes):
        record = v.read_json(self.path(n - 1))
        base = dict(id="a1", claim="add sums", required=True, requires_runtime=True,
                    requires_negative_control=False, evidence_ids=[], status="not-run")
        record["acceptance"] = [dict(base, **changes), dict(base, id="a2", claim="CLI sums")]
        self.save(n, record)
        return record


class InitFingerprintTests(Workspace):
    def test_init_records_fingerprint_definition_and_manifest(self):
        result = self.init("--observe-path", "test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(1))
        self.assertEqual(record["fingerprint"]["paths"], ["src", "test"])
        self.assertIn("node_modules", record["fingerprint"]["exclude"])
        self.assertEqual(record["fingerprint"]["baseline"], record["patch_id"])
        manifest = v.read_json(self.ev / "manifests" / (record["patch_id"] + ".json"))
        self.assertEqual(sorted(manifest["entries"]), ["src/add.js", "src/util.js", "test/add.test.js"])

    def test_default_excludes_skip_caches_and_dependencies(self):
        clean = v.fingerprint(self.repo, ["."])
        write(self.repo, {"node_modules/x/index.js": "x", ".pytest_cache/v/cache/lastfailed": "{}",
                          "src/dist/bundle.js": "b", "build/out.o": "o", ".venv/pyvenv.cfg": "c",
                          "venv/x": "x", ".mypy_cache/x": "x", ".tox/x": "x", ".next/x": "x"})
        moved = v.fingerprint(self.repo, ["."])
        self.assertEqual((moved["patch"], moved["files"]), (clean["patch"], clean["files"]))
        for name in (".pytest_cache", "node_modules", ".venv", "venv", ".mypy_cache", ".tox", "dist",
                     "build", ".next", "__pycache__", ".git"):
            self.assertIn(name, v.DEFAULT_EXCLUDE)

    def test_record_can_override_the_excludes(self):
        self.assertEqual(self.init("--no-default-excludes").returncode, 0)
        record = v.read_json(self.path(1))
        self.assertEqual(record["fingerprint"]["exclude"], [])
        write(self.repo, {"src/node_modules/x.js": "vendored and observed\n"})
        moved = self.task(1)
        self.assertEqual(moved.returncode, 1, moved.stdout)
        self.assertIn("src/node_modules/x.js", moved.stdout)

    def test_observed_paths_cover_tests_outside_the_write_paths(self):
        self.assertEqual(self.init("--observe-path", "test").returncode, 0)
        write(self.repo, {"test/add.test.js": "// weakened\n"})
        moved = self.task(1)
        self.assertEqual(moved.returncode, 1, moved.stdout)
        self.assertIn("test/add.test.js", moved.stdout)

    def test_zero_files_is_an_error(self):
        with self.assertRaises(ValueError):
            v.fingerprint(self.repo, ["srcc"])
        result = cli("init", self.path(1), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                     "--goal", "g", "--scope", "s1", "--author", "a", "--allow-path", "srcc")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("zero files", result.stdout)
        self.assertFalse(self.path(1).exists())

    def test_evidence_root_cannot_contain_an_observed_path(self):
        inner = self.repo / "src"
        result = cli("init", inner / "task.0001.json", "--root", inner, "--repo", self.repo, "--revision", "no-vcs",
                     "--goal", "g", "--scope", "s1", "--author", "a", "--allow-path", "src")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("evidence root", result.stdout)
        self.assertFalse((inner / "task.0001.json").exists())

    def test_allowed_path_must_be_observed(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["fingerprint"]["paths"] = ["test"]
        errors = v.check_task(record, self.ev)
        self.assertTrue(any("allowed path src is not inside fingerprint.paths" in e for e in errors), errors)

    def test_mismatch_lists_recorded_observed_values_and_changed_files(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        write(self.repo, {"src/add.js": "module.exports=(a,b)=>a-b;\n", "src/new.js": "x\n"})
        result = self.task(1)
        self.assertEqual(result.returncode, 1, result.stdout)
        report = out(result)
        self.assertTrue(any(record["patch_id"][:12] in e for e in report["errors"]), report)
        self.assertEqual(report["changed_files"], {"added": ["src/new.js"], "modified": ["src/add.js"], "removed": []})


class GitRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-round2-git-")
        self.base = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_subdirectory_finds_the_git_root_upward(self):
        repo = write(self.base / "mono", {".git/HEAD": HEX40 + "\n", "pkg/app/a.txt": "a\n"})
        self.assertEqual(v.git_revision(repo / "pkg/app"), HEX40)
        result = cli("fingerprint", "--repo", repo / "pkg/app")
        self.assertEqual(out(result)["revision"], HEX40)
        self.assertEqual(pathlib.Path(out(result)["git_root"]).resolve(), repo.resolve())

    def test_no_git_anywhere_is_reported_not_silent(self):
        plain = write(self.base / "plain", {"a.txt": "a\n"})
        result = out(cli("fingerprint", "--repo", plain))
        self.assertIsNone(result["revision"])
        self.assertIn("no .git", result["revision_error"])


class WriteHelperTests(Workspace):
    def test_receipt_writes_the_next_version_with_computed_hashes(self):
        self.assertEqual(self.init().returncode, 0)
        before = self.path(1).read_bytes()
        result = self.receipt(1, "e1", "--claim", "a1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path(1).read_bytes(), before)
        record = v.read_json(self.path(2))
        receipt = record["evidence"][-1]
        self.assertEqual(receipt["raw_sha256"], sha(self.ev / "raw/e1.txt"))
        self.assertEqual(receipt["artifact_sha256"], sha(self.repo / "src/add.js"))
        self.assertTrue(receipt["artifact"].startswith("snapshots/"))
        self.assertEqual((receipt["collected"], receipt["executed"], receipt["passed"], receipt["status"]),
                         (1, 1, 1, "passed"))
        self.assertEqual((receipt["patch_id"], receipt["scope_id"]), (record["patch_id"], "s1"))

    def test_receipt_never_replaces_an_existing_version(self):
        self.assertEqual(self.init().returncode, 0)
        self.path(2).write_text("{}", encoding="utf-8")
        result = self.receipt(1, "e1", "--claim", "a1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.path(2).read_text(encoding="utf-8"), "{}")

    def test_one_run_backs_several_criteria(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        result = self.receipt(2, "e1", "--claim", "a1", "--claim", "a2", "--link")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(3))
        self.assertEqual(record["evidence"][-1]["claim_ids"], ["a1", "a2"])
        self.assertEqual([(c["status"], c["evidence_ids"]) for c in record["acceptance"]],
                         [("passed", ["e1"]), ("passed", ["e1"])])
        self.assertEqual(out(self.task(3, "--previous", self.path(2)))["errors"], [])

    def test_receipt_refuses_when_the_repository_moved(self):
        self.assertEqual(self.init().returncode, 0)
        write(self.repo, {"src/add.js": "changed\n"})
        result = self.receipt(1, "e1", "--claim", "a1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("refresh", result.stdout)
        self.assertFalse(self.path(2).exists())

    def test_red_run_then_fix_then_matched_control(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance(requires_negative_control=True)
        red = self.receipt(2, "red", "--claim", "a1", passed=0, failed=1, exit_code=1)
        self.assertEqual(red.returncode, 0, red.stdout + red.stderr)
        write(self.repo, {"src/add.js": "module.exports=(a,b)=>a+b; // fixed\n"})
        self.assertEqual(cli("refresh", self.path(3), "--root", self.ev, "--repo", self.repo,
                             "--revision", "no-vcs").returncode, 0)
        green = self.receipt(4, "green", "--claim", "a1", "--claim", "a2", "--control", "red", "--link")
        self.assertEqual(green.returncode, 0, green.stdout + green.stderr)
        self.assertEqual(out(self.task(5, "--chain", self.ev))["errors"], [])

    def verified_record(self):
        self.assertEqual(self.init().returncode, 0)
        self.with_acceptance()
        self.assertEqual(self.receipt(2, "e1", "--claim", "a1", "--claim", "a2", "--link").returncode, 0)
        record = v.read_json(self.path(3))
        record["history"] = [event("h%d" % i, a, b, record) for i, (a, b) in enumerate(
            [("framed", "inspected"), ("inspected", "authorized-work"), ("authorized-work", "implemented"),
             ("implemented", "verified")], 1)]
        record.update(state="verified", verification="runtime-tested")
        self.save(4, record)
        self.assertEqual(out(self.task(4, "--previous", self.path(3)))["errors"], [])

    def test_refresh_stales_passed_receipts_and_resets_verification(self):
        self.verified_record()
        write(self.repo, {"src/add.js": "module.exports=(a,b)=>b+a;\n"})
        before = self.path(4).read_bytes()
        result = cli("refresh", self.path(4), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path(4).read_bytes(), before)
        record = v.read_json(self.path(5))
        self.assertEqual(record["evidence"][-1]["status"], "stale")
        self.assertEqual([c["status"] for c in record["acceptance"]], ["not-run", "not-run"])
        self.assertEqual((record["state"], record["verification"]), ("implemented", "unverified"))
        self.assertEqual((record["history"][-1]["from"], record["history"][-1]["to"]), ("verified", "implemented"))
        self.assertTrue(record["history"][-1]["reason"])
        self.assertEqual(out(self.task(5, "--previous", self.path(4)))["errors"], [])

    def test_refresh_after_commit_keeps_content_evidence(self):
        self.verified_record()
        result = cli("refresh", self.path(4), "--root", self.ev, "--repo", self.repo, "--revision", "commit-after")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(5))
        self.assertEqual(record["evidence"][-1]["status"], "passed")
        self.assertEqual((record["state"], record["revision"]), ("verified", "commit-after"))

    def test_refresh_records_a_granted_action(self):
        self.verified_record()
        refused = cli("refresh", self.path(4), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                      "--grant", "commit")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertFalse(self.path(5).exists())
        result = cli("refresh", self.path(4), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                     "--grant", "commit", "--reason", "User approved one local commit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(5))
        self.assertIn("commit", record["authority"]["allowed_actions"])
        self.assertEqual(record["history"][-1]["grants"], ["commit"])

    def test_refresh_scope_change_can_relax_with_a_reason(self):
        self.verified_record()
        result = cli("refresh", self.path(4), "--root", self.ev, "--repo", self.repo, "--revision", "no-vcs",
                     "--scope", "s2", "--relax", "a2", "--reason", "User dropped the CLI criterion")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.path(5))
        self.assertEqual([c["required"] for c in record["acceptance"]], [True, False])
        self.assertTrue(all(e["status"] == "stale" for e in record["evidence"]))

    def test_chain_checks_every_version_in_order(self):
        self.verified_record()
        self.assertEqual(out(self.task(4, "--chain", self.ev))["errors"], [])
        tampered = v.read_json(self.path(3))
        tampered["evidence"][-1]["coverage"] = "rewritten later"
        self.save(3, tampered)
        report = out(self.task(4, "--chain", self.ev))
        self.assertTrue(any("task.0004.json" in e and "receipt rewritten" in e for e in report["errors"]), report)
        self.path(2).unlink()
        report = out(self.task(4, "--chain", self.ev))
        self.assertTrue(any("missing version task.0002.json" in e for e in report["errors"]), report)

    def test_changed_files_outside_every_work_unit_are_reported(self):
        self.assertEqual(self.init().returncode, 0)
        record = v.read_json(self.path(1))
        record["work_units"] = [dict(id="w1", goal="fix add", depends_on=[], allowed_paths=["src/add.js"],
                                     status="active")]
        self.save(2, record)
        write(self.repo, {"src/add.js": "fixed\n", "src/util.js": "drive-by edit\n"})
        self.assertEqual(cli("refresh", self.path(2), "--root", self.ev, "--repo", self.repo,
                             "--revision", "no-vcs").returncode, 0)
        report = out(self.task(3))
        self.assertEqual(report["outside_work_units"], ["src/util.js"])


class FieldTableTests(unittest.TestCase):
    def test_contract_readme_field_table_matches_contract(self):
        import field_table
        text = (ROOT / "contracts/README.md").read_text(encoding="utf-8")
        section = re.search(r"<!-- field-table:start -->\n(.*?)<!-- field-table:end -->", text, re.S)
        self.assertIsNotNone(section, "contracts/README.md lacks the generated field table")
        self.assertEqual(section[1], field_table.render())


if __name__ == "__main__":
    unittest.main()
