# tdd-fixture: our own order store (in memory; the SQL store has the same interface)
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    order_id: str
    amount_cents: int
    charge_id: str
    status: str = "paid"


class InMemoryOrderStore:
    def __init__(self, orders=()):
        self._orders = {order.order_id: order for order in orders}

    def get(self, order_id):
        return self._orders[order_id]

    def save(self, order):
        self._orders[order.order_id] = order
