def charge_total(lines, tax_percent=8):
    net = sum(line["cents"] * line["qty"] for line in lines)
    return net + net * tax_percent // 100
