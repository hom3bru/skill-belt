import legacy_gateway


def checkout(cart, token):
    total = sum(item["price_cents"] * item["qty"] for item in cart)
    payment_id = legacy_gateway.charge(total, "USD", token)
    return {"payment_id": payment_id, "total_cents": total}
