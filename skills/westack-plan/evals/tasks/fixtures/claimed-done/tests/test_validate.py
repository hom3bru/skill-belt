# test-validate-5e7
import unittest

from importer.validate import valid_email


class ValidEmailTests(unittest.TestCase):
    def test_accepts_an_ordinary_address(self):
        self.assertTrue(valid_email("ada@example.com"))

    def test_rejects_a_missing_at(self):
        self.assertFalse(valid_email("ada.example.com"))

    def test_rejects_a_domain_without_a_dot(self):
        self.assertFalse(valid_email("user@localhost"))


if __name__ == "__main__":
    unittest.main()
