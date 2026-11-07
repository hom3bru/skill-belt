import unittest

from upload import check_size


class CheckSizeTests(unittest.TestCase):
    def test_a_small_file_passes(self):
        self.assertEqual(check_size(b"abc"), 3)


if __name__ == "__main__":
    unittest.main()
