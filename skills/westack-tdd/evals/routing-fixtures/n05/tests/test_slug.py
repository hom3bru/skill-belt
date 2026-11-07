import unittest

from slug import slugify


class SlugTest(unittest.TestCase):
    def test_spaces_become_hyphens(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_punctuation_is_stripped(self):
        self.assertEqual(slugify("Hi, there!"), "hi-there")
