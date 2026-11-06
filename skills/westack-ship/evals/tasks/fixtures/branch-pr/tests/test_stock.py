# stock-test-3e5
import unittest

from inventory.stock import Item, low_stock


class LowStockTests(unittest.TestCase):
    def test_empty_shelf_is_low(self):
        self.assertEqual(low_stock([Item("a", 0), Item("b", 40)]), [Item("a", 0)])

    def test_full_shelves_are_not_low(self):
        self.assertEqual(low_stock([Item("a", 20), Item("b", 40)]), [])


if __name__ == "__main__":
    unittest.main()
