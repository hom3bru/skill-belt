# tdd-fixture: existing tests of the behaviour the settings drive
import os
import tempfile
import unittest

from app.client import fetch
from app.settings import load


class RecordingOpener:
    def __init__(self, failures=0):
        self.failures, self.calls = failures, []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        if len(self.calls) <= self.failures:
            raise OSError("connection reset")
        return "body of " + url


class FetchTests(unittest.TestCase):
    def test_passes_the_configured_timeout_to_the_opener(self):
        opener = RecordingOpener()
        fetch("https://a.example", opener, {"http": {"timeout_seconds": 7, "retries": 0}})
        self.assertEqual(opener.calls, [("https://a.example", 7)])

    def test_retries_then_gives_up(self):
        opener = RecordingOpener(failures=5)
        with self.assertRaises(OSError):
            fetch("https://a.example", opener, {"http": {"timeout_seconds": 3, "retries": 2}})
        self.assertEqual(len(opener.calls), 3)


class LoadTests(unittest.TestCase):
    def write(self, text):
        handle, path = tempfile.mkstemp(suffix=".toml")
        os.close(handle)
        self.addCleanup(os.remove, path)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)
        return path

    def test_rejects_a_zero_timeout(self):
        with self.assertRaises(ValueError):
            load(self.write("[http]\ntimeout_seconds = 0\nretries = 1\n"))

    def test_reads_a_valid_file(self):
        data = load(self.write("[http]\ntimeout_seconds = 4\nretries = 1\n"))
        self.assertEqual(data["http"], {"timeout_seconds": 4, "retries": 1})


if __name__ == "__main__":
    unittest.main()
