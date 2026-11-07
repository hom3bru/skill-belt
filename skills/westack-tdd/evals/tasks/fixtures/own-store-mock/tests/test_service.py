# tdd-fixture: existing tests (house style)
import unittest
from unittest.mock import MagicMock

from orders.service import OrderService
from orders.store import Order


class OrderServiceTests(unittest.TestCase):
    def test_mark_shipped_saves_the_order(self):
        store = MagicMock()
        store.get.return_value = Order("o-7", 1200, "ch_3")
        service = OrderService(store, MagicMock())
        service.mark_shipped("o-7")
        store.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
