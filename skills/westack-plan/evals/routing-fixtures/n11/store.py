import sqlite3


def save_rows(conn, rows):
    with conn:
        for row in rows:
            conn.execute("INSERT INTO customers (email, name) VALUES (?, ?)", (row["email"], row.get("name", "")))
