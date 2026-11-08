"""Offline v2 behavior and negative controls. Original v1 suite stays unchanged."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import demo
import study as s


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.base, self.rule, self.hash, self.policy, self.source, self.plan = demo.fixture()
        self.rule["threshold"] = 0.8

    def report(self):
        return s.score(self.cases, self.base, self.rule, self.hash, 0.8, "holdout", self.policy["label_sources"])

    def decision(self):
        seal = s.seal_study(self.cases, self.base, self.rule, self.hash, self.policy, 0.8, self.source, self.plan)
        return s.decide(self.cases, self.base, self.rule, self.hash, self.policy, seal, self.source, self.plan)

    def issue(self, check):
        report = s.check_obligations(self.source, self.plan)
        self.assertFalse(report["passed"])
        self.assertIn(check, [x["check"] for x in report["issues"]])

    def test_obligations_preserved(self):
        self.assertTrue(s.check_obligations(self.source, self.plan)["passed"])

    def test_dropped_human_gate(self):
        self.plan["operations"][0]["kind"] = "rule"
        self.issue("human_gate")

    def test_unbounded_retry(self):
        self.plan["operations"][1]["max_retries"] = None
        self.issue("retry_cap")

    def test_missing_required_input(self):
        self.plan["operations"][1]["requires"].append("missing-variable")
        self.issue("required_input")

    def test_wrong_entity_witness(self):
        self.plan["operations"][1]["witness_entity"] = "another-entity"
        self.issue("witness_owner")

    def test_unmapped_obligation(self):
        self.plan["operations"].pop(0)
        self.issue("unmapped_obligation")

    def test_unused_gate_does_not_satisfy_input_obligation(self):
        self.plan["operations"][1]["requires"].remove("approval")
        self.issue("required_input")

    def test_consumer_and_recovery(self):
        self.plan["operations"][2]["requires"] = []
        self.issue("consumer")
        self.plan["operations"][1].pop("reconciliation")
        self.issue("reconciliation")

    def test_source_seal(self):
        self.source["obligations"][0]["operation"] = "other"
        with self.assertRaisesRegex(s.InputError, "source seal"):
            s.check_obligations(self.source, self.plan)

    def test_full_flow_accounting_and_ordinary_hybrid(self):
        r = self.report()
        c = r["counts"]
        self.assertEqual(c["eligible"], 400)
        self.assertEqual(c["gated_out"], 100)
        self.assertEqual(c["attempted"], 300)
        self.assertEqual(c["correct"] + c["wrong"], 400)
        self.assertEqual(c["fallback"], 100)
        self.assertEqual(r["arms"]["hybrid"]["correct"], 400)
        self.assertEqual(r["arms"]["hybrid"]["measurements"]["runtime_llm_calls"]["total"], 100)
        self.assertEqual(r["routed_coverage"], 0.75)
        self.assertLess(r["teacher_agreement"], 1)
        self.assertEqual(r["correctly_routed_coverage"], 0.75)
        self.assertFalse(r["provenance_verified"])

    def test_conflicts_missing_state_and_bad_evidence_fail_closed(self):
        row = self.rule["records"][201]
        for field, value, expected in (("conflict", True, "abstained"), ("input_valid", False, "gated_out"),
                                       ("evidence_valid", False, "failed"), ("output_valid", False, "failed")):
            original = copy.deepcopy(row)
            row[field] = value
            self.assertEqual(s.route(row, 0.8), expected)
            row.clear(); row.update(original)
        row.pop("evidence_valid")
        self.assertEqual(s.route(row, 0.8), "failed")
        self.assertEqual(s.route(None, 0.8), "failed")

    def test_missing_and_failed_candidates_remain_eligible(self):
        self.rule["records"] = []
        r = self.report()
        self.assertEqual(r["counts"]["failed"], 400)
        self.assertEqual(r["counts"]["fallback"], 400)
        self.assertEqual(r["counts"]["eligible"], 400)
        self.assertIsNone(r["arms"]["hybrid"]["measurements"]["runtime_llm_calls"]["total"])

    def test_fallback_requires_existing_authority(self):
        self.rule["fallback_authorized"] = False
        with self.assertRaises(s.InputError):
            self.report()

    def test_utility_and_negation_controls(self):
        r = demo.run()
        self.assertGreater(r["selective_utility"], r["always_abstain_utility"])
        self.assertEqual(r["negation_sensitive_verdict"], "Conversion not supported")
        self.assertEqual(r["decision"]["verdict"], "Bounded conversion supported")

    def test_sweep_uses_only_development(self):
        a = s.sweep(self.cases, self.base, self.rule, self.hash, [0.5, 0.8, 1], self.policy)
        for row in self.cases["cases"]:
            if row["split"] == "holdout":
                row["expectation"]["output"] = not row["expectation"]["output"]
        b = s.sweep(self.cases, self.base, self.rule, self.hash, [0.5, 0.8, 1], self.policy)
        self.assertEqual(a, b)

    def test_threshold_policy_and_artifact_seals(self):
        seal = s.seal_study(self.cases, self.base, self.rule, self.hash, self.policy, 0.8, self.source, self.plan)
        changed = copy.deepcopy(self.policy)
        changed["quality"]["value"] = 0.1
        with self.assertRaisesRegex(s.InputError, "seal"):
            s.decide(self.cases, self.base, self.rule, self.hash, changed, seal, self.source, self.plan)
        self.rule["threshold"] = 0.5
        with self.assertRaisesRegex(s.InputError, "threshold"):
            s.decide(self.cases, self.base, self.rule, self.hash, self.policy, seal, self.source, self.plan)
        self.rule["artifact_sha256"] = "0" * 64
        with self.assertRaisesRegex(s.InputError, "seal"):
            s.decide(self.cases, self.base, self.rule, self.hash, self.policy, seal, self.source, self.plan)

    def test_provenance_excludes_self_labels(self):
        row = self.cases["cases"][201]
        row["label_arm_id"] = self.rule["arm_id"]
        self.assertIn(row["id"], self.report()["excluded_labels"])
        self.assertEqual(self.decision()["verdict"], "Insufficient evidence")

    def test_changed_case_content_cannot_reuse_seal(self):
        seal = s.seal_study(self.cases, self.base, self.rule, self.hash, self.policy, 0.8, self.source, self.plan)
        self.cases["cases"][201]["expectation"]["output"] = "changed"
        with self.assertRaisesRegex(s.InputError, "seal"):
            s.decide(self.cases, self.base, self.rule, self.hash, self.policy, seal, self.source, self.plan)

    def test_teacher_dependent_and_model_labels(self):
        row = self.cases["cases"][201]
        for change in ({"label_source": "teacher"}, {"independent_of_candidate": False},
                       {"label_source": "model-adjudicated"}):
            original = copy.deepcopy(row)
            row.update(change)
            self.assertIn(row["id"], self.report()["excluded_labels"])
            row.clear(); row.update(original)

    def test_component_self_labels_also_excluded(self):
        self.rule["components"] = ["upstream-labeler"]
        self.cases["cases"][201]["label_arm_id"] = "upstream-labeler"
        self.assertIn(self.cases["cases"][201]["id"], self.report()["excluded_labels"])
        self.assertEqual(self.decision()["verdict"], "Insufficient evidence")

    def test_group_leakage_and_inference(self):
        self.cases["cases"][201]["group_id"] = self.cases["cases"][200]["group_id"]
        self.assertEqual(self.decision()["verdict"], "Insufficient evidence")
        self.cases["cases"][201]["group_id"] = self.cases["cases"][0]["group_id"]
        with self.assertRaisesRegex(s.InputError, "leaks"):
            self.report()

    def test_obligations_block_supported_verdict(self):
        self.plan["operations"][0]["kind"] = "rule"
        self.assertEqual(self.decision()["verdict"], "Insufficient evidence")

    def test_four_verdicts(self):
        self.assertEqual(self.decision()["verdict"], "Bounded conversion supported")
        for row, case in zip(self.rule["records"], self.cases["cases"]):
            row["applicable"] = True
            row["status"] = "answered"
            row["output"] = case["expectation"]["output"]
        self.assertEqual(self.decision()["verdict"], "Conversion supported")
        self.policy["critical_error_cap"] = 0
        self.assertEqual(self.decision()["verdict"], "Insufficient evidence")
        for row in self.rule["records"]:
            row["output"] = not row["output"]
        self.assertEqual(self.decision()["verdict"], "Conversion not supported")

    def test_noninferiority_path(self):
        self.policy["quality"] = {"kind": "noninferiority", "value": 0.03}
        self.assertEqual(self.decision()["verdict"], "Bounded conversion supported")

    def test_wilson_published_example(self):
        # CAMIS SAS example: 36/154, 95% Wilson 0.17390..0.30659.
        lo, hi = s.wilson(36, 154)
        self.assertAlmostEqual(lo, 0.17390, places=5)
        self.assertAlmostEqual(hi, 0.30659, places=5)

    def test_newcombe_published_paired_example(self):
        # CAMIS R paired table [[20,15],[6,5]], MOVER-NW.
        lo, hi = s.newcombe(20, 15, 6, 5)
        self.assertAlmostEqual(lo, 0.002602, places=6)
        self.assertAlmostEqual(hi, 0.369943, places=6)

    def test_exact_mcnemar_and_extremes(self):
        # Altman table 6.2 discordants 5 vs 0: two-sided exact 2/2**5.
        self.assertAlmostEqual(s.mcnemar(5, 0), 0.0625)
        self.assertEqual(s.mcnemar(0, 0), 1)
        self.assertEqual(s.mcnemar(1000, 1000), 1)
        self.assertEqual(s.wilson(0, 400)[0], 0)
        self.assertAlmostEqual(s.wilson(400, 400)[1], 1)

    def test_newcombe_original_table_negative_correlation_and_boundaries(self):
        # Newcombe 1998, Table III, method 10 (printed to four decimals).
        for cells, expected in (((36, 12, 2, 0), (0.0569, 0.3404)),
                                ((0, 30, 0, 0), (0.8395, 1.0)),
                                ((27, 0, 0, 27), (-0.0351, 0.0351))):
            with self.subTest(cells=cells):
                actual = s.newcombe(*cells)
                for got, want in zip(actual, expected):
                    self.assertAlmostEqual(got, want, places=4)

    def packet_answers(self):
        hybrid, _ = s.cascade(self.cases, self.base, self.rule, self.hash, 0.8)
        bundle = s.adjudication_packet(self.cases, self.base, hybrid, self.hash, 42, 10)
        packet, key = bundle["packet"], bundle["sealed_key"]
        by_id = s.cases_v2(self.cases)
        answers = {"schema_version": 2, "packet_sha256": s.digest(packet), "blind": True, "key_disclosed": False,
                   "label_source": "human-adjudicated", "independent_of_candidate": True,
                   "records": [{"id": token, "expectation": by_id[m["case_id"]]["expectation"]}
                               for token, m in key["mapping"].items()]}
        return packet, key, answers

    def test_blinded_disagreements_and_seeded_agreements(self):
        packet, key, answers = self.packet_answers()
        self.assertEqual(sum(m["selection"] == "agreement-sample" for m in key["mapping"].values()), 10)
        self.assertEqual(len(packet["items"]), 40)  # 30 incumbent errors plus 10 agreements
        text = json.dumps(packet)
        self.assertNotIn('"arm_id"', text)
        self.assertNotIn('"expectation"', text)
        self.assertNotIn('"selection"', text)
        self.assertEqual(packet, self.packet_answers()[0])
        result = s.ingest_adjudication(self.cases, packet, key, answers, self.hash)
        self.assertEqual(result["agreement_sample"]["n"], 10)
        self.assertFalse(result["provenance_verified"])

    def test_nonblind_adjudication_rejected(self):
        packet, key, answers = self.packet_answers()
        answers["blind"] = False
        with self.assertRaisesRegex(s.InputError, "not blind"):
            s.ingest_adjudication(self.cases, packet, key, answers, self.hash)
        answers["blind"] = True
        answers["key_disclosed"] = True
        with self.assertRaisesRegex(s.InputError, "not blind"):
            s.ingest_adjudication(self.cases, packet, key, answers, self.hash)

    def test_adjudication_tampering_and_incompleteness(self):
        packet, key, answers = self.packet_answers()
        answers["records"].pop()
        with self.assertRaisesRegex(s.InputError, "incomplete"):
            s.ingest_adjudication(self.cases, packet, key, answers, self.hash)
        packet["items"][0]["A"]["output"] = "tampered"
        with self.assertRaisesRegex(s.InputError, "seal"):
            s.ingest_adjudication(self.cases, packet, key, answers, self.hash)

    def test_shared_error_estimated_from_agreements(self):
        for row in self.base["records"]:
            row["output"] = "shared-wrong-answer"
        same = copy.deepcopy(self.base); same["arm_id"] = "other"
        b = s.adjudication_packet(self.cases, self.base, same, self.hash, 9, 12)
        answers = {"schema_version": 2, "packet_sha256": s.digest(b["packet"]), "blind": True,
                   "key_disclosed": False, "label_source": "human-adjudicated", "independent_of_candidate": True,
                   "records": [{"id": token, "expectation": {"status": "answered", "output": True}}
                               for token in b["sealed_key"]["mapping"]]}
        result = s.ingest_adjudication(self.cases, b["packet"], b["sealed_key"], answers, self.hash)
        self.assertEqual(result["agreement_sample"]["shared_errors"], 12)

    def test_v2_cli_and_original_strict_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / "request.json"
            request.write_text(json.dumps({"source": self.source, "plan": self.plan}), encoding="utf-8")
            p = subprocess.run([sys.executable, "-B", str(Path(s.__file__)), "obligations", "--request", str(request)],
                               text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(json.loads(p.stdout)["passed"])
        self.cases["schema_version"] = 3
        with self.assertRaises(s.InputError): self.report()

    def test_malformed_v2_envelopes(self):
        for value in (None, [], "not-an-envelope", {"schema_version": True}, {"schema_version": 1}):
            with self.subTest(value=value), self.assertRaises(s.InputError):
                s.cases_v2(value)

    def test_cli_complete_study_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / "request.json"
            def call(command, payload):
                request.write_text(json.dumps(payload), encoding="utf-8")
                p = subprocess.run([sys.executable, "-B", str(Path(s.__file__)), command, "--request", str(request)],
                                   capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(p.returncode, 0, p.stderr)
                return json.loads(p.stdout)
            common = {"case_set": self.cases, "baseline": self.base, "candidate": self.rule, "case_hash": self.hash}
            tuning = call("sweep", {**common, "thresholds": [0.5, 0.8, 1], "policy": self.policy})
            self.assertEqual(tuning["chosen_threshold"], 0.8)
            call("score", {**common, "threshold": 0.8})
            hybrid = call("cascade", {**common, "threshold": 0.8})["arm"]
            seal = call("seal", {**common, "policy": self.policy, "threshold": 0.8, "source": self.source, "plan": self.plan})
            decision = call("decide", {**common, "policy": self.policy, "seal": seal, "source": self.source, "plan": self.plan})
            self.assertEqual(decision["verdict"], "Bounded conversion supported")
            bundle = call("packet", {**common, "candidate": hybrid, "seed": 42, "agreements": 10})
            packet, key = bundle["packet"], bundle["sealed_key"]
            # Authored response simulation only; no human adjudication occurred.
            by_id = s.cases_v2(self.cases)
            answers = {"schema_version": 2, "packet_sha256": s.digest(packet), "blind": True, "key_disclosed": False,
                       "label_source": "human-adjudicated", "independent_of_candidate": True,
                       "records": [{"id": token, "expectation": by_id[m["case_id"]]["expectation"]}
                                   for token, m in key["mapping"].items()]}
            result = call("ingest", {"case_set": self.cases, "packet": packet, "key": key,
                                     "answers": answers, "case_hash": self.hash})
            self.assertEqual(result["agreement_sample"]["n"], 10)


if __name__ == "__main__":
    unittest.main()
