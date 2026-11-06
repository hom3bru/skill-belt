"""Acquisition planning contracts; no network scheduling or donor-effectiveness claim."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from gate_fixtures import aa, v2_fixture

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/acquisition.py"
spec = importlib.util.spec_from_file_location("owned_acquisition", SCRIPT)
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def queued(self, locators=None, recipients=None):
        run = self.root / "run"
        record = aa.init_run(run, locators or ["https://github.com/example/Project"], recipients or ["target=generic"])
        return run, record

    @staticmethod
    def tasks(result, kind=None):
        tasks = [task for wave in result["waves"] for task in wave["tasks"]]
        return [task for task in tasks if kind is None or task["kind"] == kind]

    @staticmethod
    def files(root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_public_pinned_repo_has_primary_and_both_independent_wiki_checks(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="public", resolved_locator="https://github.com/example/Project", revision="a" * 40)
        result = acquisition.plan(record, run)
        self.assertEqual({task["provider"] for task in self.tasks(result, "check-hosted-overview")}, {"deepwiki", "codewiki"})
        self.assertEqual(len(self.tasks(result, "read-primary")), 1)
        self.assertFalse(result["current_coverage_complete"])
        self.assertEqual(result["mode"], "plan-only")

    def test_unknown_publicness_requires_confirmation_before_both_hosted_checks(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", revision="a" * 40)
        result = acquisition.plan(record, run)
        self.assertEqual(len(self.tasks(result, "confirm-public-identity")), 1)
        self.assertEqual(self.tasks(result, "check-hosted-overview"), [])
        self.assertEqual(result["conditional_next_wave"][0]["providers"], ["deepwiki", "codewiki"])
        record["sources"][0]["visibility"] = "public"
        confirmed = acquisition.plan(record, run)
        self.assertEqual(len(self.tasks(confirmed, "check-hosted-overview")), 2)

    def test_confirmed_public_gitlab_repository_checks_both_providers_by_canonical_url(self):
        canonical = "https://gitlab.com/example/Project"
        run, record = self.queued([canonical])
        record["sources"][0].update(kind="repo", visibility="public", resolved_locator=canonical, revision="a" * 40)
        result = acquisition.plan(record, run)
        checks = self.tasks(result, "check-hosted-overview")
        self.assertEqual({task["provider"] for task in checks}, {"deepwiki", "codewiki"})
        self.assertTrue(all(canonical in task["query"] for task in checks))
        self.assertEqual(self.tasks(result, "confirm-public-identity"), [])
        self.assertEqual(result["conditional_next_wave"], [])

    def test_established_public_identity_allows_background_alongside_primary_and_wikis(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="public", resolved_locator="https://github.com/example/Project", revision="a" * 40)
        result = acquisition.plan(record, run)
        background = self.tasks(result, "research-background")[0]
        self.assertEqual(background["after"], [])
        self.assertEqual(len(result["waves"]), 1)
        self.assertEqual({task["kind"] for task in result["waves"][0]["tasks"]}, {"read-primary", "check-hosted-overview", "research-background"})

    def test_unknown_or_private_context_keeps_background_after_initial_primary_read(self):
        for visibility in ("unknown", "private"):
            with self.subTest(visibility=visibility):
                case = self.root / visibility
                record = aa.init_run(case, ["https://example.test/repository"], ["target=generic"])
                record["sources"][0].update(kind="repo", visibility=visibility, revision="pin")
                result = acquisition.plan(record, case)
                background = self.tasks(result, "research-background")[0]
                primary = next(task for task in self.tasks(result) if task["kind"] in {"read-primary", "confirm-public-identity"})
                self.assertEqual(background["after"], [primary["id"]])

    def test_unknown_gitlab_visibility_still_requires_confirmation(self):
        canonical = "https://gitlab.com/example/Project"
        run, record = self.queued([canonical])
        record["sources"][0].update(kind="repo", resolved_locator=canonical, revision="a" * 40)
        result = acquisition.plan(record, run)
        self.assertEqual(self.tasks(result, "check-hosted-overview"), [])
        self.assertEqual(len(self.tasks(result, "confirm-public-identity")), 1)
        self.assertIn("public repository identity", result["conditional_next_wave"][0]["condition"])
        self.assertNotIn("GitHub", result["conditional_next_wave"][0]["condition"])

    def test_private_gitlab_identity_never_generates_hosted_queries(self):
        canonical = "https://gitlab.com/example/PrivateProject"
        run, record = self.queued([canonical])
        record["sources"][0].update(kind="repo", visibility="private", resolved_locator=canonical, revision="a" * 40)
        result = acquisition.plan(record, run)
        self.assertEqual(self.tasks(result, "check-hosted-overview"), [])
        self.assertEqual(result["conditional_next_wave"], [])
        self.assertTrue(all("query" not in task for task in self.tasks(result)))

    def test_private_repo_never_gets_hosted_jobs_or_public_queries(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="private")
        result = acquisition.plan(record, run)
        self.assertEqual(self.tasks(result, "check-hosted-overview"), [])
        self.assertEqual(self.tasks(result, "confirm-public-identity"), [])
        self.assertEqual(result["conditional_next_wave"], [])
        self.assertTrue(all("query" not in task for task in self.tasks(result)))
        self.assertEqual(len(self.tasks(result, "read-primary")), 1)

    def test_local_unknown_repo_needs_local_identity_confirmation_without_public_query(self):
        run, record = self.queued([str(self.root / "local-repo")])
        record["sources"][0]["kind"] = "repo"
        result = acquisition.plan(record, run)
        self.assertEqual(len(self.tasks(result, "confirm-public-identity")), 1)
        self.assertTrue(all("query" not in task for task in self.tasks(result)))
        self.assertEqual(result["conditional_next_wave"][0]["providers"], ["deepwiki", "codewiki"])

    def test_confirmed_same_pin_shares_acquisition_but_keeps_all_pairs_and_fragments(self):
        locators = ["https://github.com/example/Project#mechanism-a", "https://example.test/redirect#mechanism-b"]
        run, record = self.queued(locators, ["one=generic", "two=generic"])
        for source in record["sources"]:
            source.update(kind="repo", visibility="public", resolved_locator="https://github.com/example/Project", revision="a" * 40)
        result = acquisition.plan(record, run)
        self.assertEqual(len(result["shared_sources"]), 1)
        shared = result["shared_sources"][0]
        self.assertEqual(shared["source_ids"], ["s1", "s2"])
        self.assertEqual([scope["locator"] for scope in shared["scopes"]], locators)
        self.assertEqual(shared["pairs"], ["q1", "q2", "q3", "q4"])
        self.assertEqual(len(self.tasks(result, "read-primary")), 1)
        self.assertEqual(len(self.tasks(result, "check-hosted-overview")), 2)
        self.assertEqual([len(row["pairs"]) for row in result["recipient_work"]], [2, 2])

    def test_aliases_share_only_at_a_declared_canonical_identity_and_same_pin(self):
        run, record = self.queued(["https://example.test/original", "https://example.test/moved"])
        first, second = record["sources"]
        first.update(revision="pin", resolved_locator="https://example.test/canonical", aliases=[second["locator"]])
        second.update(revision="pin", resolved_locator=second["locator"])
        self.assertEqual(len(acquisition.plan(record, run)["shared_sources"]), 1)
        second["revision"] = "another-pin"
        self.assertEqual(len(acquisition.plan(record, run)["shared_sources"]), 2)

    def test_unresolved_versions_and_similar_names_do_not_merge(self):
        run, record = self.queued(["https://example.test/Project", "https://example.test/Project#copy"])
        for source in record["sources"]:
            source["resolved_locator"] = "https://example.test/Project"
        self.assertEqual(len(acquisition.plan(record, run)["shared_sources"]), 2)
        for source in record["sources"]:
            source.update(revision="same-pin", resolved_locator=source["locator"].replace("#copy", "-copy"))
        self.assertEqual(len(acquisition.plan(record, run)["shared_sources"]), 2)

    def test_conflicting_access_scopes_cannot_share_a_retrieval_group(self):
        run, record = self.queued(["https://example.test/a", "https://example.test/b"])
        for source, visibility in zip(record["sources"], ["public", "private"]):
            source.update(revision="pin", resolved_locator="https://example.test/canonical", visibility=visibility)
        self.assertEqual(len(acquisition.plan(record, run)["shared_sources"]), 2)

    def test_wave_limit_and_dependencies_keep_every_task(self):
        run, record = self.queued([f"https://example.test/source{i}" for i in range(7)])
        result = acquisition.plan(record, run, jobs=3)
        self.assertTrue(all(len(wave["tasks"]) <= 3 for wave in result["waves"]))
        tasks = self.tasks(result)
        self.assertEqual(len({task["id"] for task in tasks}), len(tasks))
        self.assertEqual({source for task in tasks for source in task["source_ids"]}, {f"s{i}" for i in range(1, 8)})
        done = set()
        for wave in result["waves"]:
            self.assertTrue(all(set(task["after"]) <= done for task in wave["tasks"]))
            done.update(task["id"] for task in wave["tasks"])

    def test_existing_unread_capture_is_inspected_without_claiming_a_read(self):
        run, record = self.queued(["https://example.test/source"])
        source = self.root / "source.txt"
        source.write_text("A supplied method for inspection.", encoding="utf-8")
        record["sources"][0].update(revision="pin", kind="docs")
        evidence = aa.capture(run, source, "s1", "pin")
        record["evidence"].append(evidence)
        result = acquisition.plan(record, run)
        task = self.tasks(result, "inspect-captures")[0]
        self.assertEqual(task["unread_captures"], [evidence["id"]])
        self.assertEqual(result["shared_sources"][0]["captures"][0]["read_scope"], "unread")
        self.assertEqual(record["evidence"][0]["read_scope"], "unread")

    def test_validated_closed_donor_shares_captures_and_separate_recipient_states_without_verdicts(self):
        run, record, intake = v2_fixture(self.root, two_recipients=True)
        result = acquisition.plan(record, run)
        self.assertEqual(self.tasks(result), [])
        self.assertEqual(len(result["shared_sources"][0]["pairs"]), 2)
        self.assertEqual([row["pairs"][0]["state"] for row in result["recipient_work"]], ["READY", "READY"])
        self.assertNotIn("decision", json.dumps(result))
        self.assertNotIn('"result"', json.dumps(result))
        self.assertIn("durable record readback pending", result["outstanding"])

    def test_plan_preserves_unknown_measurements_and_experiment_without_using_them_as_filters(self):
        run, record, intake = v2_fixture(self.root)
        item = record["items"][0]
        item["ledger"]["measurements"] = [{"id": "unknown", "status": "unknown", "metric": "runtime", "unit": "USD", "scope": "unrun", "note": "Not measured"}]
        item["decision"]["basis"]["measurements"] = ["unknown"]
        before = copy.deepcopy(record)
        result = acquisition.plan(record, run)
        self.assertEqual(record, before)
        self.assertEqual(result["recipient_work"][0]["pairs"][0]["state"], "READY")

    def test_linked_unqueued_work_and_named_work_remain_explicit_without_invented_targets(self):
        run, record = self.queued(["https://example.test/post"])
        record["sources"][0].update(kind="social-post", revision="post-pin")
        donor = self.root / "post.txt"
        donor.write_text("See https://example.test/paper and the project called BetterMethods.", encoding="utf-8")
        evidence = aa.capture(run, donor, "s1", "post-pin")
        evidence["read_scope"] = "Full supplied text"
        record["evidence"].append(evidence)
        intake = aa.load(run / "intake.json")
        node = intake["artifacts"][0]
        node["coverage"] = {"body": {"state": "read", "surface": "full-text", "evidence": [evidence["id"]], "note": "Supplied post"}}
        node["links"] = [{"url": "https://example.test/paper", "resolved": "https://example.test/paper", "source": None, "classification": "research", "evidence": [evidence["id"]], "reason": "Substantive paper"}]
        node["named_works"] = [{"name": "BetterMethods", "lookup": "not-yet-looked-up"}]
        aa.save(run / "intake.json", intake)
        result = acquisition.plan(record, run)
        self.assertEqual(result["links"][0]["parent"], "s1")
        self.assertEqual(len(result["unresolved_discoveries"]), 2)
        named = next(row for row in result["unresolved_discoveries"] if "named_work" in row)
        self.assertNotIn("url", named)
        self.assertEqual(len(self.tasks(result, "research-background")), 1)

    def test_declared_provider_success_avoids_repeating_that_check_but_not_the_other(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="public", revision="pin")
        captured = self.root / "overview.txt"
        captured.write_text("An existing overview was read.", encoding="utf-8")
        evidence = aa.capture(run, captured, "s1", "pin")
        evidence["read_scope"] = "Complete overview"
        record["evidence"].append(evidence)
        intake = aa.load(run / "intake.json")
        intake["artifacts"][0]["attempts"] = [{"method": "deepwiki", "url": "https://example.test/overview", "outcome": "content", "evidence": [evidence["id"]], "note": "Existing overview read"}]
        intake["artifacts"][0]["coverage"]["deepwiki"] = {"state": "read", "surface": "full-text", "evidence": [evidence["id"]], "note": "The existing hosted overview body was read, not just its retrieval metadata."}
        aa.save(run / "intake.json", intake)
        result = acquisition.plan(record, run)
        self.assertEqual([task["provider"] for task in self.tasks(result, "check-hosted-overview")], ["codewiki"])

    def test_failed_retrieval_remains_alternative_work_and_preserves_actual_attempt(self):
        run, record = self.queued(["https://example.test/source"])
        record["sources"][0].update(kind="docs", revision="pin")
        error = self.root / "error.txt"
        error.write_text("Forbidden", encoding="utf-8")
        evidence = aa.capture(run, error, "s1", "pin")
        evidence["read_scope"] = "Entire error response"
        record["evidence"].append(evidence)
        intake = aa.load(run / "intake.json")
        attempt = {"method": "ordinary-reader", "url": "https://example.test/source", "outcome": "error", "evidence": [evidence["id"]], "note": "Returned forbidden"}
        intake["artifacts"][0]["attempts"] = [attempt]
        aa.save(run / "intake.json", intake)
        result = acquisition.plan(record, run)
        primary = self.tasks(result, "read-primary")[0]
        self.assertEqual(primary["failed_attempts"][0]["method"], "ordinary-reader")
        self.assertEqual(primary["after"], [])
        self.assertEqual(self.tasks(result, "retrieval-followup"), [])
        self.assertFalse(result["current_coverage_complete"])

    def test_read_provider_metadata_does_not_skip_its_unread_body(self):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="public", revision="pin")
        metadata_path, body_path = self.root / "headers.json", self.root / "body.html"
        metadata_path.write_text('{"status":200,"surface":"headers"}', encoding="utf-8")
        body_path.write_text("<html><body>An existing hosted architecture overview body.</body></html>", encoding="utf-8")
        metadata = aa.capture(run, metadata_path, "s1", "pin")
        metadata["read_scope"] = "HTTP retrieval metadata only"
        body = aa.capture(run, body_path, "s1", "pin")
        body["origin"] = "https://deepwiki.com/example/Project"
        record["evidence"].extend([metadata, body])
        intake = aa.load(run / "intake.json")
        intake["artifacts"][0]["attempts"] = [{"method": "deepwiki", "url": body["origin"], "outcome": "content", "evidence": [metadata["id"]], "note": "Retrieval succeeded; provider body is not inspected."}]
        aa.save(run / "intake.json", intake)
        result = acquisition.plan(record, run)
        inspect = self.tasks(result, "inspect-hosted-overview")[0]
        self.assertEqual(inspect["provider"], "deepwiki")
        self.assertEqual(inspect["existing_captures"], [metadata["id"], body["id"]])
        self.assertEqual(inspect["unread_captures"], [body["id"]])
        self.assertEqual([task["provider"] for task in self.tasks(result, "check-hosted-overview")], ["codewiki"])
        primary = self.tasks(result, "read-primary")[0]
        self.assertNotIn(body["id"], primary["existing_captures"])
        self.assertEqual(record["evidence"][-1]["read_scope"], "unread")

    def failed_provider(self, exhausted):
        run, record = self.queued()
        record["sources"][0].update(kind="repo", visibility="public", resolved_locator="https://github.com/example/Project", revision="pin")
        error_path = self.root / "provider-error.txt"
        error_path.write_text("Forbidden", encoding="utf-8")
        evidence = aa.capture(run, error_path, "s1", "pin")
        evidence.update(read_scope="Entire failure response", origin="https://deepwiki.com/example/Project")
        record["evidence"].append(evidence)
        intake = aa.load(run / "intake.json")
        node = intake["artifacts"][0]
        node["attempts"] = [{"method": method, "url": evidence["origin"], "outcome": "error", "evidence": [evidence["id"]], "note": "Captured unavailable response"}
                            for method in ("deepwiki", "browser")]
        node["retrieval"] = {"available_methods": ["deepwiki", "browser"], "exhausted": exhausted,
                             "next_step": "Reopen the public browser route if source availability changes; continue primary-source analysis meanwhile."}
        aa.save(run / "intake.json", intake)
        return run, record, evidence

    def test_failed_provider_job_retains_attempts_and_only_remaining_alternatives(self):
        run, record, evidence = self.failed_provider(False)
        result = acquisition.plan(record, run)
        provider = next(task for task in self.tasks(result, "check-hosted-overview") if task["provider"] == "deepwiki")
        self.assertEqual(provider["failed_attempts"][0]["method"], "deepwiki")
        self.assertEqual(provider["existing_captures"], [])
        self.assertIn("materially different", provider["work"])
        self.assertEqual(len(self.tasks(result, "read-primary")), 1)

    def test_exhausted_provider_attempts_do_not_start_fresh_identical_probe_or_block_primary(self):
        run, record, evidence = self.failed_provider(True)
        result = acquisition.plan(record, run)
        retained = self.tasks(result, "review-recorded-attempts")[0]
        self.assertEqual(retained["provider"], "deepwiki")
        self.assertNotIn("query", retained)
        self.assertIn("source availability changes", retained["next_steps"][0])
        self.assertEqual(retained["failed_attempts"][0]["evidence"], [evidence["id"]])
        self.assertEqual([task["provider"] for task in self.tasks(result, "check-hosted-overview")], ["codewiki"])
        primary = self.tasks(result, "read-primary")[0]
        self.assertEqual(primary["after"], [])
        self.assertIn("unavailable overview alone never blocks", retained["work"])

    def test_intake_change_during_plan_rejects_instead_of_using_unchecked_new_work(self):
        run, record = self.queued()
        original = acquisition.aa.contract_status
        def changed_after_check(*args, **kwargs):
            status = original(*args, **kwargs)
            intake = aa.load(run / "intake.json")
            intake["artifacts"][0]["background"]["note"] = "Concurrent research update"
            aa.save(run / "intake.json", intake)
            return status
        with mock.patch.object(acquisition.aa, "contract_status", changed_after_check):
            with self.assertRaisesRegex(ValueError, "intake changed while planning"):
                acquisition.plan(record, run)

    def test_non_object_record_has_actionable_failure(self):
        with self.assertRaisesRegex(ValueError, "record must be an object"):
            acquisition.plan(None, self.root)

    def test_calls_are_deterministic_and_leave_record_and_run_bytes_unchanged(self):
        run, record, intake = v2_fixture(self.root, two_recipients=True)
        before_record, before_files = copy.deepcopy(record), self.files(self.root)
        first = acquisition.plan(record, run)
        self.assertEqual(acquisition.plan(record, run), first)
        self.assertEqual(record, before_record)
        self.assertEqual(self.files(self.root), before_files)

    def test_stale_capture_or_recipient_snapshot_is_rejected(self):
        run, record, intake = v2_fixture(self.root)
        capture = run / record["evidence"][0]["path"]
        original = capture.read_bytes()
        capture.write_bytes(b"Changed capture")
        with self.assertRaisesRegex(ValueError, "byte/hash mismatch"):
            acquisition.plan(record, run)
        capture.write_bytes(original)
        (self.root / "recipient/entry.py").write_text("Changed recipient", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot is stale"):
            acquisition.plan(record, run)

    def test_invalid_jobs_or_visibility_rejects_without_mutation(self):
        run, record = self.queued()
        for invalid in (0, -1, True, 1.5):
            with self.subTest(jobs=invalid), self.assertRaisesRegex(ValueError, "positive integer"):
                acquisition.plan(record, run, invalid)
        record["sources"][0]["visibility"] = "assumed-public"
        with self.assertRaisesRegex(ValueError, "visibility"):
            acquisition.plan(record, run)

    def test_cli_emits_json_and_invalid_record_has_error_exit_without_writes(self):
        run, record = self.queued()
        before = self.files(self.root)
        valid = subprocess.run([sys.executable, "-B", str(SCRIPT), str(run / "run.json"), "--jobs", "2"], capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads(valid.stdout)["max_parallel"], 2)
        self.assertEqual(self.files(self.root), before)
        invalid = subprocess.run([sys.executable, "-B", str(SCRIPT), str(run / "run.json"), "--jobs", "0"], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("positive integer", invalid.stderr)
        self.assertEqual(self.files(self.root), before)


if __name__ == "__main__":
    unittest.main()
