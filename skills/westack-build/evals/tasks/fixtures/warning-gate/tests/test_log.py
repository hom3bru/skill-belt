# existing-test-log-2d9
import unittest

from audit.log import record


class RecordTests(unittest.TestCase):
    def test_record_keeps_action_and_user(self):
        entry = record("refund", "ada")
        self.assertEqual((entry["action"], entry["user"]), ("refund", "ada"))


if __name__ == "__main__":
    unittest.main()
