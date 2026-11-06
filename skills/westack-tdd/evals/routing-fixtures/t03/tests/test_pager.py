import unittest

from pager import paginate


class PaginateTest(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(paginate(list(range(25)), 1), list(range(10)))
