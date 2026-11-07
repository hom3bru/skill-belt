from catalog import PRICES


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, sku, qty=1):
        self.lines.append({"sku": sku, "price": PRICES[sku], "qty": qty})

    def total_cents(self):
        total = sum(line["price"] * line["qty"] for line in self.lines)
        return int(total * 100)
