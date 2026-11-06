def payout_total(orders):
    return sum(order["cents"] for order in orders)
