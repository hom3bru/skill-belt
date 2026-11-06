import unittest

from pager import page_count, page_slice


class PagerTests(unittest.TestCase):
    def test_page_count_rounds_up(self):
        self.assertEqual(page_count(41, 20), 3)

    def test_page_past_end_is_empty(self):
        self.assertEqual(page_slice(list(range(10)), 5, 5), [])


if __name__ == "__main__":
    unittest.main()
