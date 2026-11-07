# test-cli-2b9
import unittest

import cli


class CliTests(unittest.TestCase):
    def test_export_runs(self):
        self.assertEqual(cli.main(["export", "a.csv"]), 0)

    def test_no_arguments_prints_usage(self):
        self.assertEqual(cli.main([]), 2)


if __name__ == "__main__":
    unittest.main()
