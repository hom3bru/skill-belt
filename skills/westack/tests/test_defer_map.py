"""The defer map: schema shape, the never-defer list, session-scoped consent, honest `unmeasured`
evidence and a seed limited to capability and convention defers."""
import json
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
v = fixtures.v
DELIVERY = {"push", "merge", "deploy", "publish", "tracker-write", "message"}


def load(relative):
    return v.read_json(ROOT / relative)


class DeferMapTests(unittest.TestCase):
    def setUp(self):
        self.schema = load("contracts/defer-map.schema.json")
        self.map = load("references/defer-map.json")

    def errors(self, value):
        return v.shape(value, self.schema["root"], defs=self.schema["$defs"])

    def test_map_matches_schema(self):
        self.assertEqual(self.errors(self.map), [])

    def test_schema_rejects_unknown_kind_and_missing_disclosure(self):
        entry = json.loads(json.dumps(self.map["entries"][0]))
        entry["kind"] = "prestige"
        del entry["side_effects"]
        broken = dict(self.map, entries=[entry])
        found = self.errors(broken)
        self.assertTrue(any("value outside enum" in e for e in found), found)
        self.assertTrue(any("missing side_effects" in e for e in found), found)

    def test_seed_is_capability_or_convention_only(self):
        self.assertTrue(self.map["entries"])
        self.assertEqual({e["kind"] for e in self.map["entries"]} - {"capability", "convention"}, set())

    def test_every_entry_starts_unmeasured(self):
        for entry in self.map["entries"]:
            with self.subTest(entry=entry["id"]):
                self.assertEqual(entry["evidence"]["status"], "unmeasured")
                self.assertIsNone(entry["evidence"]["eval_run"])
                self.assertIsNone(entry["evidence"]["candidate_commit"])

    def test_side_effects_require_consent(self):
        for entry in self.map["entries"]:
            with self.subTest(entry=entry["id"]):
                effects = entry["side_effects"]
                if effects["status"] != "none":
                    self.assertTrue(entry["consent_required"])
                if effects["status"] == "known":
                    self.assertTrue(effects["effects"])

    def test_delivery_is_fenced_and_never_deferred(self):
        never = " ".join(self.map["never_defer"]).lower()
        for word in ("evidence", "guardrails", "authority", "push", "merge", "deploy"):
            self.assertIn(word, never)
        for entry in self.map["entries"]:
            with self.subTest(entry=entry["id"]):
                self.assertEqual(set(entry["fence"]), DELIVERY)

    def test_consent_is_session_scoped_and_never_persisted(self):
        consent = self.map["consent"]
        self.assertEqual(consent["scope"], "session")
        self.assertFalse(consent["persisted"])

    def test_every_entry_can_be_detected(self):
        ids = [e["id"] for e in self.map["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in self.map["entries"]:
            with self.subTest(entry=entry["id"]):
                detect = entry["detect"]
                self.assertTrue(detect["skill_names"] or detect["files"] or detect["repo_markers"])


if __name__ == "__main__":
    unittest.main()
