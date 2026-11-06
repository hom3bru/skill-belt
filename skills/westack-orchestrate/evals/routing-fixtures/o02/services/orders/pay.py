from billing.api import charge


def pay_for_order(order):
    return charge(order["customer"], order["cents"])
