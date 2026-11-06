# tdd-fixture: shipping fees
RATE_PER_KG = 1.5


def base_fee(weight_kg):
    return round(weight_kg * RATE_PER_KG, 2)


def shipping_fee(weight_kg, express=False):
    fee = base_fee(weight_kg)
    return fee
