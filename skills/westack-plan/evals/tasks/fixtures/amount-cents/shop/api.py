# api-src-1a7
"""The orders endpoint body. GET /orders returns orders_json(all_orders())."""
import json


def order_payload(order):
    return {"id": order.id, "amount": order.total_euros, "currency": order.currency}


def orders_json(orders):
    return json.dumps([order_payload(o) for o in orders])
