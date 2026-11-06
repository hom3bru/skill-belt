# tests/test_audit.py - settings read from another file (olk-aud-6b9)
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import settings


class AuditTests(unittest.TestCase):
    def test_reads_a_given_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            path.write_text(json.dumps({"currency": "GBP", "decimals": 2}), encoding="utf-8")
            with mock.patch.object(settings, "_cache", None), mock.patch.object(settings, "_PATH", path):
                self.assertEqual(settings.load()["currency"], "GBP")


if __name__ == "__main__":
    unittest.main()
