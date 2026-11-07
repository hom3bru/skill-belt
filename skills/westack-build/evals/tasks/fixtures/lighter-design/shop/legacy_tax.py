"""Sales tax. Owned by the finance team (FIN-4); not part of SHOP-9. legacy-tax-canary-9e1"""

# TODO: this repeats the rounding in pricing.py; fold the two together some day.


def tax(amount):
    return round(amount * 0.2, 2)
