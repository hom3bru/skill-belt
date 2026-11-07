RATES = {"standard": 500, "express": 1500}


def shipping_cents(service, weight_kg):
    base = RATES[service]
    extra = max(0, weight_kg - 1) * 200
    return base + extra
