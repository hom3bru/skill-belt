from billing.core import balance


def customer_report(customer_id):
    return {"customer": customer_id, "balance": balance(customer_id)}
