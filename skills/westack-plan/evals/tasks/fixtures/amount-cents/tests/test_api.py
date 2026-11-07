# test-api-9d4
import json
import unittest

from shop.api import order_payload, orders_json
from shop.models import Order


class OrderPayloadTests(unittest.TestCase):
    def test_amount_is_in_euros(self):
        self.assertEqual(order_payload(Order(7, 12.5))["amount"], 12.5)

    def test_orders_json_lists_every_order(self):
        body = json.loads(orders_json([Order(1, 3.0), Order(2, 4.25)]))
        self.assertEqual([o["id"] for o in body], [1, 2])


if __name__ == "__main__":
    unittest.main()
