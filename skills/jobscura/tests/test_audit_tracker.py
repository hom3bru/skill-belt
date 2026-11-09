"""Offline regression and positive controls for tracker audit findings R2 and R8."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
tracker_diff = importlib.import_module("tracker_diff")


class TrackerAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def row(self, record_id="A", status="applied", employer="Example Arts"):
        return {"Record ID": record_id, "Company": employer, "Title": "Coordinator", "Status": status}

    def compare(self, before, after):
        for name, rows in (("before", before), ("after", after)):
            (self.root / (name + ".json")).write_text(json.dumps(rows), encoding="utf-8")
        return tracker_diff.compare(self.root / "before.json", self.root / "after.json")

    def transition(self, before, after):
        return self.compare([self.row(status=before)], [self.row(status=after)])

    def test_unidentified_loss_blocks_and_identified_changes_keep_contract(self):
        result = self.compare([self.row(), self.row("")], [self.row()])
        self.assertEqual(result["status"], "blocked")
        problem = next(p for p in result["problems"] if p["kind"] == "unidentified_rows_decreased")
        self.assertEqual((problem["before"], problem["after"]), (1, 0))
        self.assertIn("record IDs", problem["message"])
        self.assertIn("by hand", problem["message"])
        for side, rows, missing in (("before", 2, 1), ("after", 1, 0)):
            self.assertEqual((result[side]["rows"], result[side]["unidentified"], result[side]["records"]),
                             (rows, missing, 1))
        self.assertIn("before", {r.get("side") for r in result["review"]})
        added = self.compare([self.row()], [self.row(), self.row("B", employer="Other Org")])
        self.assertEqual((added["status"], added["added"]), ("conserved", ["B"]))
        removed = self.compare([self.row(), self.row("B", employer="Other Org")], [self.row()])
        self.assertEqual(removed["status"], "blocked")
        self.assertIn({"kind": "record_removed", "record_id": "B", "employer": "Other Org",
                       "title": "Coordinator"}, removed["problems"])
        run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "tracker_diff.py"),
                              "--before", str(self.root / "before.json"),
                              "--after", str(self.root / "after.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "blocked")

    def test_retained_unidentified_rows_require_review(self):
        for rows in ([self.row(), self.row("")], [self.row(""), self.row()]):
            with self.subTest(rows=rows):
                result = self.compare(rows, rows)
                self.assertEqual(result["status"], "review_required")
                self.assertEqual(result["problems"], [])
                self.assertEqual({r["side"] for r in result["review"]
                                  if r["kind"] == "rows_without_record_id"}, {"before", "after"})
                self.assertEqual(result["before"]["unidentified"], 1)
        clean = self.compare([self.row()], [self.row()])
        self.assertEqual(clean["status"], "conserved")
        increasing = self.compare([self.row()], [self.row(), self.row("")])
        self.assertEqual(increasing["status"], "review_required")
        self.assertEqual(increasing["problems"], [])
        for name, status in (("before", "applied"), ("after", "interview")):
            (self.root / (name + ".json")).write_text(json.dumps([
                {"Company": "Example Arts", "Title": "Coordinator", "Status": status}]), encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "tracker_diff.py"),
                              "--before", str(self.root / "before.json"),
                              "--after", str(self.root / "after.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stdout)
        self.assertEqual(json.loads(run.stderr), {"status": "blocked",
                         "error": "neither export has record IDs; map one with --map record_id=Header"})
        self.assertEqual(run.stdout, "")
        for name, status in (("before", "applied"), ("after", "interview")):
            (self.root / (name + ".json")).write_text(json.dumps([
                {"Tracking Key": "A", "Company": "Example Arts", "Title": "Coordinator", "Status": status}]),
                encoding="utf-8")
        mapped = subprocess.run([sys.executable, "-B", str(SCRIPTS / "tracker_diff.py"),
                                 "--before", str(self.root / "before.json"),
                                 "--after", str(self.root / "after.json"), "--map", "record_id=Tracking Key"],
                                capture_output=True, text=True)
        self.assertEqual(mapped.returncode, 0, mapped.stderr)
        self.assertEqual(json.loads(mapped.stdout)["status"], "conserved")

    def test_rank_decreases_and_history_loss_block_with_negation_controls(self):
        for old, new in (("interview", "applied"), ("offer pending", "submitted"),
                         ("offered", "interviewing"), ("applied; interview; offer", "interview"),
                         ("offer", "applied; not offered"), ("interview", "not applied"),
                         ("applied", ""), ("accepted", "active"),
                         ("interview", "never interviewed; submitted")):
            with self.subTest(old=old, new=new):
                result = self.transition(old, new)
                self.assertEqual(result["status"], "blocked")
                self.assertIn("application_history_regressed", {p["kind"] for p in result["problems"]})
        for old, new in (("applied", "interview"), ("interview", "offer"), ("offer", "accepted"),
                         ("not applied", "active"), ("never interviewed", "submitted"),
                         ("yet to interview", "applied"), ("not yet offered; applied", "submitted"),
                         ("not applied; interview", "interview"), ("submitted", "applied")):
            with self.subTest(old=old, new=new):
                result = self.transition(old, new)
                self.assertEqual(result["status"], "conserved")
                self.assertEqual(result["review"], [])

    def test_terminal_reopenings_require_review_and_forward_moves_stay_silent(self):
        for terminal in ("rejected", "declined", "withdrawn", "hired", "accepted"):
            for ranked in ("applied", "interview", "offer"):
                with self.subTest(terminal=terminal, ranked=ranked):
                    result = self.transition(terminal, ranked)
                    self.assertEqual(result["status"], "review_required")
                    self.assertEqual(result["problems"], [])
                    self.assertEqual([r["kind"] for r in result["review"]], ["status_reopened"])
            self.assertEqual(self.transition("offer", terminal)["status"], "conserved")
            self.assertEqual(self.transition(terminal, terminal)["status"], "conserved")
        self.assertEqual(self.transition("not accepted; interview", "offer")["status"], "conserved")

    def test_terminal_changes_require_review_and_same_terminal_keeps_history(self):
        for old, new in (("rejected", "withdrawn"), ("accepted", "declined"),
                         ("offer; accepted", "offer; hired")):
            with self.subTest(old=old, new=new):
                result = self.transition(old, new)
                self.assertEqual(result["status"], "review_required")
                self.assertEqual(result["problems"], [])
                self.assertEqual([r["kind"] for r in result["review"]], ["terminal_status_changed"])
        for old, new in (("offer; accepted", "accepted"), ("accepted", "accepted; not declined"),
                         ("offer", "accepted")):
            self.assertEqual(self.transition(old, new)["status"], "conserved")


if __name__ == "__main__":
    unittest.main()
