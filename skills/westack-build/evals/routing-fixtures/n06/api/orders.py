from flask import Blueprint, jsonify, request

from db import all_orders

bp = Blueprint("orders", __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def paginate(items, page, size):
    start = (page - 1) * size
    return items[start:start + size]


@bp.get("/api/orders")
def list_orders():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", DEFAULT_PAGE_SIZE, type=int)
    if size > MAX_PAGE_SIZE:
        return jsonify({"error": "size too large"}), 400
    return jsonify({"orders": paginate(all_orders(), page, size), "page": page, "size": size})
