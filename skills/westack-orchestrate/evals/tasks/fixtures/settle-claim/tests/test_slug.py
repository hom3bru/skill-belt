# test-slug-6c1
import unittest

from src.slug import slugify


class SlugTests(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(slugify("Hello"), "hello")

    def test_spaces_become_hyphens(self):
        self.assertEqual(slugify("hello world"), "hello-world")

    def test_strips_edges(self):
        self.assertEqual(slugify(" Hi! "), "hi")
