# test-client-4c6
import unittest

import client


class BuildUrlTests(unittest.TestCase):
    def test_joins_base_and_path_with_one_slash(self):
        self.assertEqual(client.build_url("https://api.example/", "/v1/items"), "https://api.example/v1/items")

    def test_keeps_a_path_without_a_leading_slash(self):
        self.assertEqual(client.build_url("https://api.example", "v1/items"), "https://api.example/v1/items")
