def price_for(sku):
    return {"sku": sku, "cents": 1999, "currency": "USD"}


def format_price(cents):
    return "$%d.%02d" % divmod(cents, 100)
