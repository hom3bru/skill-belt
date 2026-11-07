class Cart:
    def __init__(self):
        self.lines = []

    def add(self, name, price_cents, qty=1):
        self.lines.append({"name": name, "price_cents": price_cents, "qty": qty})

    def subtotal_cents(self):
        return sum(l["price_cents"] * l["qty"] for l in self.lines)
