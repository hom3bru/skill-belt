def charge(amount_cents, currency, token):
    return "pay_%s_%d" % (token[-4:], amount_cents)


def refund(payment_id, amount_cents):
    return None
