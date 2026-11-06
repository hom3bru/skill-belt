def all_orders():
    return [{"id": n, "total": n * 5} for n in range(1, 101)]
