import unittest

from slugify import slugify


class SlugifyTests(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(slugify("Hello"), "hello")

    def test_punctuation_removed(self):
        self.assertEqual(slugify("rock&roll"), "rock-roll")

    def test_trims_edges(self):
        self.assertEqual(slugify("  padded  "), "padded")


if __name__ == "__main__":
    unittest.main()
