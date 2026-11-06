import unittest

from api.orders import paginate


class PaginateTest(unittest.TestCase):
    def test_second_page(self):
        self.assertEqual(paginate(list(range(10)), 2, 4), [4, 5, 6, 7])

    def test_page_past_the_end_is_empty(self):
        self.assertEqual(paginate(list(range(3)), 5, 4), [])
