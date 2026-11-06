import unittest

from notes.cli import export


class ExportTest(unittest.TestCase):
    def test_since_filters_older_notes(self):
        notes = [{"created": "2026-10-01"}, {"created": "2026-10-20"}]
        self.assertEqual(export(notes, since="2026-10-10"), [{"created": "2026-10-20"}])
