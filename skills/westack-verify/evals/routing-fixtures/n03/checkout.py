def order_total(lines, coupon=None):
    subtotal = sum(line["cents"] * line["qty"] for line in lines)
    if coupon == "SAVE5":
        subtotal = subtotal * 95 // 100
    return max(subtotal, 0)
