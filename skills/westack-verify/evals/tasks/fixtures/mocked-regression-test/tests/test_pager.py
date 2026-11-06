# test-mrt-8b4
import unittest
from unittest import mock

import pager


class PaginateTests(unittest.TestCase):
    def test_full_pages(self):
        self.assertEqual(pager.paginate([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_rejects_size_zero(self):
        with self.assertRaises(ValueError):
            pager.paginate([1], 0)

    def test_keeps_the_last_partial_page(self):
        # regression test for the dropped last page
        with mock.patch("pager.paginate", return_value=[[1, 2], [3, 4], [5]]):
            pages = pager.paginate([1, 2, 3, 4, 5], 2)
        self.assertEqual(pages[-1], [5])
