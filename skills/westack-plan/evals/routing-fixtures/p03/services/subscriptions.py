from billing.core import charge_customer, refund_customer


def renew(customer_id, cents):
    return charge_customer(customer_id, cents)


def cancel(customer_id, cents):
    return refund_customer(customer_id, cents)
