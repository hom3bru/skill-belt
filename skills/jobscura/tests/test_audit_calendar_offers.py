"""Regression controls for calendar identity and inconsistent vesting terms."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
deadlines = importlib.import_module("deadlines")
offers = importlib.import_module("offer_compare")
common = importlib.import_module("jobscura_common")


class CalendarOfferAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def rows(self):
        return [{"employer": "Example", "title": title, "url": "https://example.org/" + title,
                 "deadline": "2026-11-20"} for title in ("Engineer", "Designer")]

    def plan(self, rows):
        return deadlines.plan(self.save("tracker.json", rows), "UTC", "2026-11-04T12:00:00Z")

    def cli(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *map(str, args)],
                              capture_output=True, text=True)

    def event_uids(self, text):
        events = {}
        for event in text.replace("\r\n ", "").split("BEGIN:VEVENT")[1:]:
            fields = dict(line.split(":", 1) for line in event.splitlines() if ":" in line)
            events[fields["SUMMARY"]] = fields["UID"]
        return events

    def test_url_fallback_is_unique_stable_and_preserves_identified_uids(self):
        rows = self.rows()
        rows.append({"employer": "Example", "title": "Legacy", "record_id": "JOB-1",
                     "requisition_id": "REQ-42", "deadline": "2026-11-20"})
        text, count = deadlines.calendar(self.plan(rows), "UTC")
        uids = self.event_uids(text)
        self.assertEqual(count, 3)
        self.assertEqual(len(set(uids.values())), 3)
        reversed_text, _ = deadlines.calendar(self.plan(list(reversed(rows))), "UTC")
        self.assertEqual(uids, self.event_uids(reversed_text))
        # Captured from the base release for this ID-bearing row.
        legacy = "jobscura-a102f34ba980e5bc2c234a6f5d010804@jobscura.invalid"
        self.assertEqual(uids["Closes: Legacy - Example"], legacy)

    def test_identityless_calendar_rows_are_reported_as_skipped(self):
        rows = self.rows()
        rows.append({"employer": "Example", "title": "Unknown", "deadline": "2026-11-20"})
        tracker = self.save("tracker.json", rows)
        output = self.root / "deadlines.ics"
        run = self.cli("deadlines.py", "--tracker", tracker, "--timezone", "UTC",
                       "--as-of", "2026-11-04T12:00:00Z", "--ics", output)
        self.assertEqual(run.returncode, 0, run.stderr)
        calendar = json.loads(run.stdout)["calendar"]
        self.assertEqual(calendar["events"], 2)
        self.assertEqual(len(calendar["skipped"]), 1)
        skipped = calendar["skipped"][0]
        self.assertEqual((skipped["row"], skipped["employer"], skipped["title"]), (3, "Example", "Unknown"))
        self.assertIn("identity", skipped["reason"])
        self.assertEqual(len(self.event_uids(output.read_text(encoding="utf-8"))), 2)

    def test_malformed_url_skips_only_the_unidentified_row(self):
        rows = self.rows()
        rows[1]["url"] = "www.example.test/jobs/2"
        tracker = self.save("tracker.json", rows)
        output = self.root / "mixed.ics"
        run = self.cli("deadlines.py", "--tracker", tracker, "--timezone", "UTC",
                       "--as-of", "2026-11-04T12:00:00Z", "--ics", output)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)["calendar"]
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["skipped"], [{"row": 2, "employer": "Example", "title": "Designer",
                         "reason": "URL is not an absolute http(s) link; add a record ID or the full URL"}])
        self.assertEqual(len(self.event_uids(output.read_text(encoding="utf-8"))), 1)
        rows[1]["record_id"] = "JOB-2"
        text, count = deadlines.calendar(self.plan(rows), "UTC")
        self.assertEqual((count, len(self.event_uids(text))), (2, 2))

    def test_duplicate_calendar_uids_block_before_file_creation(self):
        rows = self.rows()
        rows.append(dict(rows[0]))
        tracker = self.save("tracker.json", rows)
        output = self.root / "duplicate.ics"
        run = self.cli("deadlines.py", "--tracker", tracker, "--timezone", "UTC",
                       "--as-of", "2026-11-04T12:00:00Z", "--ics", output)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stderr)["status"], "blocked")
        self.assertIn("duplicate calendar UID", json.loads(run.stderr)["error"])
        self.assertEqual(run.stdout, "")
        self.assertFalse(output.exists())

    def test_cliff_cannot_exceed_vesting_and_errors_name_the_offer(self):
        equity = {"type": "rsu", "grant_value": 48000, "vesting_years": 4, "cliff_months": 60}
        data = {"years": 5, "offers": [{"name": "Example offer", "base": 100000, "equity": equity}]}
        run = self.cli("offer_compare.py", "--offers", self.save("offers.json", data))
        self.assertEqual(run.returncode, 2, run.stdout)
        self.assertIn("Example offer", json.loads(run.stderr)["error"])
        equity["cliff_months"] = 48
        values, _ = offers.equity_by_year(equity, 5)
        self.assertEqual(values, [0.0, 0.0, 0.0, 48000.0, 0.0])
        equity["cliff_months"] = -1
        with self.assertRaisesRegex(common.ToolError, "Example offer"):
            offers.compare(data)
        equity["schedule_pct"] = [25, 25, 25, 25]
        for cliff in (-1, 60):
            equity["cliff_months"] = cliff
            with self.subTest(cliff=cliff), self.assertRaisesRegex(common.ToolError, "Example offer"):
                offers.compare(data)


if __name__ == "__main__":
    unittest.main()
