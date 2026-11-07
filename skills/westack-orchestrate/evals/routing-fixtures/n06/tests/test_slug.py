import unittest

from src.slug import make


class SlugTest(unittest.TestCase):
    def test_make(self):
        self.assertEqual(make("Hello, World!"), "hello-world")
