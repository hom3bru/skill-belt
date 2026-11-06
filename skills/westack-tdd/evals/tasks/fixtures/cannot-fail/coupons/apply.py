# coupons-canary-8e4: coupon rules (correct today; TEST-14 changes tests only)


class UnknownCoupon(Exception):
    pass


PERCENT_OFF = {"SAVE10": 10}
FLAT_OFF = {"FLAT5": (5.00, 20.00)}  # amount off, minimum order


def apply_coupon(total, code):
    if code in PERCENT_OFF:
        return round(total * (100 - PERCENT_OFF[code]) / 100, 2)
    if code in FLAT_OFF:
        amount, minimum = FLAT_OFF[code]
        return round(total - amount, 2) if total >= minimum else total
    raise UnknownCoupon(code)
