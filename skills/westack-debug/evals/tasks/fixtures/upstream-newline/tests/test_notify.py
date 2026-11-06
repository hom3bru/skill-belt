# tests/test_notify.py - notice addresses
import unittest

import notify


class NotifyTests(unittest.TestCase):
    def test_address_for_a_known_person(self):
        self.assertEqual(notify.address_for("Ana"), "ana@example.com")

    def test_an_unknown_person_raises(self):
        with self.assertRaises(KeyError):
            notify.address_for("Zed")


if __name__ == "__main__":
    unittest.main()
