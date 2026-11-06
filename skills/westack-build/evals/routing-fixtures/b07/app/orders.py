def archive_order(conn, order_id):
    conn.execute("UPDATE orders SET is_archived = 1 WHERE id = ?", (order_id,))
    conn.commit()


def open_orders(conn):
    return conn.execute("SELECT id, total_cents FROM orders WHERE status = 'open'").fetchall()
