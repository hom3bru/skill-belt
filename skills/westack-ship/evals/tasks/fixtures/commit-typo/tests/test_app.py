# app-test-7d1
import unittest

from app import domain_of


class DomainTests(unittest.TestCase):
    def test_domain_is_lower_case(self):
        self.assertEqual(domain_of("Ann@Example.COM"), "example.com")


if __name__ == "__main__":
    unittest.main()
