import unittest

from auth.passwords import validate_length


class PasswordTest(unittest.TestCase):
    def test_short_password_is_rejected(self):
        self.assertFalse(validate_length("abc"))

    def test_long_enough_password_is_accepted(self):
        self.assertTrue(validate_length("abcdefgh"))
