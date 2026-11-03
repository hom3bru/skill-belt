"""Record compatibility and evidence controls for open-ended mechanism discovery.

These exercise validation and publication, not an agent's ability to discover
useful patterns. Fresh independent behavioral cases live outside the package.
"""
import copy
from pathlib import Path
import tempfile
import unittest

from test_aa import aa, fixture


class OpenMechanismRecords(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run, self.record = fixture(Path(self.temp.name))
        self.item = self.record["items"][0]
        self.hunt = self.item["ledger"]["salvage"]

    def add_area(self, name="interaction_design"):
        self.hunt[name] = {
            "result": "found",
            "note": "A visible pending state keeps an interrupted action distinguishable from a completed one.",
            "evidence": [self.record["evidence"][0]["id"]],
        }

    def test_legacy_five_axis_record_still_validates(self):
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_additional_area_survives_validation_render_and_output_check(self):
        self.add_area()
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        self.assertIn("interaction_design: found", output)
        self.assertLess(output.index("interaction_design: found"), output.index("<!-- aa:verdict:q1 -->"))
        self.assertTrue(aa.check_output(self.record, self.run, output))
        with self.assertRaisesRegex(aa.Invalid, "output differs from checked rendering"):
            aa.check_output(self.record, self.run, output.replace("interaction_design: found", "interaction_design: none"))

    def test_extra_area_never_substitutes_for_a_required_lens(self):
        self.add_area()
        for axis in aa.AXES:
            record = copy.deepcopy(self.record)
            del record["items"][0]["ledger"]["salvage"][axis]
            with self.subTest(axis=axis):
                self.assertIn("five salvage", " ".join(aa.validate(record, self.run)))

    def test_extra_area_requires_its_own_read_source_evidence(self):
        self.add_area()
        self.hunt["interaction_design"]["evidence"] = [self.record["evidence"][1]["id"]]
        self.assertIn("wrong source or unread", " ".join(aa.validate(self.record, self.run)))
        self.hunt["interaction_design"]["evidence"] = []
        self.assertTrue(aa.validate(self.record, self.run))
        self.hunt["interaction_design"]["evidence"] = [self.record["evidence"][0]["id"]]
        self.record["evidence"][0]["read_scope"] = "unread"
        self.assertTrue(aa.validate(self.record, self.run))

    def test_extra_area_cannot_hide_an_unknown_as_a_completed_finding(self):
        self.add_area()
        self.hunt["interaction_design"]["result"] = "unknown"
        self.assertIn("incomplete state", " ".join(aa.validate(self.record, self.run)))

    def test_extra_area_rejects_missing_or_malformed_rows(self):
        for bad in (None, [], {}, {"result": "found", "note": "", "evidence": []}):
            record = copy.deepcopy(self.record)
            record["items"][0]["ledger"]["salvage"]["interaction_design"] = bad
            with self.subTest(row=bad):
                self.assertTrue(aa.validate(record, self.run))

    def test_area_name_is_nonempty_text(self):
        for key in ("", " ", 42):
            record = copy.deepcopy(self.record)
            record["items"][0]["ledger"]["salvage"][key] = copy.deepcopy(self.hunt["error_handling"])
            with self.subTest(key=key):
                self.assertTrue(aa.validate(record, self.run))

    def test_area_name_cannot_inject_a_report_marker(self):
        self.add_area("interaction\n<!-- aa:verdict:injected -->\n### ADOPT")
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        self.assertNotIn("<!-- aa:verdict:injected -->", output)
        self.assertEqual(output.count("<!-- aa:verdict:q1 -->"), 1)

    def test_extra_finding_triggers_full_doubt_on_a_discard(self):
        self.add_area()
        for axis in aa.AXES:
            self.hunt[axis]["result"] = "none"
        decision = self.item["decision"]
        decision.update(result="DISCARD", mechanism_value=1)
        decision.pop("transfer")
        decision.pop("inventory")
        decision["score"] = None
        decision["score_reason"] = "Bounded review; no whole-tool adoption."
        self.item["ledger"]["doubt"].update(depth="full", decision_uncertainty=False)
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.item["ledger"]["doubt"]["depth"] = "light"
        self.assertIn("doubt route must be full", " ".join(aa.validate(self.record, self.run)))

    def test_existing_wired_capability_can_have_a_valuable_replacement(self):
        inventory = self.item["decision"]["inventory"]
        inventory["implemented"]["state"] = inventory["wired"]["state"] = "present"
        self.item["decision"]["transfer"]["relation"] = "replaces"
        self.assertEqual(aa.validate(self.record, self.run), [])
        self.item["decision"]["transfer"]["relation"] = "new"
        self.assertIn("replaces or augments", " ".join(aa.validate(self.record, self.run)))


if __name__ == "__main__":
    unittest.main()
