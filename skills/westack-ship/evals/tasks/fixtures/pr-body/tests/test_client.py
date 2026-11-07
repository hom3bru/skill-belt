import io
import unittest
import urllib.error

from app.client import fetch


def opener_for(*answers):
    """An opener that gives each answer in turn: bytes for a body, an int for an HTTP error."""
    calls = []

    def opener(url, timeout):
        calls.append(url)
        answer = answers[len(calls) - 1]
        if isinstance(answer, int):
            raise urllib.error.HTTPError(url, answer, "error", {}, None)
        return io.BytesIO(answer)
    opener.calls = calls
    return opener


class FetchTests(unittest.TestCase):
    def test_returns_the_body_as_text(self):
        self.assertEqual(fetch("http://billing/x", opener_for(b"ok")), "ok")

    def test_a_404_is_raised(self):
        with self.assertRaises(urllib.error.HTTPError):
            fetch("http://billing/x", opener_for(404))


if __name__ == "__main__":
    unittest.main()
