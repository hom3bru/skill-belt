# billing-canary-5a1: proration (no tests yet; BILL-12)


def prorated_charge(monthly_price, days_used, days_in_month=30):
    """Charge for part of a month, rounded to cents."""
    if days_used <= 0:
        return 0.0
    share = days_used / days_in_month
    return round(monthly_price * share, 2)


def plan_change_credit(old_price, new_price, days_left, days_in_month=30):
    """What a customer is credited (negative: what they owe) when they switch plans with days_left in the month."""
    return round(prorated_charge(old_price, days_left, days_in_month)
                 - prorated_charge(new_price, days_left, days_in_month), 2)
