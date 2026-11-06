# test-settings-5b8
import unittest

import settings


class LoadTests(unittest.TestCase):
    def test_an_explicit_timeout_wins(self):
        self.assertEqual(settings.load({"FETCHR_TIMEOUT": "7"}).timeout, 7.0)

    def test_retries_default(self):
        self.assertEqual(settings.load({}).retries, settings.DEFAULT_RETRIES)

    def test_format_defaults_to_json(self):
        self.assertEqual(settings.load({}).output_format, "json")

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(ValueError):
            settings.load({"FETCHR_FORMAT": "xml"})
