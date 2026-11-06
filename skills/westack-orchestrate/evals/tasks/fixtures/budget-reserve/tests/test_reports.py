# test-reports-8c2
import unittest

from src.reports import daily, monthly, weekly, yearly


class HeaderTests(unittest.TestCase):
    def test_each_header_names_its_period(self):
        for module in (daily, weekly, monthly, yearly):
            self.assertIn("Q3", module.header("Q3"))
