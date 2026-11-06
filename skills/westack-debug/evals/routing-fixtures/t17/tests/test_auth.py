import unittest

from auth import is_expired


class AuthTest(unittest.TestCase):
    def test_token_is_expired_at_exactly_its_ttl(self):
        self.assertTrue(is_expired(100, 60, now=160))

    def test_fresh_token_is_not_expired(self):
        self.assertFalse(is_expired(100, 60, now=120))
