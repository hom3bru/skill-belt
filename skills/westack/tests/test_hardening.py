"""0.3.0 regressions: observed repository state, snapshots, record immutability,
negative controls, optional contract fields, typed evidence, front matter, CLI
reachability and state-machine entry. All inputs are synthetic and local."""
import copy
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_westack as fixtures

v = fixtures.v
ROOT = fixtures.ROOT
SCRIPT = ROOT / "scripts" / "validate.py"
HEX40 = "0123456789abcdef0123456789abcdef01234567"
OTHER40 = "f" * 40


def cli(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=60)


def out(result):
    return json.loads(result.stdout)


def make_repo(base, files):
    base = pathlib.Path(base)
    for relative, text in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return base


def manual_fingerprint(repo, relatives):
    lines = sorted(rel + "\0" + hashlib.sha256((repo / rel).read_bytes()).hexdigest() + "\n"
                   for rel in relatives)
    return hashlib.sha256(("estack-fingerprint-v1\n" + "".join(lines)).encode("utf-8")).hexdigest()


def rebind(task, patch):
    task["patch_id"] = patch
    for group in ("evidence", "history", "reviews"):
        for item in task[group]:
            item["patch_id"] = patch


def in_progress(task):
    task.update(state="inspected", completion="open", delivery="none", history=task["history"][:1])


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-hardening-")
        self.root = pathlib.Path(self.temp.name)
        self.task = fixtures.make_task(self.root)
        self.context = {k: self.task[k] for k in ("revision", "scope_id", "patch_id")}

    def tearDown(self):
        self.temp.cleanup()

    def errors(self, task=None, previous=None):
        task = self.task if task is None else task
        context = {k: task[k] for k in ("revision", "scope_id", "patch_id")}
        return v.check_task(task, self.root, context, previous)

    def assertError(self, text, task=None, previous=None):
        errors = self.errors(task, previous)
        self.assertTrue(any(text in e for e in errors), errors)

    def save(self, task, name="task.json"):
        path = self.root / name
        path.write_text(json.dumps(task), encoding="utf-8")
        return path


