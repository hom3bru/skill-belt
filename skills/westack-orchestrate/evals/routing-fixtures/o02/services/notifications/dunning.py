from billing.api import balance


def overdue(users):
    return [u for u in users if balance(u["id"]) > 0]
