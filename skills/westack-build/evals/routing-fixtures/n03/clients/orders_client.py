import requests

BASE = "http://orders.internal:8000"


def get_order(order_id):
    return requests.get("%s/orders/%d" % (BASE, order_id), timeout=3).json()


def create_order(payload):
    return requests.post(BASE + "/orders", json=payload, timeout=3).json()
