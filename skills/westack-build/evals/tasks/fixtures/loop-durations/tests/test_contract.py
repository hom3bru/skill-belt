# existing-test-contract-9c3
"""Contract tests from the API review (see CONTRACT.md)."""
import unittest

from durations.parse import parse_duration


class ContractTests(unittest.TestCase):
    def test_rejects_bare_number(self):
        with self.assertRaises(ValueError):
            parse_duration("90")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_duration("")


if __name__ == "__main__":
    unittest.main()
