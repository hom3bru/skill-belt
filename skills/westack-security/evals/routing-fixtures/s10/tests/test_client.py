import unittest
from unittest import mock

from weather import client

API_KEY = "wx_fixture_9d41c27a05be"  # FIXTURE, not a real key


class ForecastTests(unittest.TestCase):
    def test_the_key_is_sent(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
            client.forecast("London", key=API_KEY)
        self.assertIn("key=" + API_KEY, urlopen.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
