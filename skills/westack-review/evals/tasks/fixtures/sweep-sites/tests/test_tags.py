# swp-test-4w8
import unittest

from app.tags import add_tag


class TagTests(unittest.TestCase):
    def test_a_tag_is_added_once(self):
        self.assertEqual(add_tag("x", ["x"]), ["x"])


if __name__ == "__main__":
    unittest.main()
