from billing.core import balance


def outstanding(customer_id):
    return balance(customer_id)
