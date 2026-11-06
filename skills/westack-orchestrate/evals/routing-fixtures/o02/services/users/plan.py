from billing.api import balance


def can_upgrade(user):
    return balance(user["id"]) == 0
