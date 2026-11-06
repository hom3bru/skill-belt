# tdd-fixture: existing tests
import unittest

from accounts.signup import EmailTaken, register


class NullMailer:
    def send(self, to, subject, body):
        pass


class RegisterTests(unittest.TestCase):
    def test_stores_the_normalised_address(self):
        store = {}
        register(store, NullMailer(), "  Bo@Example.org ", "Bo")
        self.assertEqual(list(store), ["bo@example.org"])

    def test_refuses_a_taken_address(self):
        store = {"bo@example.org": {"name": "Bo"}}
        with self.assertRaises(EmailTaken):
            register(store, NullMailer(), "BO@example.org", "Another Bo")


if __name__ == "__main__":
    unittest.main()
