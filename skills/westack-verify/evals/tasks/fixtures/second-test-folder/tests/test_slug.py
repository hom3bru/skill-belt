# test-stf-2f9
import unittest

from slugs import slugify


class SlugTests(unittest.TestCase):
    def test_words_are_joined_by_hyphens(self):
        self.assertEqual(slugify("Hello, World"), "hello-world")

    def test_digits_are_kept(self):
        self.assertEqual(slugify("Top 10 tips"), "top-10-tips")

    def test_long_titles_are_capped_at_40(self):
        slug = slugify("A very long title about the many ways to cut a slug short")
        self.assertLessEqual(len(slug), 40)

    def test_a_capped_slug_never_ends_with_a_hyphen(self):
        self.assertFalse(slugify("x" * 39 + " and more").endswith("-"))
