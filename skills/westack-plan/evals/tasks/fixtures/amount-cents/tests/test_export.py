# test-export-3e8
import json
import pathlib
import tempfile
import unittest

from jobs.nightly_export import main


class NightlyExportTests(unittest.TestCase):
    def test_writes_euro_amounts_with_two_decimals(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = pathlib.Path(folder, "orders.json"), pathlib.Path(folder, "orders.csv")
            source.write_text(json.dumps([{"id": 7, "amount": 12.5, "currency": "EUR"}]), encoding="utf-8")
            main(source, target)
            self.assertEqual(target.read_text(encoding="utf-8").splitlines()[1], "7,12.50,EUR")


if __name__ == "__main__":
    unittest.main()
