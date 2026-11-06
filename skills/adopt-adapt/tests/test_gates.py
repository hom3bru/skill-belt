"""V2 contract controls: coverage truthfulness and room for unmeasured research."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from gate_fixtures import aa, discard, measured_counter, recapture_donor, v2_fixture


class GateCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.record, self.intake = v2_fixture(self.root)

    def save(self):
        aa.save(self.run / "run.json", self.record)
        aa.save(self.run / "intake.json", self.intake)

    def errors(self, complete=False):
        self.save()
        return aa.validate(self.record, self.run, complete=complete)

    def bad(self, pattern, complete=False):
        errors = self.errors(complete)
        self.assertTrue(errors, "The planted bad evidence was accepted")
        self.assertRegex(" ".join(errors).lower(), pattern)

    def seal(self, index=None):
        self.save()
        aa.record_readback(self.run / "run.json", index=index)
        self.intake = aa.load(self.run / "intake.json")


class VersionAndCompletionTests(GateCase):
    def test_new_run_requires_versioned_sidecar(self):
        other = self.root / "new"
        record = aa.init_run(other, ["https://example.test/post"], ["reviewer"])
        self.assertEqual(record["schema_version"], 3)
        intake = aa.load(other / "intake.json")
        self.assertEqual(intake["schema_version"], 1)
        self.assertEqual(intake["inputs_sha256"], aa.digest(aa.canonical(aa.load(other / "inputs.json"))))
        self.assertEqual(aa.validate(record, other), [])
        status = aa.contract_status(record, other)
        self.assertEqual(status["contract"], "v3")
        self.assertFalse(status["complete"])

    def test_deleting_sidecar_never_downgrades_v2(self):
        self.save()
        (self.run / "intake.json").unlink()
        self.assertRegex(" ".join(aa.validate(self.record, self.run)).lower(), "intake|sidecar")

    def test_wrong_sidecar_version_or_input_binding_is_rejected(self):
        for key, value in (("schema_version", 99), ("inputs_sha256", "0" * 64)):
            with self.subTest(key=key):
                original = self.intake[key]
                self.intake[key] = value
                self.bad("version|binding|input|contract")
                self.intake[key] = original

    def test_legacy_records_stay_readable_but_not_complete(self):
        self.record["schema_version"] = 1
        self.save()
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.assertEqual(aa.contract_status(self.record, self.run)["contract"], "legacy")
        self.bad("legacy|version", complete=True)
        self.assertIn("legacy", aa.render(self.record, self.run).lower())

    def test_complete_record_requires_actual_saved_readback(self):
        self.assertEqual(self.errors(), [])
        self.bad("record|readback|saved", complete=True)
        self.seal()
        self.assertEqual(aa.validate(self.record, self.run, complete=True), [])
        self.assertTrue(aa.contract_status(self.record, self.run)["complete"])

    def test_saved_record_mutation_invalidates_readback(self):
        self.seal()
        self.record["request"] += " Changed after readback."
        self.bad("record|readback|hash|saved", complete=True)

    def test_index_claim_binds_record_and_ids(self):
        self.save()
        payload = {"record_sha256": aa.digest((self.run / "run.json").read_bytes()),
                   "source_ids": [source["id"] for source in self.record["sources"]],
                   "item_ids": [item["id"] for item in self.record["items"]]}
        aa.save(self.run / "index.json", payload)
        self.seal(index="index.json")
        self.assertEqual(aa.validate(self.record, self.run, complete=True), [])
        payload["item_ids"] = []
        aa.save(self.run / "index.json", payload)
        self.assertRegex(" ".join(aa.validate(self.record, self.run, complete=True)).lower(), "index|hash|record")

    def test_status_validation_and_handoff_do_not_write(self):
        self.save()
        before = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        self.assertEqual(aa.validate(self.record, self.run), [])
        aa.contract_status(self.record, self.run)
        aa.record_status(self.record, self.run)
        aa.handoff(self.record, self.run)
        after = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        self.assertEqual(after, before)


class CoverageTests(GateCase):
    def post_with_link(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID.\nCode: https://example.test/source\n")

    def test_unregistered_post_link_stays_visible_and_prevents_completion(self):
        self.post_with_link()
        self.assertEqual(self.errors(), [])
        status = aa.contract_status(self.record, self.run)
        self.assertFalse(status["complete"])
        self.assertIn("https://example.test/source", json.dumps(status))
        self.bad("link|child|coverage|unaccounted", complete=True)

    def test_explicit_nonresearch_link_needs_parent_evidence_and_reason(self):
        self.post_with_link()
        # Isolate generic link classification from the separate social-project lookup gate.
        self.record["sources"][0]["kind"] = "docs"
        evidence = self.record["evidence"][0]["id"]
        self.intake["artifacts"][0]["links"] = [{"url": "https://example.test/source", "resolved": "https://example.test/source",
                                                "source": None, "classification": "non-research", "evidence": [evidence],
                                                "reason": "This synthetic URL is declared navigation in the control."}]
        self.seal()
        self.assertEqual(aa.validate(self.record, self.run, complete=True), [])
        self.intake["artifacts"][0]["links"][0]["reason"] = ""
        self.bad("reason|link")

    def test_registered_read_and_assessed_child_closes_the_source_family(self):
        self.post_with_link()
        self.save()
        destination = self.root / "closed-family"
        aa.extend_run(self.run / "run.json", destination, ["https://example.test/source"], "Follow the linked implementation")
        record = aa.load(destination / "run.json")
        intake = aa.load(destination / "intake.json")
        child = record["sources"][-1]
        child_text = self.root / "child-method.txt"
        child_text.write_text("A documented bounded retry uses a stable request ID.\n", encoding="utf-8")
        child.update(kind="docs", revision=aa.digest(child_text.read_bytes()))
        evidence = aa.capture(destination, child_text, child["id"], child["revision"])
        evidence["read_scope"] = "Full supplied linked-method document"
        record["evidence"].append(evidence)
        parent_evidence = record["evidence"][0]["id"]
        source_claim = copy.deepcopy(record["claims"][0])
        source_claim.update(id="child-claim", subject=child["id"], evidence=[evidence["id"]])
        record["claims"].append(source_claim)
        original = copy.deepcopy(record["items"][0])
        original.update(id=record["items"][-1]["id"], source=child["id"])
        original = self._replace_exact(original, parent_evidence, evidence["id"])
        original["decision"]["claims"] = ["child-claim", "c2"]
        record["items"][-1] = original
        intake["artifacts"][0]["links"] = [{"url": "https://example.test/source", "resolved": "https://example.test/source",
            "source": child["id"], "classification": "research", "evidence": [parent_evidence], "reason": "The supplied post links this method."}]
        child_node = copy.deepcopy(intake["artifacts"][0])
        child_node.update(id=child["id"], links=[])
        child_node["coverage"]["body"]["evidence"] = [evidence["id"]]
        intake["artifacts"][-1] = child_node
        aa.save(destination / "run.json", record)
        aa.save(destination / "intake.json", intake)
        aa.record_readback(destination / "run.json")
        self.assertEqual(aa.validate(record, destination, complete=True), [])
        self.assertTrue(aa.contract_status(record, destination)["complete"])

    @staticmethod
    def _replace_exact(value, old, new):
        if isinstance(value, dict):
            return {key: CoverageTests._replace_exact(item, old, new) for key, item in value.items()}
        if isinstance(value, list):
            return [CoverageTests._replace_exact(item, old, new) for item in value]
        return new if value == old else value

    def test_missing_selected_recipient_pair_cannot_disappear(self):
        multi = self.root / "multi"
        multi.mkdir()
        run, record, intake = v2_fixture(multi, two_recipients=True)
        record["items"].pop()
        aa.save(run / "run.json", record)
        self.assertRegex(" ".join(aa.validate(record, run)).lower(), "pair|recipient")

    def test_declared_failed_response_cannot_be_a_read_receipt(self):
        evidence = self.record["evidence"][0]["id"]
        self.intake["artifacts"][0]["attempts"] = [{"method": "web-reader", "url": "https://example.test/post",
            "outcome": "error", "evidence": [evidence], "note": "Captured failure, not usable source content."}]
        self.bad("read|error|response|content")

    def test_empty_source_capture_cannot_prove_body_read(self):
        self.record, self.intake = recapture_donor(self.run, self.record, self.intake, "   \n")
        self.bad("empty|read|body|content")

    def test_http_error_body_does_not_become_content_by_labelling_it_success(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake, '{"status":403,"message":"Forbidden"}\n')
        evidence = self.record["evidence"][0]["id"]
        self.intake["artifacts"][0]["attempts"] = [{"method": "reader", "url": "https://example.test/post",
            "outcome": "content", "evidence": [evidence], "note": "The caller labelled the response as successful."}]
        self.bad("error|response|read|content|forbidden|403")

    def test_login_shell_is_not_a_social_post_body(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake, '<html><title>Sign in</title><body>Sign in to continue</body></html>')
        self.bad("stub|login|sign.in|read|content|body")

    def test_abstract_cannot_satisfy_paper_method_results_and_limits(self):
        self.record["sources"][0]["kind"] = "paper"
        evidence = self.record["evidence"][0]["id"]
        self.intake["artifacts"][0]["coverage"] = {
            role: {"state": "read", "surface": "abstract", "evidence": [evidence], "note": "Only the abstract is supplied."}
            for role in ("method", "results", "limitations")}
        self.bad("abstract|paper|surface")

    def test_named_work_requires_a_resource_lookup(self):
        self.intake["artifacts"][0]["named_works"] = [{"name": "Unlinked project by public developer", "lookup": "missing"}]
        self.bad("lookup|named", complete=True)

    def test_one_failure_cannot_be_called_exhausted(self):
        item = self.record["items"][0]
        item.update(state="BLOCKED", transitions=["QUEUED", "RESEARCHING", "BLOCKED"], reason="Need an alternate source.")
        item.pop("decision")
        node = self.intake["artifacts"][0]
        node["coverage"]["body"].update(state="unknown", evidence=[])
        node["retrieval"] = {"available_methods": ["reader", "mirror"], "exhausted": True, "next_step": "Try the mirror."}
        node["attempts"] = [{"method": "reader", "url": "https://example.test/post", "outcome": "error",
                              "evidence": [self.record["evidence"][0]["id"]], "note": "Reader failed."}]
        self.bad("exhaust|method|retrieval")

    def test_blocked_partial_work_is_valid_and_never_becomes_discard(self):
        item = self.record["items"][0]
        item.update(state="BLOCKED", transitions=["QUEUED", "RESEARCHING", "BLOCKED"], reason="A paper body remains unavailable.")
        item.pop("decision")
        self.intake["artifacts"][0]["coverage"]["body"].update(state="unknown", evidence=[])
        self.intake["artifacts"][0]["discovery"] = "open"
        self.assertEqual(self.errors(), [])
        self.assertNotIn("decision", item)
        self.assertFalse(aa.contract_status(self.record, self.run)["complete"])
        self.bad("coverage|pair|complete|blocked|outstanding", complete=True)


class MeasurementAndExperimentTests(GateCase):
    def measured_claim(self, percent):
        row, receipt = measured_counter(self.run, self.record)
        statement = aa.measurement_statement(row)
        self.assertIn("50%", statement)
        self.record["claims"].append({
            "id": "measured-cost", "subject": "s1", "kind": "verified_outcome",
            "text": statement.replace("50%", f"{percent}%"),
            "status": "supported", "scope": "The owned counter fixture only",
            "limitations": "This is not a donor runtime or production cost observation.",
            "evidence": [receipt["id"]], "execution": receipt["id"], "level": "tested",
            "review": "The captured payload binds the owned comparison, units and arithmetic inputs.",
            "measurement_refs": [row["id"]],
        })
        return row

    def unknown(self):
        row = {"id": "u1", "status": "unknown", "metric": "runtime-cost", "unit": "USD", "scope": "Unrun proposed method",
               "note": "No cost observation exists; a small pilot could supply one."}
        self.record["items"][0]["ledger"]["measurements"] = [row]
        self.record["items"][0]["decision"]["basis"]["measurements"] = ["u1"]
        return row

    def test_unknown_measurement_does_not_block_a_narrow_pilot(self):
        self.unknown()
        decision = self.record["items"][0]["decision"]
        decision["score"].update(components=[0, 0, 0, 0], penalty=0, total=0,
                                 rationale="Whole-tool fit is poor; a narrow source-grounded experiment remains useful.")
        self.assertEqual(self.errors(), [])
        self.assertEqual(decision["result"], "ADAPT-with-prerequisite")
        self.assertEqual(decision["experiment"]["state"], "proposed")

    def test_unknown_cannot_be_silently_coerced_to_zero(self):
        self.unknown()["value"] = 0
        self.bad("unknown|numeric|value")

    def test_explicit_null_unknowns_keep_the_unmeasured_pilot_available(self):
        row = self.unknown()
        row.update(value=None, range=None, baseline=None, candidate=None, receipt=None, check=None)
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.record["items"][0]["decision"]["result"], "ADAPT-with-prerequisite")

    def test_qualitative_estimate_does_not_need_a_runtime_receipt(self):
        e = self.record["items"][0]["decision"]["basis"]["evidence"]
        self.record["items"][0]["ledger"]["measurements"] = [{"id": "estimate", "status": "estimated", "metric": "integration-burden",
            "unit": "qualitative", "scope": "The selected sender seam only", "qualitative": "Add an identity parameter to the existing sender.",
            "assumptions": "The receiver already supports stable identities.", "evidence": e}]
        self.record["items"][0]["decision"]["basis"]["measurements"] = ["estimate"]
        self.assertEqual(self.errors(), [])

    def test_estimate_range_and_unrelated_unknown_cost_can_coexist_without_false_rejection(self):
        self.unknown()
        item = self.record["items"][0]
        item["ledger"]["measurements"].append({"id": "latency-estimate", "status": "estimated", "metric": "latency",
            "unit": "ms", "scope": "Only the proposed owned comparison", "range": {"low": 10, "high": 20},
            "assumptions": "An unexecuted planning estimate, conditional on the current sender shape.",
            "evidence": [self.record["evidence"][0]["id"]]})
        refs = ["latency-estimate", "u1"]
        statement = "Estimated latency is 15 ms under the stated fixture assumptions."
        item["decision"]["basis"]["measurements"] = refs
        item["decision"]["summary"] = statement
        self.record["claims"].append({"id": "planning-estimate", "subject": "s1", "kind": "source_observation",
            "text": statement, "status": "unvalidated", "scope": "Planning only, within the explicit estimate range",
            "limitations": "The latency estimate and runtime cost remain unmeasured.", "level": "claimed",
            "evidence": [self.record["evidence"][0]["id"]], "measurement_refs": refs})
        self.assertEqual(self.errors(), [])
        self.assertEqual(item["decision"]["experiment"]["state"], "proposed")

    def test_cost_rejection_without_any_burden_basis_is_rejected(self):
        discard(self.record)
        self.bad("burden|measurement|cost")

    def test_missing_measurement_is_never_a_negative_reason(self):
        discard(self.record, reason="missing-measurements")
        self.bad("reason|measurement|basis")

    def test_original_purpose_is_never_a_negative_reason(self):
        discard(self.record, reason="purpose")
        self.bad("reason|purpose|basis")

    def test_unknown_cost_cannot_justify_cost_based_discard(self):
        self.unknown()
        discard(self.record)
        self.bad("burden|unknown|measurement")

    def test_experiment_targets_are_not_claimed_observations(self):
        self.record["claims"].append({"id": "target", "subject": "s1", "kind": "experiment", "text": "Test whether cost can be 40% lower.",
            "status": "unvalidated", "scope": "A proposed comparison only", "limitations": "Unrun; no expected gain established.",
            "evidence": [], "level": "claimed"})
        self.assertEqual(self.errors(), [])

    def test_a_promising_discard_is_a_retained_experiment_lead(self):
        decision = discard(self.record, reason="research-lead")
        decision["promising_check"] = "Run the controlled receiver comparison after confirming its contract."
        self.assertEqual(self.errors(), [])
        self.assertEqual(aa.contract_status(self.record, self.run)["retained_leads"], 1)
        self.assertIn("research lead", aa.render(self.record, self.run).lower())

    def test_every_ready_pair_keeps_a_reopening_experiment(self):
        self.record["items"][0]["decision"].pop("experiment")
        self.bad("experiment|reopen")

    def test_claimed_numeric_savings_without_a_measurement_is_rejected(self):
        self.record["claims"][0]["text"] = "The new method costs 40% less on the same workload."
        self.bad("measurement|quantif|numeric")

    def test_measured_values_are_bound_to_the_actual_execution_payload(self):
        measured_counter(self.run, self.record)
        self.assertEqual(self.errors(), [])

    def test_valid_measurement_supports_its_actual_percentage(self):
        self.measured_claim(50)
        self.assertEqual(self.errors(), [])

    def test_valid_receipt_does_not_support_wrong_percentage_in_a_claim(self):
        self.measured_claim(40)
        self.bad("percent|arithmetic|numeric|value|measurement")

    def test_valid_receipt_does_not_support_wrong_percentage_in_a_summary(self):
        row, _ = measured_counter(self.run, self.record)
        decision = self.record["items"][0]["decision"]
        decision["basis"]["measurements"] = [row["id"]]
        decision["summary"] = aa.measurement_statement(row).replace("50%", "40%")
        self.bad("percent|arithmetic|numeric|value|measurement")

    def test_canonical_measured_claim_cannot_change_direction_metric_workload_or_units(self):
        row = self.measured_claim(50)
        claim = self.record["claims"][-1]
        canonical = aa.measurement_statement(row)
        for old, new in (("decrease", "increase"), (row["metric"], "production-cost"),
                         (row["workload"], "A production workload"), (row["unit"], "USD")):
            with self.subTest(field=old):
                self.assertIn(old, canonical)
                claim["text"] = canonical.replace(old, new)
                self.bad("numeric measurement statement|metric/workload/units/direction")
        claim["text"] = canonical
        self.assertEqual(self.errors(), [])

    def test_an_eligible_receipt_does_not_license_invented_metric_values(self):
        row, _ = measured_counter(self.run, self.record)
        row["candidate"]["value"] = 0
        self.bad("payload|receipt|measurement|value")

    def test_units_workload_denominator_and_revision_match_the_payload(self):
        row, _ = measured_counter(self.run, self.record)
        original = copy.deepcopy(row)
        for key, value in (("unit", "USD"), ("workload", "A different population"), ("denominator", "per token")):
            with self.subTest(key=key):
                row.clear(); row.update(copy.deepcopy(original)); row[key] = value
                self.bad("payload|receipt|measurement|unit|workload|denominator")
        row.clear(); row.update(original); row["candidate"]["revision"] = "unrelated-revision"
        self.bad("revision|payload|receipt|measurement")

    def test_measured_numbers_are_finite_and_sample_size_is_positive(self):
        row, _ = measured_counter(self.run, self.record)
        original = copy.deepcopy(row)
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                row.clear(); row.update(copy.deepcopy(original)); row["candidate"]["value"] = value
                self.bad("finite|number|numeric|value|payload|measurement")
        row.clear(); row.update(original); row["sample_size"] = 0
        self.bad("sample|positive|payload|measurement")

    def test_static_footprint_is_computed_from_the_declared_captures(self):
        source, recipient = self.record["evidence"][:2]
        row = {"id": "static", "status": "static", "metric": "captured-bytes", "unit": "bytes",
               "scope": "These selected captures only, not the full donor or recipient",
               "baseline": {"evidence": [recipient["id"]], "value": recipient["bytes"]},
               "candidate": {"evidence": [source["id"]], "value": source["bytes"]}}
        self.record["items"][0]["ledger"]["measurements"] = [row]
        self.assertEqual(self.errors(), [])
        row["candidate"]["value"] += 1
        self.bad("static|capture|computed|measurement|value")


class QueueExtensionTests(GateCase):
    def test_extension_preserves_existing_work_and_adds_all_recipient_pairs(self):
        self.save()
        before = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        destination = self.root / "continued"
        aa.extend_run(self.run / "run.json", destination, ["https://example.test/new-paper"], "New substantive source discovered")
        extended = aa.load(destination / "run.json")
        self.assertEqual(extended["items"][0], self.record["items"][0])
        self.assertEqual(extended["sources"][0], self.record["sources"][0])
        self.assertEqual(len(extended["sources"]), 2)
        self.assertEqual(len(extended["items"]), 2)
        self.assertEqual(extended["items"][1]["state"], "QUEUED")
        self.assertEqual(extended["items"][1]["recipient"], "target")
        intake = aa.load(destination / "intake.json")
        self.assertTrue(intake["lineage"])
        self.assertEqual(intake["recording"]["state"], "pending")
        self.assertEqual(aa.validate(extended, destination), [])
        after = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_extension_cannot_overwrite_an_existing_destination(self):
        self.save()
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("unrelated work", encoding="utf-8")
        with self.assertRaisesRegex((ValueError, OSError), "exist|overwrite|destination"):
            aa.extend_run(self.run / "run.json", destination, ["new source"], "new discovery")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unrelated work")

    def test_extension_rejects_an_overlapping_destination(self):
        self.save()
        with self.assertRaisesRegex((ValueError, OSError), "overlap|inside|destination"):
            aa.extend_run(self.run / "run.json", self.run / "nested", ["new source"], "new discovery")

    def test_extension_adds_each_new_source_for_both_recipients(self):
        other = self.root / "multi"
        other.mkdir()
        run, record, intake = v2_fixture(other, two_recipients=True)
        destination = self.root / "multi-continued"
        aa.extend_run(run / "run.json", destination, ["https://example.test/new-paper"], "New linked work")
        extended = aa.load(destination / "run.json")
        new_source = extended["sources"][-1]["id"]
        self.assertEqual({item["recipient"] for item in extended["items"] if item["source"] == new_source}, {"target", "target2"})
        self.assertEqual(extended["items"][:2], record["items"])


class CoverageHardeningTests(GateCase):
    def relative_document(self, body):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID.\n" + body, kind="docs")
        self.record["sources"][0]["resolved_locator"] = "https://example.test/project/"

    def assert_unaccounted(self, urls):
        self.assertEqual(self.errors(), [])
        outstanding = aa.contract_status(self.record, self.run)["outstanding"]
        for url in urls:
            self.assertIn(f"s1: unaccounted captured link {url}", outstanding)
        self.seal()
        self.bad("unaccounted captured link", complete=True)

    def capture_parent_receipt(self, body, name="lookup.json"):
        path = self.root / name
        path.write_text(body, encoding="utf-8")
        source = self.record["sources"][0]
        evidence = aa.capture(self.run, path, source["id"], source["revision"])
        evidence["read_scope"] = "The entire owned lookup/resolution receipt"
        self.record["evidence"].append(evidence)
        return evidence["id"]

    def extend_with(self, locator):
        self.save()
        destination = self.root / "discovered-child"
        aa.extend_run(self.run / "run.json", destination, [locator], "Follow the associated resource")
        self.run = destination
        self.record = aa.load(destination / "run.json")
        self.intake = aa.load(destination / "intake.json")
        return self.record["sources"][-1]["id"]

    def shortened_link(self):
        original, resolved = "https://short.test/project", "https://github.test/owner/project"
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            f"A documented bounded retry uses a stable request ID.\nCode: {original}\n", kind="docs")
        child = self.extend_with(resolved)
        edge = {"url": original, "resolved": resolved, "source": child, "classification": "research",
                "evidence": [self.record["evidence"][0]["id"]], "reason": "Follow the captured implementation link."}
        self.intake["artifacts"][0]["links"] = [edge]
        return edge

    def test_relative_inline_markdown_link_remains_outstanding(self):
        self.relative_document("[Method details](docs/recovery.md)\n")
        self.assert_unaccounted(["https://example.test/project/docs/recovery.md"])

    def test_relative_reference_markdown_link_remains_outstanding(self):
        self.relative_document("Read the [method][method].\n\n[method]: papers/retry.html\n")
        self.assert_unaccounted(["https://example.test/project/papers/retry.html"])

    def test_relative_html_links_and_media_remain_outstanding(self):
        self.relative_document('<a href="papers/retry.html">Method</a><img src="figures/flow.png">\n')
        self.assert_unaccounted(["https://example.test/project/papers/retry.html",
                                 "https://example.test/project/figures/flow.png"])

    def test_relative_navigation_can_be_accounted_with_its_capture_and_reason(self):
        self.relative_document("[Home](../index.html)\n")
        absolute = "https://example.test/index.html"
        self.intake["artifacts"][0]["links"] = [{"url": absolute, "resolved": absolute, "source": None,
            "classification": "non-research", "evidence": [self.record["evidence"][0]["id"]],
            "reason": "The owned example explicitly identifies this as home navigation."}]
        self.seal()
        self.assertEqual(aa.validate(self.record, self.run, complete=True), [])

    def test_changed_link_identity_requires_a_captured_resolution(self):
        self.shortened_link()
        self.bad("redirect resolution|original-to-final resolution")

    def test_resolution_capture_binds_original_and_final_to_the_queued_child(self):
        edge = self.shortened_link()
        receipt = self.capture_parent_receipt(json.dumps({"original": edge["url"], "resolved": edge["resolved"]}))
        edge["resolution_evidence"] = [receipt]
        self.intake["artifacts"][0]["links"].append({"url": edge["resolved"], "resolved": edge["resolved"],
            "source": edge["source"], "classification": "research", "evidence": [receipt],
            "reason": "The captured resolution receipt identifies the same queued final resource."})
        self.assertEqual(self.errors(), [])
        status = aa.contract_status(self.record, self.run)
        self.assertFalse(status["complete"])
        self.assertEqual({row["url"] for row in status["links"]}, {edge["url"], edge["resolved"]})
        self.assertTrue(any("QUEUED" in row for row in status["outstanding"]))
        self.assertFalse(any("unaccounted captured link" in row for row in status["outstanding"]))

    def test_resolution_for_another_destination_cannot_bind_the_link(self):
        edge = self.shortened_link()
        edge["resolution_evidence"] = [self.capture_parent_receipt(json.dumps({
            "original": edge["url"], "resolved": "https://github.test/unrelated/project"}))]
        self.bad("original-to-final resolution receipt")

    def test_social_post_without_a_resource_link_requires_a_background_lookup(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID. The project is called StableRetry.\n")
        self.assertEqual(self.errors(), [])
        status = aa.contract_status(self.record, self.run)
        self.assertIn("s1: social source without resource links needs a recorded background/project lookup", status["outstanding"])
        self.seal()
        self.bad("background/project lookup", complete=True)

    def test_captured_background_lookup_preserves_its_queued_project_for_research(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID. The project is called StableRetry.\n")
        locator = "https://github.test/owned/StableRetry"
        child = self.extend_with(locator)
        receipt = self.capture_parent_receipt(json.dumps({"query": "StableRetry developer GitHub", "result": locator}))
        node = self.intake["artifacts"][0]
        node["background"] = {"status": "checked", "note": "The owned project-name and developer lookup response was read."}
        node["named_works"] = [{"name": "StableRetry", "lookup": "project-search"}]
        node["lookups"] = [{"id": "project-search", "query": "StableRetry developer GitHub", "method": "owned-search-response",
            "status": "found", "note": "The captured lookup identifies a queued project; its methods still need inspection.",
            "evidence": [receipt], "matches": [child]}]
        node["links"] = [{"url": locator, "resolved": locator, "source": child, "classification": "research",
            "evidence": [receipt], "reason": "Follow the project identified by the captured background lookup."}]
        self.assertEqual(self.errors(), [])
        status = aa.contract_status(self.record, self.run)
        self.assertFalse(status["complete"])
        self.assertFalse(any("needs a recorded background/project lookup" in row for row in status["outstanding"]))
        self.assertTrue(any("QUEUED" in row for row in status["outstanding"]))

    def test_unsuccessful_project_lookup_does_not_close_the_named_work(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID. The project is called StableRetry.\n")
        receipt = self.capture_parent_receipt(json.dumps({"query": "StableRetry developer GitHub", "results": []}))
        node = self.intake["artifacts"][0]
        node["named_works"] = [{"name": "StableRetry", "lookup": "project-search"}]
        node["lookups"] = [{"id": "project-search", "query": "StableRetry developer GitHub", "method": "owned-search-response",
            "status": "not-found", "note": "One owned search response found no project; alternate discovery remains useful.",
            "evidence": [receipt], "matches": []}]
        self.assertEqual(self.errors(), [])
        self.seal()
        self.bad("named work stableretry remains unresolved", complete=True)


class QueueLineageTests(GateCase):
    def extend(self):
        self.save()
        destination = self.root / "lineage-revision"
        aa.extend_run(self.run / "run.json", destination, ["https://example.test/new-method"], "New associated method")
        self.run = destination
        self.record = aa.load(destination / "run.json")
        self.intake = aa.load(destination / "intake.json")

    def rebind_inputs(self, inputs):
        aa.save(self.run / "inputs.json", inputs)
        self.intake["inputs_sha256"] = aa.digest(aa.canonical(inputs))

    def test_each_parent_lineage_snapshot_rejects_byte_tampering(self):
        self.extend()
        for name in ("parent_record", "parent_inputs", "parent_intake"):
            with self.subTest(snapshot=name):
                path = self.run / self.intake["lineage"][0][name]["path"]
                original = path.read_bytes()
                changed = aa.load(path)
                changed["tampered-control"] = True
                aa.save(path, changed)
                self.bad("queue lineage snapshot hash differs")
                path.write_bytes(original)
        self.assertEqual(self.errors(), [])

    def test_replacing_a_prior_pair_id_is_rejected_even_with_current_input_binding(self):
        self.extend()
        self.record["items"][0]["id"] = "replacement-pair"
        inputs = aa.load(self.run / "inputs.json")
        inputs["pairs"][0]["id"] = "replacement-pair"
        self.rebind_inputs(inputs)
        self.bad("queue extension lost a previous pair or its state history")

    def test_replacing_a_prior_source_id_is_rejected_even_with_current_input_binding(self):
        self.extend()
        # Keep present-day references coherent so this probes lineage, not dangling references.
        self.record = CoverageTests._replace_exact(self.record, "s1", "replacement-source")
        self.intake = CoverageTests._replace_exact(self.intake, "s1", "replacement-source")
        inputs = CoverageTests._replace_exact(aa.load(self.run / "inputs.json"), "s1", "replacement-source")
        self.rebind_inputs(inputs)
        self.bad("queue extension lost or replaced a previous source identity")

    def test_a_prior_pair_cannot_be_reset_to_queued_and_lose_its_assessment_history(self):
        self.extend()
        item = self.record["items"][0]
        item.update(state="QUEUED", transitions=["QUEUED"], reason="The planted reset would erase the completed assessment.")
        item.pop("decision")
        item.pop("ledger")
        self.bad("queue extension lost a previous pair or its state history")


class ResidualBindingTests(GateCase):
    def static_quantity_claim(self, unit):
        source, recipient = self.record["evidence"][:2]
        def count(evidence):
            data = (self.run / evidence["path"]).read_bytes()
            return len(data.splitlines()) if unit == "lines" else 1
        row = {"id": "selected-size", "status": "static", "metric": f"captured-{unit}", "unit": unit,
               "scope": "Only these selected captures, not the entire project",
               "baseline": {"evidence": [recipient["id"]], "value": count(recipient)},
               "candidate": {"evidence": [source["id"]], "value": count(source)}}
        self.record["items"][0]["ledger"]["measurements"] = [row]
        claim = {"id": "static-quantity", "subject": "s1", "kind": "source_observation",
                 "text": aa.measurement_statement(row), "status": "supported", "level": "present",
                 "scope": "The selected source and recipient captures only", "limitations": "No whole-project footprint claimed.",
                 "evidence": [source["id"]], "measurement_refs": [row["id"]],
                 "review": "Counts are computed from the exact selected local captures."}
        self.record["claims"].append(claim)
        self.assertEqual(self.errors(), [])
        return claim

    def test_static_file_reference_does_not_license_fabricated_999_files(self):
        claim = self.static_quantity_claim("files")
        claim["text"] = "The selected source contains 999 files."
        self.bad("numeric measurement statement|metric/workload/units/direction")

    def test_static_line_reference_does_not_license_fabricated_999_lines(self):
        claim = self.static_quantity_claim("lines")
        claim["text"] = "The selected source contains 999 lines."
        self.bad("numeric measurement statement|metric/workload/units/direction")

    def test_measured_custom_unit_reference_does_not_license_fabricated_999_fixture_units(self):
        row, receipt = measured_counter(self.run, self.record)
        claim = {"id": "custom-quantity", "subject": "s1", "kind": "verified_outcome",
                 "text": aa.measurement_statement(row), "status": "supported", "level": "tested",
                 "scope": "Owned arithmetic fixture only", "limitations": "No donor or production improvement claimed.",
                 "evidence": [receipt["id"]], "execution": receipt["id"], "measurement_refs": [row["id"]],
                 "review": "The complete arithmetic comparison and its bound payload were reviewed."}
        self.record["claims"].append(claim)
        self.assertEqual(self.errors(), [])
        claim["text"] = "The owned comparison uses 999 fixture-units."
        self.bad("numeric measurement statement|metric/workload/units/direction")

    def test_qualitative_estimate_with_explicit_null_range_keeps_the_pilot_available(self):
        item = self.record["items"][0]
        row = {"id": "qualitative-null-range", "status": "estimated", "metric": "integration-burden",
               "unit": "qualitative", "scope": "Only the sender parameter seam", "range": None,
               "qualitative": "Add an identity parameter to the existing sender.",
               "assumptions": "Receiver semantics remain a prerequisite; no execution is claimed.",
               "evidence": [self.record["evidence"][0]["id"]]}
        item["ledger"]["measurements"] = [row]
        item["decision"]["basis"]["measurements"] = [row["id"]]
        self.assertEqual(self.errors(), [])
        self.assertEqual(item["decision"]["result"], "ADAPT-with-prerequisite")
        self.assertEqual(item["decision"]["experiment"]["state"], "proposed")

    def test_unknown_measurement_can_record_empty_or_same_pair_contextual_evidence(self):
        item = self.record["items"][0]
        row = {"id": "unknown-context", "status": "unknown", "metric": "runtime-cost", "unit": "USD",
               "scope": "The unrun sender comparison", "note": "Source context is available; cost is still unmeasured.",
               "evidence": []}
        item["ledger"]["measurements"] = [row]
        item["decision"]["basis"]["measurements"] = [row["id"]]
        self.assertEqual(self.errors(), [])
        row["evidence"] = [evidence["id"] for evidence in self.record["evidence"]]
        self.assertEqual(self.errors(), [])
        self.assertEqual(item["decision"]["experiment"]["state"], "proposed")

    def test_unknown_measurement_rejects_missing_or_foreign_contextual_evidence(self):
        other = self.root / "unknown-multi"
        other.mkdir()
        self.run, self.record, self.intake = v2_fixture(other, two_recipients=True)
        item = self.record["items"][0]
        foreign = next(evidence["id"] for evidence in self.record["evidence"] if evidence["subject"] == "target2")
        row = {"id": "unknown-context", "status": "unknown", "metric": "runtime-cost", "unit": "USD",
               "scope": "The unrun first-recipient comparison", "note": "Missing cost is not a negative judgment."}
        item["ledger"]["measurements"] = [row]
        item["decision"]["basis"]["measurements"] = [row["id"]]
        for reference in ("missing-capture", foreign):
            with self.subTest(reference=reference):
                row["evidence"] = [reference]
                self.bad("unknown/duplicate evidence|belongs to another source/recipient")

    def test_social_media_post_alias_requires_a_no_resource_background_lookup(self):
        self.record, self.intake = recapture_donor(
            self.run, self.record, self.intake,
            "A documented bounded retry uses a stable request ID. The project is called StableRetry.\n",
            kind="social-media-post")
        self.assertEqual(self.errors(), [])
        status = aa.contract_status(self.record, self.run)
        self.assertIn("s1: social source without resource links needs a recorded background/project lookup", status["outstanding"])
        self.seal()
        self.bad("background/project lookup", complete=True)


if __name__ == "__main__":
    unittest.main()
