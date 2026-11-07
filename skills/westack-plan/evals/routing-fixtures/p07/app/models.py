def get_order(conn, order_id):
    return conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()


def items_for(conn, order_id):
    return conn.execute("SELECT * FROM order_items WHERE order_id = %s", (order_id,)).fetchall()
