import unittest

from app import issue


class AuthTest(unittest.TestCase):
    def test_issue(self):
        self.assertEqual(issue("ada"), "tok-ada")