class FingerprintTests(Base):
    def test_fingerprint_is_canonical_sorted_and_lowercase(self):
        repo = make_repo(self.root / "repo-a", {"src/b.txt": "b\n", "src/a/c.txt": "c\n", "other/x.txt": "x\n"})
        result = v.fingerprint(repo, ["src"])
        self.assertRegex(result["patch"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["patch"], manual_fingerprint(repo, ["src/a/c.txt", "src/b.txt"]))
        self.assertEqual(result["files"], 2)
        twin = make_repo(self.root / "repo-b", {"src/a/c.txt": "c\n", "src/b.txt": "b\n"})
        self.assertEqual(v.fingerprint(twin, ["src"])["patch"], result["patch"])
        (repo / "src/b.txt").write_bytes(b"changed\n")
        self.assertNotEqual(v.fingerprint(repo, ["src"])["patch"], result["patch"])

    def test_fingerprint_skips_git_pycache_and_inner_evidence_root(self):
        repo = make_repo(self.root / "repo", {"src/a.txt": "a\n"})
        clean = v.fingerprint(repo, ["."])["patch"]
        make_repo(repo, {".git/HEAD": "ref: refs/heads/main\n", "src/__pycache__/a.cpython-314.pyc": "junk",
                         ".westack/run/task.json": "{}"})
        self.assertEqual(v.fingerprint(repo, ["."], exclude=[repo / ".westack/run"])["patch"], clean)
        # Without the exclusion, writing evidence would move the patch it is bound to.
        self.assertNotEqual(v.fingerprint(repo, ["."])["patch"], clean)
        with self.assertRaises(ValueError):
            v.fingerprint(repo, ["."], exclude=[repo])

    def test_fingerprint_rejects_nonportable_paths(self):
        repo = make_repo(self.root / "repo", {"src/a.txt": "a\n"})
        for bad in ("../x", "C:/x", "/x", "src\\a.txt", "a//b", "src/./a.txt"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                v.fingerprint(repo, [bad])

    def test_fingerprint_marks_missing_paths(self):
        repo = make_repo(self.root / "repo", {"src/a.txt": "a\n"})
        result = v.fingerprint(repo, ["src", "tests"])
        self.assertEqual(result["missing"], ["tests"])
        make_repo(repo, {"tests/t.txt": "t\n"})
        self.assertNotEqual(v.fingerprint(repo, ["src", "tests"])["patch"], result["patch"])

    def test_fingerprint_cli_matches_function(self):
        repo = make_repo(self.root / "repo", {"src/a.txt": "a\n", ".westack/out.txt": "o\n"})
        result = cli("fingerprint", "--repo", repo, "--path", ".", "--root", repo / ".westack")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(out(result)["patch"], v.fingerprint(repo, ["src"])["patch"])
        self.assertIsNone(out(result)["revision"])
        # Observing the evidence root itself would make the binding blind to it; that is an error now.
        blind = cli("fingerprint", "--repo", repo, "--path", "src", "--path", ".westack", "--root", repo / ".westack")
        self.assertEqual(blind.returncode, 1, blind.stdout)
        self.assertIn("equals or contains fingerprint path .westack", blind.stdout)

    def bound_task(self):
        repo = make_repo(self.root / "repo", {"src/parser/parse.txt": "parse returns a string\n"})
        rebind(self.task, v.fingerprint(repo, ["src/parser"])["patch"])
        return repo

    def test_task_repo_recomputes_patch_from_disk(self):
        repo = self.bound_task()
        path = self.save(self.task)
        base = ["task", path, "--root", self.root, "--repo", repo,
                "--revision", self.task["revision"], "--scope", self.task["scope_id"]]
        ok = cli(*base)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (repo / "src/parser/parse.txt").write_bytes(b"edited\n")
        moved = cli(*base)
        self.assertEqual(moved.returncode, 1, moved.stdout)
        self.assertIn("host-observed patch_id", moved.stdout)
        (repo / "src/parser/parse.txt").write_bytes(b"parse returns a string\n")
        disagree = cli(*base, "--patch", "f" * 64)
        self.assertEqual(disagree.returncode, 1, disagree.stdout)
        self.assertIn("--patch differs from the repository fingerprint", disagree.stdout)

    def test_task_repo_reads_revision_from_git(self):
        repo = self.bound_task()
        make_repo(repo, {".git/HEAD": "ref: refs/heads/main\n", ".git/refs/heads/main": HEX40 + "\n"})
        self.task["revision"] = HEX40
        for receipt in self.task["evidence"]:
            receipt["revision"] = HEX40
        path = self.save(self.task)
        base = ["task", path, "--root", self.root, "--repo", repo, "--scope", self.task["scope_id"]]
        ok = cli(*base)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (repo / ".git/refs/heads/main").write_bytes((OTHER40 + "\n").encode())
        # Same content under a new commit: reported, not stale.
        moved = cli(*base)
        self.assertEqual(moved.returncode, 0, moved.stdout)
        self.assertTrue(any(OTHER40[:12] in n for n in out(moved)["notes"]), moved.stdout)


class GitRevisionTests(Base):
    def test_loose_ref(self):
        repo = make_repo(self.root / "r", {".git/HEAD": "ref: refs/heads/main\n", ".git/refs/heads/main": HEX40 + "\n"})
        self.assertEqual(v.git_revision(repo), HEX40)

    def test_packed_ref_with_peeled_lines(self):
        repo = make_repo(self.root / "r", {
            ".git/HEAD": "ref: refs/heads/main\n",
            ".git/packed-refs": "# pack-refs with: peeled fully-peeled sorted \n"
                                + OTHER40 + " refs/heads/dev\n" + HEX40 + " refs/heads/main\n^" + OTHER40 + "\n"})
        self.assertEqual(v.git_revision(repo), HEX40)

    def test_detached_head(self):
        repo = make_repo(self.root / "r", {".git/HEAD": HEX40 + "\n"})
        self.assertEqual(v.git_revision(repo), HEX40)

    def test_worktree_pointer_uses_common_refs(self):
        main = make_repo(self.root / "main", {
            ".git/refs/heads/feature": HEX40 + "\n",
            ".git/worktrees/wt/HEAD": "ref: refs/heads/feature\n",
            ".git/worktrees/wt/commondir": "../..\n"})
        tree = make_repo(self.root / "wt", {".git": "gitdir: " + str((main / ".git/worktrees/wt").resolve()) + "\n",
                                            "src/a.txt": "a\n"})
        self.assertEqual(v.git_revision(tree), HEX40)

    def test_no_git_is_none(self):
        self.assertIsNone(v.git_revision(make_repo(self.root / "plain", {"a.txt": "a\n"})))

    def test_unsafe_or_missing_refs_are_errors(self):
        heads = ("ref: ../../outside\n", "ref: refs/heads/../../../x\n", "ref: refs/heads/unborn\n", "garbage\n")
        for index, head in enumerate(heads):
            with self.subTest(head=head):
                repo = make_repo(self.root / ("r" + str(index)), {".git/HEAD": head})
                with self.assertRaises(ValueError):
                    v.git_revision(repo)


class SnapshotTests(Base):
    def source(self):
        return make_repo(self.root / "repo", {"src/parser/add.js": "module.exports=(a,b)=>a-b;\n"}) / "src/parser/add.js"

    def test_snapshot_copies_by_digest_and_reuses_identical(self):
        source = self.source()
        evidence = self.root / "evidence"
        evidence.mkdir()
        first = v.snapshot(source, evidence)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual((first["status"], first["path"], first["sha256"]), ("created", "snapshots/" + sha + ".js", sha))
        self.assertEqual((evidence / first["path"]).read_bytes(), source.read_bytes())
        self.assertEqual(v.snapshot(source, evidence)["status"], "reused")

    def test_snapshot_refuses_to_replace_a_mismatched_file(self):
        source = self.source()
        evidence = self.root / "evidence"
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        planted = make_repo(evidence, {"snapshots/" + sha + ".js": "tampered\n"}) / ("snapshots/" + sha + ".js")
        with self.assertRaises(ValueError):
            v.snapshot(source, evidence)
        self.assertEqual(planted.read_bytes(), b"tampered\n")

    def test_snapshot_cli_prints_relative_path_and_hash(self):
        source = self.source()
        evidence = self.root / "evidence"
        evidence.mkdir()
        result = cli("snapshot", source, "--root", evidence)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(out(result)["path"].startswith("snapshots/"))
        self.assertEqual(out(result)["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_red_receipt_survives_in_place_fix(self):
        source = self.source()
        repo = self.root / "repo"
        red_patch = v.fingerprint(repo, ["src/parser"])["patch"]
        red_snap = v.snapshot(source, self.root)
        source.write_bytes(b"module.exports=(a,b)=>a+b;\n")  # the fix, in place
        green_snap = v.snapshot(source, self.root)
        rebind(self.task, v.fingerprint(repo, ["src/parser"])["patch"])
        (self.root / "green.txt").write_bytes(b"# pass 2\n# fail 0\n")
        (self.root / "red.txt").write_bytes(b"# pass 0\n# fail 2\n")
        green = self.task["evidence"][0]
        green.update(type="unit", artifact=green_snap["path"], artifact_sha256=green_snap["sha256"],
                     raw_output="green.txt", raw_sha256=v.digest(self.root / "green.txt"),
                     collected=2, executed=2, passed=2, operation="node --test against the fixed file")
        red = dict(green, id="red-before-fix", status="failed", patch_id=red_patch,
                   artifact=red_snap["path"], artifact_sha256=red_snap["sha256"],
                   raw_output="red.txt", raw_sha256=v.digest(self.root / "red.txt"),
                   passed=0, failed=2, exit_code=1, operation="node --test before the fix")
        self.task["evidence"].append(red)
        self.task.update(mode="repair", verification="runtime-tested",
                         history=fixtures.history(self.task["patch_id"], "framed", "inspected", "authorized-work",
                                                  "implemented", "verified", "delivered"))
        self.task["acceptance"][0]["requires_runtime"] = True
        self.assertEqual(self.errors(), [])


class ImmutabilityTests(Base):
    def test_rewritten_receipt_is_rejected(self):
        previous = copy.deepcopy(self.task)
        previous["evidence"][0].update(status="failed", passed=0, failed=1, exit_code=1)
        self.assertError("receipt rewritten: e1", previous=previous)

    def test_receipt_may_only_change_to_stale(self):
        in_progress(self.task)
        self.task["acceptance"][0]["status"] = "not-run"
        previous = copy.deepcopy(self.task)
        # Only a receipt whose patch or scope no longer matches may go stale.
        self.task.update(patch_id="e" * 64)
        self.task["evidence"][0]["status"] = "stale"
        self.assertEqual(self.errors(previous=previous), [])
        self.task["evidence"][0]["coverage"] = "rewritten while going stale"
        self.assertError("receipt rewritten: e1", previous=previous)

    def test_removed_receipt_is_rejected(self):
        in_progress(self.task)
        self.task["acceptance"][0].update(status="not-run", evidence_ids=[])
        previous = copy.deepcopy(self.task)
        self.task["evidence"] = []
        self.assertError("receipt removed: e1", previous=previous)

    def finding(self, adjudication):
        return dict(id="f1", claim="CLI consumer breaks", location="cli.js:3", consequence="crash",
                    evidence_ids=["e1"], severity="high", severity_rationale="user path", correction="adapt cli",
                    adjudication=adjudication, rationale="review", verification_ids=[])

    def test_findings_cannot_be_removed_or_move_backward(self):
        in_progress(self.task)
        self.task["findings"] = [self.finding("open")]
        previous = copy.deepcopy(self.task)
        self.task["findings"] = []
        self.assertError("finding removed: f1", previous=previous)
        self.task["findings"] = [self.finding("accepted")]
        self.assertEqual(self.errors(previous=previous), [])
        previous["findings"] = [self.finding("rejected")]
        self.task["findings"] = [self.finding("open")]
        self.assertError("finding f1 adjudication cannot move from rejected to open", previous=previous)
        previous["findings"] = [self.finding("deferred")]
        self.task["findings"] = [self.finding("accepted")]
        self.assertError("cannot move from deferred to accepted", previous=previous)

    def test_requirements_cannot_be_removed_or_rewritten(self):
        requirement = dict(id="r1", text="Offline only", origin="user", status="active", supersedes=None)
        self.task["requirements"] = [requirement]
        previous = copy.deepcopy(self.task)
        self.task["requirements"] = []
        self.assertError("requirement removed: r1", previous=previous)
        self.task["requirements"] = [dict(requirement, text="Cloud allowed")]
        self.assertError("requirement rewritten: r1", previous=previous)
        self.task["requirements"] = [dict(requirement, status="parked")]
        self.assertEqual(self.errors(previous=previous), [])
        previous["requirements"] = [dict(requirement, status="superseded")]
        self.task["requirements"] = [dict(requirement, status="active")]
        self.assertError("requirement r1 status cannot move from superseded to active", previous=previous)


class NegativeControlTests(Base):
    def receipt(self, rid, artifact, control):
        (self.root / artifact).write_bytes(("source for " + rid + "\n").encode())
        base = self.task["evidence"][0]
        return dict(base, id=rid, type="unit", artifact=artifact, artifact_sha256=v.digest(self.root / artifact),
                    negative_control=control)

    def control(self, cid, artifact):
        (self.root / artifact).write_bytes(("broken copy " + cid + "\n").encode())
        base = self.task["evidence"][0]
        return dict(base, id=cid, type="unit", status="failed", artifact=artifact,
                    artifact_sha256=v.digest(self.root / artifact), passed=0, failed=1, exit_code=1,
                    negative_control=None)

    def setUp(self):
        super().setUp()
        self.task["evidence"] = [self.receipt("e1", "good-1.txt", "c1"), self.control("c1", "broken-1.txt")]
        self.task["acceptance"][0].update(requires_runtime=True, requires_negative_control=True)
        self.task.update(verification="runtime-tested")

    def test_distinct_broken_copy_is_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_control_on_the_same_artifact_is_rejected(self):
        control = self.task["evidence"][1]
        control.update(artifact="good-1.txt", artifact_sha256=self.task["evidence"][0]["artifact_sha256"])
        self.assertError("negative control c1 uses the same artifact as e1")

    def test_every_passing_receipt_needs_its_own_control(self):
        self.task["evidence"].append(self.receipt("e2", "good-2.txt", None))
        self.task["acceptance"][0]["evidence_ids"] = ["e1", "e2"]
        self.assertError("missing failed negative control for current claim/context (e2)")
        self.task["evidence"][-1]["negative_control"] = "c2"
        self.task["evidence"].append(self.control("c2", "broken-2.txt"))
        self.assertEqual(self.errors(), [])


class OptionalContractTests(Base):
    def test_decisions_and_work_unit_links_validate(self):
        self.task["decisions"] = [
            dict(id="dec1", question="Storage", choice="SQLite", alternatives=["JSON file"], origin="user",
                 status="superseded", supersedes=None),
            dict(id="dec2", question="Storage", choice="JSON file", alternatives=["SQLite"], origin="user",
                 status="active", supersedes="dec1")]
        self.task["work_units"] = [dict(id="w1", goal="Adapt parser", depends_on=[], allowed_paths=["src/parser"],
                                        status="done", acceptance_ids=["a1"], rollback="Revert src/parser")]
        self.assertEqual(self.errors(), [])
        self.task["work_units"][0]["acceptance_ids"] = ["missing"]
        self.assertError("w1: unknown acceptance missing")
        self.task["work_units"][0]["acceptance_ids"] = ["a1"]
        self.task["decisions"][1]["supersedes"] = "nope"
        self.assertError("dec2: superseded decision missing/still active")

    def test_shipped_example_validates_against_its_workspace(self):
        examples = ROOT / "examples"
        record = v.read_json(examples / "task.json")
        self.assertEqual(record["patch_id"], v.fingerprint(examples / "workspace", record["authority"]["allowed_paths"])["patch"])
        result = cli("task", examples / "task.json", "--root", examples, "--repo", examples / "workspace",
                     "--revision", record["revision"], "--scope", record["scope_id"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_frozen_0_2_0_record_still_validates(self):
        folder = ROOT / "tests/fixtures/v1-0.2.0"
        record = v.read_json(folder / "task.json")
        self.assertEqual(v.shape(record, v.CONTRACT["root"]), [])
        context = {k: record[k] for k in ("revision", "scope_id", "patch_id")}
        self.assertEqual(v.check_task(record, folder, context), [])


class EvidenceTypeTests(Base):
    def test_source_receipt_may_omit_exit_codes(self):
        self.task["evidence"][0].update(exit_code=None, expected_exit=None)
        self.assertEqual(self.errors(), [])

    def test_half_null_exit_codes_are_rejected(self):
        self.task["evidence"][0].update(exit_code=0, expected_exit=None)
        self.assertError("e1: exit_code and expected_exit must both be null or both integers")

    def test_runtime_receipt_needs_exit_codes(self):
        self.task["evidence"][0].update(type="unit", exit_code=None, expected_exit=None)
        self.assertError("e1: runtime receipt needs exit_code and expected_exit")

    def test_review_receipt_records_that_the_review_ran(self):
        (self.root / "review.txt").write_bytes(b"Reviewer B read the patch; one blocking finding.\n")
        review_e = dict(self.task["evidence"][0], id="rev-e", claim_id="rev1", type="review",
                        raw_output="review.txt", raw_sha256=v.digest(self.root / "review.txt"),
                        exit_code=None, expected_exit=None, operation="independent read review")
        self.task["evidence"].append(review_e)
        self.task["findings"] = [dict(id="f1", claim="CLI breaks", location="cli.js:3", consequence="crash",
            evidence_ids=["rev-e"], severity="high", severity_rationale="user path", correction="adapt",
            adjudication="open", rationale="reviewer", verification_ids=[])]
        self.task["reviews"] = [dict(id="rev1", author_id=self.task["author_id"], reviewer_id="reviewer-b",
            context_id="fresh", patch_id=self.task["patch_id"], kind="independent", status="completed",
            evidence_ids=["rev-e"], finding_ids=["f1"])]
        in_progress(self.task)
        self.assertEqual(self.errors(), [])
        review_e.update(status="failed", passed=0, failed=1)
        self.assertError("put defects in findings")


class FrontMatterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-frontmatter-")
        self.package = pathlib.Path(self.temp.name) / "westack"
        shutil.copytree(ROOT, self.package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def tearDown(self):
        self.temp.cleanup()

    def front(self, *lines):
        text = (self.package / "SKILL.md").read_text(encoding="utf-8")
        body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
        (self.package / "SKILL.md").write_text("---\n" + "\n".join(lines) + "\n---\n" + body,
                                               encoding="utf-8", newline="\n")
        return v.check_package(self.package)

    def test_known_optional_host_keys_are_accepted(self):
        self.assertEqual(self.front("name: westack", "description: Plain description.", "license: Proprietary",
                                    "allowed-tools: Read Grep", "disable-model-invocation: false", "metadata:",
                                    "  short-description: Evidence workflow"), [])

    def test_unknown_duplicate_or_missing_keys_are_rejected(self):
        cases = {"unknown": ("name: westack", "description: Plain.", "model: anything"),
                 "duplicate": ("name: westack", "description: One.", "description: Two."),
                 "missing name": ("description: Plain.",),
                 "wrong name": ("name: other", "description: Plain."),
                 "orphan indent": ("name: westack", "description: Plain.", "  stray: value")}
        for label, lines in cases.items():
            with self.subTest(case=label):
                errors = self.front(*lines)
                self.assertTrue(any("front matter" in e for e in errors), errors)

    def test_yaml_unsafe_description_is_rejected(self):
        self.assertTrue(any("front matter" in e for e in self.front("name: westack", "description: Workflow: does things")))
        self.assertEqual(self.front("name: westack", 'description: "Workflow: does things"'), [])

    def test_shipped_description_is_specific_and_bounded(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        front = re.match(r"^---\n(.*?)\n---\n", text, re.S)[1]
        description = re.search(r"^description: (.+)$", front, re.M)[1]
        self.assertLessEqual(len(description), 450)
        for phrase in ("task record", "broken-copy", "not-run", "Not for", "PR review", "debugging", "install"):
            self.assertIn(phrase, description)
        self.assertNotIn("disable-model-invocation", front)


class ReconcileCliTests(Base):
    def action(self, **changes):
        result = dict(id="act-1", kind="local-write", target="src/parser/a.py", target_hash="a" * 64,
                      scope_id=self.task["scope_id"], occurrence="pause-1", decision="approved",
                      outcome="uncertain", evidence_ids=[])
        result.update(changes)
        return result

    def run_reconcile(self, observed, action_id="act-1"):
        return cli("reconcile", self.save(self.task), "--root", self.root, "--action", action_id, "--observed", observed)

    def test_reconcile_cli_prints_diagnostic_recommendation(self):
        in_progress(self.task)
        self.task["actions"] = [self.action()]
        for observed, expected in (("unknown", "inspect-without-replay"), ("applied", "do-not-replay"),
                                   ("not-applied", "refresh-authority-before-retry")):
            with self.subTest(observed=observed):
                result = self.run_reconcile(observed)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(out(result)["recommendation"], expected)
                self.assertIn("diagnostic", out(result)["claim"])
        self.task["actions"] = [self.action(decision="denied", outcome="denied")]
        self.assertEqual(out(self.run_reconcile("not-applied"))["recommendation"], "stop-denied")
        self.assertEqual(self.run_reconcile("unknown", "no-such-action").returncode, 1)


class StateEntryTests(Base):
    def test_empty_history_requires_framed_state(self):
        self.task["history"] = []
        self.assertError("empty history requires state framed")

    def test_history_must_start_at_framed(self):
        self.task["history"] = self.task["history"][1:]
        self.assertError("history must start at framed")

    def test_framed_record_cannot_be_complete(self):
        self.task.update(state="framed", history=[])
        self.assertError("final record needs a nonempty connected history")

    def test_fresh_framed_record_remains_valid(self):
        self.task.update(state="framed", completion="open", delivery="none", history=[])
        self.assertEqual(self.errors(), [])


class AuthorityPathTests(Base):
    def unit(self, path):
        return dict(id="w1", goal="edit", depends_on=[], allowed_paths=[path], status="done")

    def test_work_unit_paths_must_be_portable_and_inside_authority(self):
        for path, text in (("C:/Windows", "nonportable work-unit path"), ("../../outside", "nonportable work-unit path"),
                           ("/etc", "nonportable work-unit path"), ("src/other", "work-unit path outside authority")):
            with self.subTest(path=path):
                self.task["work_units"] = [self.unit(path)]
                self.assertError(text)
        self.task["work_units"] = [self.unit("src/parser/a.py")]
        self.assertEqual(self.errors(), [])

    def test_authority_paths_must_be_portable(self):
        self.task["authority"]["allowed_paths"] = ["../outside"]
        self.assertError("nonportable authority path")

    def test_kind_cannot_be_both_allowed_and_forbidden(self):
        self.task["authority"]["allowed_actions"].append("push")
        self.assertError("push is both allowed and forbidden")


class InitFlagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-init-flags-")
        self.base = pathlib.Path(self.temp.name)
        self.evidence = self.base / "evidence"
        self.evidence.mkdir()
        self.output = self.evidence / "task.json"

    def tearDown(self):
        self.temp.cleanup()

    def init(self, *extra, context=True):
        args = ["init", self.output, "--root", self.evidence, "--goal", "Add bounded import", "--scope", "import-v1",
                "--author", "fixture-author", "--allow-path", "src", *extra]
        if context:
            args += ["--revision", "authored-v1", "--patch", "a" * 64]
        return cli(*args)

    def test_forbidden_actions_and_non_goals_are_recorded(self):
        result = self.init("--forbid-action", "push", "--forbid-action", "deploy", "--non-goal", "No publication")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.output)
        self.assertEqual(record["authority"]["forbidden_actions"], ["push", "deploy"])
        self.assertEqual(record["non_goals"], ["No publication"])

    def test_overlapping_allow_and_forbid_is_rejected(self):
        result = self.init("--allow-action", "push", "--forbid-action", "push")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("both allowed and forbidden", result.stdout)
        self.assertFalse(self.output.exists())

    def test_repo_supplies_observed_patch_and_revision(self):
        repo = make_repo(self.base / "repo", {"src/a.txt": "a\n", ".git/HEAD": HEX40 + "\n"})
        result = self.init("--repo", repo, context=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = v.read_json(self.output)
        self.assertEqual(record["patch_id"], v.fingerprint(repo, ["src"])["patch"])
        self.assertEqual(record["revision"], HEX40)

    def test_repo_and_disagreeing_patch_are_rejected(self):
        repo = make_repo(self.base / "repo", {"src/a.txt": "a\n"})
        result = self.init("--repo", repo, "--revision", "no-vcs", "--patch", "a" * 64, context=False)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("differs from the repository fingerprint", result.stdout)
        self.assertFalse(self.output.exists())


class DocsMatchCliTests(unittest.TestCase):
    EXPECTED = {"package", "init", "task", "fingerprint", "snapshot", "reconcile", "receipt", "refresh"}

    def docs(self, include_readme=True):
        files = [ROOT / "SKILL.md", ROOT / "contracts/README.md", *sorted((ROOT / "references").glob("*.md")),
                 *sorted((ROOT / "examples").glob("*.md")), *sorted((ROOT / "hosts").glob("*"))]
        if include_readme:
            files.append(ROOT / "README.md")
        return {path: path.read_text(encoding="utf-8") for path in files}

    def test_cli_and_docs_name_the_same_commands(self):
        result = cli("--help")
        commands = set(re.search(r"\{([a-z,]+)\}", result.stdout)[1].split(","))
        self.assertEqual(commands, self.EXPECTED)
        mentioned = set()
        for text in self.docs().values():
            mentioned.update(re.findall(r"validate\.py\"?\s+([a-z]+)", text))
        self.assertEqual(mentioned, self.EXPECTED)

    def test_agent_facing_docs_have_no_internal_ids(self):
        pattern = re.compile(r"\b[DE](0[1-9]|1[0-9]|20)\b|pstack|Context Hub")
        hits = [str(path.relative_to(ROOT)) + ": " + match.group(0)
                for path, text in self.docs().items() for match in pattern.finditer(text)]
        self.assertEqual(hits, [])

    def test_route_and_contract_offer_plan_and_verify(self):
        modes = v.CONTRACT["$defs"]["task"]["properties"]["mode"]["enum"]
        self.assertTrue({"plan", "verify"} <= set(modes))
        route = (ROOT / "references/route.md").read_text(encoding="utf-8")
        intents = re.search(r"Preserve explicit intent: ([^.]+)\.", route)[1]
        self.assertEqual(set(re.split(r", | or ", intents)), set(modes))


if __name__ == "__main__":
    unittest.main()
