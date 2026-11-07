def refund(customer_id, cents):
    return {"customer": customer_id, "cents": -cents, "kind": "refund"}
