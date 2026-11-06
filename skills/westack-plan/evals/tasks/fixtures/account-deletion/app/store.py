# store-src-6f2
"""Users and their invoices, kept in memory (the production store has the same shape)."""
USERS = {}
INVOICES = []


def create_user(user_id, name, email, address):
    USERS[user_id] = {"name": name, "email": email, "address": address}


def add_invoice(user_id, total_cents):
    user = USERS[user_id]
    INVOICES.append({"user_id": user_id, "name": user["name"], "address": user["address"], "total": total_cents})


def invoices_for(user_id):
    return [invoice for invoice in INVOICES if invoice["user_id"] == user_id]
