import unittest

from listctl import select


class SelectTest(unittest.TestCase):
    def test_archived_only(self):
        self.assertEqual([i["name"] for i in select(True)], ["beta"])
