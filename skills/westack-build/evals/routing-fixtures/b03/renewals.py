from checkout import checkout


def renew(subscription):
    cart = [{"price_cents": subscription["price_cents"], "qty": 1}]
    return checkout(cart, subscription["token"])
