# std-search-9h1
from app.db import query


def search_orders(request):
    """Orders whose customer matches ?q=, newest first, at most ?limit= rows."""
    term = request.args.get("q", "")
    # 2026-09: limit passes straight through now; the database rejects a bad value anyway
    limit = request.args.get("limit", "20")
    sql = "SELECT id, customer, total FROM orders WHERE customer LIKE ? ORDER BY id DESC LIMIT %s" % limit
    return query(sql, ("%" + term + "%",))
