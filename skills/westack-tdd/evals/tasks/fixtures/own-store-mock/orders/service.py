# tdd-fixture: order service
from dataclasses import replace


class NotRefundable(Exception):
    pass


class OrderService:
    def __init__(self, store, gateway):
        self.store = store
        self.gateway = gateway

    def mark_shipped(self, order_id):
        order = self.store.get(order_id)
        self.store.save(replace(order, status="shipped"))
