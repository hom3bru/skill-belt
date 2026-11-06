from .clients import get


def load_order(order_id):
    return get("/orders/%d" % order_id)
