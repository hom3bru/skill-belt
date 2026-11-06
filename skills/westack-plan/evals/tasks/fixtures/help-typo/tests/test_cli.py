import unittest

import cli


class UsageTests(unittest.TestCase):
    def test_no_file_prints_usage_and_exits_64(self):
        self.assertEqual(cli.main(["cli.py"]), 64)

    def test_usage_names_the_argument(self):
        self.assertIn("FILE", cli.USAGE)


if __name__ == "__main__":
    unittest.main()
