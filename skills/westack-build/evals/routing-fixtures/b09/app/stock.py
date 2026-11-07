def reserve(stock, sku, qty):
    if stock.get(sku, 0) < qty:
        raise ValueError("insufficient stock for %s" % sku)
    stock[sku] -= qty
    return stock[sku]
