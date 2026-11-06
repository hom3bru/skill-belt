# core-test-2c4
import unittest

from slugkit import slugify


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_accents_fold_to_ascii(self):
        self.assertEqual(slugify("Crème Brûlée"), "creme-brulee")

    def test_max_length_cuts_back_to_a_whole_word(self):
        self.assertEqual(slugify("Hello World Again", max_length=11), "hello-world")

    def test_max_length_shorter_than_the_first_word(self):
        self.assertEqual(slugify("Hello World", max_length=3), "hel")

    def test_no_max_length_keeps_everything(self):
        self.assertEqual(slugify("Hello World Again"), "hello-world-again")


if __name__ == "__main__":
    unittest.main()
