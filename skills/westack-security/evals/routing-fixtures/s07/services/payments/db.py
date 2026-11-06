import sqlite3

DB = "payments.db"
FIELDS = ("id", "user_id", "amount", "currency", "status")


def _conn():
    return sqlite3.connect(DB)


def create(user_id, amount, currency, card_token):
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO payments (user_id, amount, currency, card_token, status) VALUES (?, ?, ?, ?, 'paid')",
            (user_id, amount, currency, card_token))
        return {"id": cursor.lastrowid, "amount": amount, "currency": currency, "status": "paid"}


def get(payment_id):
    row = _conn().execute("SELECT id, user_id, amount, currency, status FROM payments WHERE id = ?",
                          (payment_id,)).fetchone()
    return dict(zip(FIELDS, row)) if row else {}


def refund(payment_id, amount):
    with _conn() as conn:
        conn.execute("UPDATE payments SET status = 'refunded', refunded = ? WHERE id = ?", (amount, payment_id))
    return {"id": payment_id, "status": "refunded", "refunded": amount}
