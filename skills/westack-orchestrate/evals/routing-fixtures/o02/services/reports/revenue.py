from billing.api import balance


def revenue_line(user):
    return {"user": user["id"], "balance": balance(user["id"])}
