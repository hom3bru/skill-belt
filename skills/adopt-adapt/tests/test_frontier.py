"""Regression cases for actionable retained-lead reports."""
import copy
from pathlib import Path
import tempfile
import unittest

from gate_fixtures import aa, discard, replace_ref, v2_fixture


class FrontierTests(unittest.TestCase):
    def test_manual_templates_put_current_burden_before_prototype(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("output-template.md", "bounded-ledger-template.md"):
            with self.subTest(template=name):
                body = (root / "references" / name).read_text(encoding="utf-8")
                self.assertIn("Current burden:", body)
                self.assertIn("unobserved", body)
                self.assertIn("recipient-only", body)
                self.assertLess(body.index("Current burden:"), body.index("Prototype:"))

    def test_unconfirmed_burden_keeps_prototype_conditional(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("output-template.md", "bounded-ledger-template.md"):
            with self.subTest(template=name):
                body = (root / "references" / name).read_text(encoding="utf-8")
                self.assertIn("Unconfirmed need", body)
                self.assertIn("recipient observation + evidence, or unobserved", body)
                self.assertIn("recipient-only burden observation if unobserved", body)
                self.assertIn("conditional on confirmed need", body)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.record, self.intake = v2_fixture(self.root)
        self.record["report_format"] = "decision-frontier-v1"
        self.lead = discard(self.record, reason="research-lead")
        self.lead["promising_check"] = "Compare the receiver under a lost acknowledgement."

    def add_lead(self):
        """Build another owned donor pair and its matching fixture inputs."""
        n = len(self.record["sources"]) + 1
        sid = f"s{n}"
        donor = self.root / f"donor-{n}.txt"
        donor.write_text(f"Owned method {n} describes a stable request ID.\n", encoding="utf-8")
        source = dict(self.record["sources"][0], id=sid, locator=str(donor),
                      revision=aa.digest(donor.read_bytes()))
        old = self.record["evidence"][0]["id"]
        capture = aa.capture(self.run, donor, sid, source["revision"])
        capture["read_scope"] = "Complete supplied method"
        self.record["sources"].append(source)
        self.record["evidence"].append(capture)
        claim = dict(self.record["claims"][0], id=f"method-{n}", subject=sid, evidence=[capture["id"]])
        self.record["claims"].append(claim)
        item = replace_ref(copy.deepcopy(self.record["items"][0]), old, capture["id"])
        item = replace_ref(item, "c1", claim["id"])
        item.update(id=f"q{n}", source=sid)
        self.record["items"].append(item)
        node = replace_ref(copy.deepcopy(self.intake["artifacts"][0]), old, capture["id"])
        node["id"] = sid
        self.intake["artifacts"].append(node)
        inputs = aa.load(self.run / "inputs.json")
        inputs["sources"].append(source)
        inputs["pairs"].append({k: item[k] for k in ("id", "source", "recipient")})
        self.intake["inputs_sha256"] = aa.digest(aa.canonical(inputs))
        aa.save(self.run / "inputs.json", inputs)
        aa.save(self.run / "intake.json", self.intake)
        return item["decision"]

    def report(self):
        return aa.render(self.record, self.run)

    def frontier(self):
        return self.report().split("## Decision frontier\n", 1)[1].split("\n## ", 1)[0]

    def prerequisite(self):
        return {
            "id": "receiver-contract",
            "test": "Inspect the existing receiver's retry contract before comparing donor implementations.",
            "criterion": "A request ID survives a lost acknowledgement at the receiving endpoint.",
            "reopen": "Run the separate donor experiments if the contract supports a stable ID.",
            "evidence": [self.record["evidence"][1]["id"]],
        }

    def use_schema3(self):
        self.record["schema_version"] = 3
        inputs = aa.load(self.run / "inputs.json")
        inputs["schema_version"] = 3
        self.intake["inputs_sha256"] = aa.digest(aa.canonical(inputs))
        aa.save(self.run / "inputs.json", inputs)
        aa.save(self.run / "intake.json", self.intake)
        experiment = self.lead["experiment"]
        experiment.update(flips_to="ADAPT-with-prerequisite", cluster="retry",
                          seam_evidence=[self.record["evidence"][1]["id"]])
        self.lead["promising_check"] = experiment["test"]

    def test_schema3_lead_requires_read_recipient_seam_evidence(self):
        self.use_schema3()
        experiment = self.lead["experiment"]
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.assertIn("ADAPT-with-prerequisite", self.frontier())
        del experiment["seam_evidence"]
        self.assertIn("seam evidence", " ".join(aa.validate(self.record, self.run)))
        experiment["seam_evidence"] = [self.record["evidence"][0]["id"]]
        self.assertIn("evidence belongs to another source/recipient", " ".join(aa.validate(self.record, self.run)))

    def test_schema3_lead_cannot_publish_a_different_check_in_the_label(self):
        self.use_schema3()
        self.lead["promising_check"] = "Try a different contract."
        self.assertIn("promising_check must match", " ".join(aa.validate(self.record, self.run)))

    def test_schema3_same_test_has_one_cluster_and_a_different_test_stays_distinct(self):
        self.use_schema3()
        other = self.add_lead()
        other["experiment"]["cluster"] = "duplicate"
        self.assertIn("same recipient check", " ".join(aa.validate(self.record, self.run)))
        other["experiment"]["cluster"] = "retry"
        self.assertIn("(q1, q2)", self.frontier())
        other["experiment"]["test"] = "Change the failure schedule."
        other["promising_check"] = other["experiment"]["test"]
        self.assertIn("cluster has conflicting checks", " ".join(aa.validate(self.record, self.run)))

    def test_schema3_inputs_prevent_downgrading_to_schema2(self):
        self.use_schema3()
        self.record["schema_version"] = 2
        self.assertIn("input manifest schema", " ".join(aa.validate(self.record, self.run)))

    def test_schema3_groups_identical_checks_and_keeps_both_seam_citations(self):
        recipient = self.root / "recipient"
        flags = recipient / "flags.json"
        flags.write_text('{"stable_request_id": true}', encoding="utf-8")
        snapshot = aa.snapshot(recipient, ["entry.py", flags.name])
        entry = aa.capture(self.run, recipient / "entry.py", "target", snapshot["id"])
        config = aa.capture(self.run, flags, "target", snapshot["id"])
        for capture in (entry, config):
            capture["read_scope"] = "Complete fixture file"
        old = self.record["evidence"][1]["id"]
        self.record = replace_ref(self.record, old, entry["id"])
        self.record["recipients"][0].update(revision=snapshot["id"], snapshot=snapshot)
        self.record["evidence"][1] = entry
        self.record["evidence"].append(config)
        self.lead = self.record["items"][0]["decision"]
        self.use_schema3()
        other = self.add_lead()["experiment"]
        other["seam_evidence"] = [config["id"]]

        frontier = self.frontier()
        self.assertIn("(q1, q2)", frontier)
        evidence = ", ".join(sorted([entry["id"], config["id"]]))
        self.assertIn(f"Recipient seam evidence: {evidence}", frontier)
        self.assertTrue(aa.check_output(self.record, self.run, self.report()))
        other["criterion"] = "The alternate sender fixture produces a different outcome."
        self.assertNotIn("(q1, q2)", self.frontier())

    def test_schema3_cluster_cannot_span_recipients(self):
        with tempfile.TemporaryDirectory() as temp:
            run, record, intake = v2_fixture(Path(temp), two_recipients=True)
            record.update(schema_version=3, report_format="decision-frontier-v1")
            inputs = aa.load(run / "inputs.json")
            inputs["schema_version"] = 3
            aa.save(run / "inputs.json", inputs)
            intake["inputs_sha256"] = aa.digest(aa.canonical(inputs))
            aa.save(run / "intake.json", intake)
            discard(record, reason="research-lead")
            for item in record["items"]:
                decision = item["decision"]
                experiment = decision["experiment"]
                refs = [e["id"] for e in record["evidence"] if e["subject"] == item["recipient"]]
                experiment.update(cluster="retry", flips_to="ADAPT", seam_evidence=refs)
                decision["promising_check"] = experiment["test"]
            self.assertIn("cluster spans recipients", " ".join(aa.validate(record, run)))
            record["items"][1]["decision"]["experiment"]["cluster"] = "retry-target2"
            self.assertEqual(aa.validate(record, run), [])

    def test_schema3_mismatch_requires_named_assumption_and_both_sides(self):
        self.use_schema3()
        self.lead.pop("promising_check")
        basis = self.lead["basis"]
        basis["reason"] = "assumption-mismatch"
        self.assertIn("assumption", " ".join(aa.validate(self.record, self.run)))
        basis["assumption"] = "The donor has a single writer, but the receiving entry point runs concurrently."
        basis["evidence"] = [self.record["evidence"][1]["id"]]
        self.assertIn("donor evidence", " ".join(aa.validate(self.record, self.run)))
        basis["evidence"].append(self.record["evidence"][0]["id"])
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_same_experiment_shares_a_row_and_case_sensitive_commands_stay_separate(self):
        other = self.add_lead()
        first = self.lead["experiment"]
        first["test"] = "Replay SendCase under the lost acknowledgement fixture."
        other["experiment"]["test"] = first["test"]
        third = self.add_lead()
        third["experiment"]["test"] = first["test"].replace("SendCase", "sendcase")
        frontier = self.frontier()
        self.assertIn("q1, q2", frontier)
        self.assertIn("sendcase", frontier)
        self.assertLess(frontier.index("q1, q2"), frontier.index("q3"))
        other["experiment"]["criterion"] = "The fixture records a different outcome."
        self.assertNotIn("q1, q2", self.frontier())

    def test_shared_prerequisite_keeps_donor_experiments_and_detects_stripping(self):
        self.lead["experiment"]["shared_prerequisite"] = self.prerequisite()
        other = self.add_lead()
        other["experiment"]["test"] = "Test whether the alternative store preserves the request ID."
        report = self.report()
        self.assertIn("q1, q2", self.frontier())
        self.assertIn("Test whether the alternative store preserves the request ID.", report)
        self.assertLess(report.index("aa:ledger:q1"), report.index("aa:verdict:q1"))
        self.assertIn("### Retained research lead", report)
        self.assertTrue(aa.check_output(self.record, self.run, report))
        with self.assertRaises(aa.Invalid):
            aa.check_output(self.record, self.run, report.replace("## Decision frontier", "## Omitted checks"))

    def test_shared_prerequisite_cannot_borrow_donor_evidence(self):
        prereq = self.prerequisite()
        prereq["evidence"] = [self.record["evidence"][0]["id"]]
        self.lead["experiment"]["shared_prerequisite"] = prereq
        self.assertIn("evidence belongs to another source/recipient", " ".join(aa.validate(self.record, self.run)))

    def test_shared_capture_retains_distinct_pair_criteria(self):
        self.use_schema3()
        first = self.lead["experiment"]
        first["criterion"] = "One logical retry produces one receiver effect."
        first["shared_prerequisite"] = dict(
            self.prerequisite(),
            test="Capture one current sender trace under one lost-acknowledgement schedule.",
            criterion="For q1 inspect duplicate effects. For q2 inspect request identity in that same trace.",
            reopen="Reopen each donor experiment only if its recipient observation establishes the need.",
        )
        other = self.add_lead()["experiment"]
        other["criterion"] = "One logical retry preserves its request identity."

        report = self.report()
        frontier = self.frontier()
        self.assertIn("(q1, q2)", frontier)
        self.assertEqual(frontier.count("- **Shared prerequisite**"), 1)
        self.assertIn(first["criterion"], report)
        self.assertIn(other["criterion"], report)
        self.assertTrue(aa.check_output(self.record, self.run, report))
        with self.assertRaises(aa.Invalid):
            aa.check_output(self.record, self.run, report.replace(other["criterion"], "Criterion omitted."))

    def test_same_prerequisite_id_cannot_hide_conflicting_criteria(self):
        self.lead["experiment"]["shared_prerequisite"] = self.prerequisite()
        other = self.add_lead()
        other["experiment"]["shared_prerequisite"]["criterion"] = "The receiver may lose the request ID."
        self.assertIn("conflicting shared prerequisite", " ".join(aa.validate(self.record, self.run)))

    def test_historical_format_keeps_legacy_heading(self):
        self.record.pop("report_format")
        report = self.report()
        self.assertNotIn("## Decision frontier", report)
        self.assertIn("### DISCARD (promising:", report)

    def test_blocked_check_stays_visible_below_a_runnable_check(self):
        other = self.add_lead()
        self.lead["experiment"]["shared_prerequisite"] = dict(
            self.prerequisite(), condition="the owner supplies the receiver contract")
        frontier = self.frontier()
        self.assertIn("Blocked until the owner supplies the receiver contract", frontier)
        self.assertLess(frontier.index("(q2)"), frontier.index("(q1)"))
        self.assertEqual(other["experiment"]["state"], "proposed")

    def test_unknown_or_open_pair_does_not_get_a_verdict(self):
        self.add_lead()
        self.record["items"][1].update(
            state="BLOCKED", transitions=["QUEUED", "RESEARCHING", "BLOCKED"],
            reason="The underlying source could not be retrieved.")
        self.record["items"][1].pop("decision")
        self.assertNotIn("q2", self.frontier())
        report = self.report()
        self.assertIn("q2: BLOCKED", report)
        self.assertNotIn("aa:verdict:q2", report)

    def test_same_text_is_not_grouped_across_recipients(self):
        with tempfile.TemporaryDirectory() as temp:
            run, record, _ = v2_fixture(Path(temp), two_recipients=True)
            record["report_format"] = "decision-frontier-v1"
            discard(record, reason="research-lead")
            report = aa.render(record, run)
        self.assertIn("for target (q1)", report)
        self.assertIn("for target2 (q2)", report)
        frontier = report.split("## Decision frontier\n", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("q1, q2", frontier)

    def test_new_init_includes_frontier_and_finalization_checks_it(self):
        pending = self.root / "pending"
        record = aa.init_run(pending, ["https://example.test/source"], ["target=generic"])
        self.assertEqual(record["report_format"], "decision-frontier-v1")
        output = pending / "report.md"
        aa.finalize(pending / "run.json", output)
        report = output.read_text(encoding="utf-8")
        self.assertIn("No retained lead checks.", report)
        self.assertTrue(aa.check_output(aa.load(pending / "run.json"), pending, report))
        extended = self.root / "extended"
        aa.extend_run(pending / "run.json", extended, ["https://example.test/next"], "Found the upstream work")
        expanded = aa.load(extended / "run.json")
        self.assertEqual(expanded["schema_version"], 3)
        self.assertEqual(aa.validate(expanded, extended), [])
