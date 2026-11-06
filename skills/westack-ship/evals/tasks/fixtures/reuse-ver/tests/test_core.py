# export-test-9f3
import csv
import json
import pathlib
import tempfile
import unittest

from exporter.core import export_csv, export_json

ROWS = [{"id": 1, "name": "ada"}, {"id": 2, "name": "bo"}]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = pathlib.Path(self.temp.name)

    def test_json_round_trips(self):
        export_json(ROWS, self.dir / "r.json")
        self.assertEqual(json.loads((self.dir / "r.json").read_text(encoding="utf-8")), ROWS)

    def test_csv_has_a_header_and_one_line_per_row(self):
        export_csv(ROWS, self.dir / "r.csv")
        with open(self.dir / "r.csv", encoding="utf-8", newline="") as stream:
            self.assertEqual(list(csv.reader(stream)), [["id", "name"], ["1", "ada"], ["2", "bo"]])

    def test_csv_of_no_rows_is_empty(self):
        export_csv([], self.dir / "e.csv")
        self.assertEqual((self.dir / "e.csv").read_text(encoding="utf-8").strip(), "")


if __name__ == "__main__":
    unittest.main()
