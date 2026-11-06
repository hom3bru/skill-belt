RATES = {"basic": 1000, "plus": 2500, "team": 9000}


def invoice_total(plan, seats, months, coupon=None):
    base = RATES[plan] * seats * months
    if months >= 12:
        base = base * 9 // 10
    if plan == "team" and seats > 20:
        base -= 500 * (seats - 20) * months
    if coupon == "WELCOME10":
        base = base * 9 // 10
    elif coupon == "HALF":
        base = base // 2
    tax = base * 8 // 100
    return {"net": base, "tax": tax, "gross": base + tax}


def proration(plan, seats, days_left, days_in_month):
    daily = RATES[plan] * seats // days_in_month
    return daily * days_left
