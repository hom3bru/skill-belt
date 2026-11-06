# tests/test_slug.py - slug tests
import unittest

from textkit.slug import slugify


class SlugTests(unittest.TestCase):
    def test_lowercase_words(self):
        self.assertEqual(slugify("make it so"), "make-it-so")

    def test_capitals_and_punctuation(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_digits(self):
        self.assertEqual(slugify("route 66"), "route-66")


if __name__ == "__main__":
    unittest.main()
