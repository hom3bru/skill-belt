"""Evaluate authored template examples; no production scanner or registry."""
import ast
import copy
import json
from pathlib import Path
import unittest

ASSETS = Path(__file__).resolve().parents[1] / "assets"


class TemplateTests(unittest.TestCase):
    def test_discovery_distinguishes_five_paths(self):
        ledger = json.loads((ASSETS / "discovery/ledger.json").read_text())
        self.assertEqual(len(ledger), 5)
        for row in ledger:
            file, line = row["evidence"].split(":")
            code = (ASSETS / "discovery" / file).read_text()
            self.assertLessEqual(int(line), len(code.splitlines()))
            values = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(code).body if isinstance(n, ast.Assign)}
            if values.get("ENABLED") is False:
                self.assertEqual(row["recommendation"], "exclude disabled path")
            elif "test-only" in values["CALLER"]:
                self.assertEqual(row["recommendation"], "exclude production savings")
            elif "RULE" in values:
                self.assertEqual(row["recommendation"], "reuse existing rule")
                self.assertEqual(row["savings"], 0)
            elif "REQUIRED_STATE" in values and values["REQUIRED_STATE"] is None:
                self.assertEqual(row["recommendation"], "insufficient evidence")
                self.assertIsNone(row["savings"])
            else:
                self.assertEqual(row["recommendation"], "test selective rule")

    def test_lifetime_closure_invalidates_only_dependent_assets(self):
        record = json.loads((ASSETS / "lifetime.json").read_text())
        def invalid(current):
            return {name for name, asset in record["assets"].items()
                    if any(current.get(key) != value for key, value in asset["closure"].items())}
        self.assertEqual(invalid(record["identities"]), set())
        for key, expected in (("source", {"rule", "source-cache"}), ("policy", {"rule"}), ("interpreter", {"rule"})):
            current = {**record["identities"], key: "changed"}
            self.assertEqual(invalid(current), expected)
        current = {**record["identities"], "annotation": "changed"}
        self.assertEqual(invalid(current), set())

    def test_partial_effect_not_replayed_or_completed(self):
        checkpoint = json.loads((ASSETS / "lifetime.json").read_text())["checkpoint"]
        self.assertEqual(checkpoint["status"], "partial")
        self.assertFalse(checkpoint["consumer_acknowledged"])
        self.assertFalse(checkpoint["replay_allowed"])
        self.assertTrue(checkpoint["next"])

    def test_economics_allows_loss_and_unknowns(self):
        rows = json.loads((ASSETS / "lifetime.json").read_text())["economics"]
        for row in rows:
            parts = [row[k] for k in ("net_events", "avoided_per_event", "runtime_per_event", "routing_check_fallback_per_event", "build_eval", "upkeep")]
            if None in parts:
                self.assertIsNone(row["net"])
            else:
                n, avoided, runtime, routing, build, upkeep = parts
                self.assertEqual(row["net"], n * (avoided - runtime - routing) - build - upkeep)
        self.assertLess(rows[0]["net"], 0)
        self.assertLess(rows[1]["net"], 0)
