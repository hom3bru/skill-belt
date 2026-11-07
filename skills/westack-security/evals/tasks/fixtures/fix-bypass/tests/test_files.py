# fxb-test-7w4
import unittest

from app.files import download


class DownloadTests(unittest.TestCase):
    def test_reads_an_upload(self):
        self.assertIn("quarterly report", download("report.txt"))

    def test_sec14_parent_step_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            download("../secret.txt")


if __name__ == "__main__":
    unittest.main()
