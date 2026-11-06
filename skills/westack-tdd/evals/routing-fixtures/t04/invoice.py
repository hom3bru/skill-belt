TAX_PERCENT = 8


def line_total(price_cents, qty):
    return price_cents * qty


def invoice_total(lines, discount_percent=0):
    subtotal = sum(line_total(l["price_cents"], l["qty"]) for l in lines)
    discounted = subtotal - subtotal * discount_percent // 100
    return discounted + discounted * TAX_PERCENT // 100


def format_invoice(lines):
    rows = ["%-10s x%d" % (l["name"], l["qty"]) for l in lines]
    return "\n".join(rows + ["TOTAL %d" % invoice_total(lines)])
