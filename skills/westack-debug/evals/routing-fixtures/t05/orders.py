ORDERS = [
    {"id": 1, "user_id": 7, "status": "completed", "placed_at": "2026-10-28", "total": 42.0},
    {"id": 2, "user_id": 7, "status": "pending", "placed_at": "2026-10-29", "total": 13.5},
    {"id": 3, "user_id": 9, "status": "completed", "placed_at": "2026-10-30", "total": 8.0},
]


def list_orders(user_id, status=None):
    return [o for o in ORDERS if o["user_id"] == user_id and (status is None or o["status"] == status)]
