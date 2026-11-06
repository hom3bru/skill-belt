# totals-src-5b1
"""Monthly totals per account, in cents."""


def totals_per_account(payments):
    totals = {}
    for account, cents in payments:
        totals[account] = totals.get(account, 0) + cents
    return dict(sorted(totals.items()))
