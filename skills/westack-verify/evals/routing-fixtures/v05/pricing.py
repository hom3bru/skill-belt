TIERS = [(100, 80), (10, 90)]


def price(item, qty):
    unit = item["unit_cents"]
    for minimum, percent in TIERS:
        if qty >= minimum:
            return unit * percent // 100 * qty
    return unit * qty


def cart_total(items):
    return sum(price(i, i["qty"]) for i in items)
