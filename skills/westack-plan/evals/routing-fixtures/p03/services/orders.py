from billing.core import charge_customer


def place_order(customer_id, cents):
    return charge_customer(customer_id, cents)
