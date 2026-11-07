from . import ledger


def charge(customer_id, cents):
    ledger.record(customer_id, cents, "charge")
    return {"customer": customer_id, "cents": cents}
