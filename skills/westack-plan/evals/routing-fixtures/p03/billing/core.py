def charge_customer(customer_id, cents):
    return {"customer": customer_id, "cents": cents, "ok": True}


def refund_customer(customer_id, cents):
    return {"customer": customer_id, "cents": -cents, "ok": True}


def balance(customer_id):
    return 0
