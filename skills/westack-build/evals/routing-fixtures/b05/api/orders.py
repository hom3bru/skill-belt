from flask import Blueprint, jsonify, request

from db import all_orders

bp = Blueprint("orders", __name__)

DEFAULT_PAGE_SIZE = 20


def paginate(items, page, size):
    start = (page - 1) * size
    return items[start:start + size]


@bp.get("/api/orders")
def list_orders():
    orders = all_orders()
    return jsonify({"orders": orders})
