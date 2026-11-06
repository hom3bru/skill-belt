ENTRIES = []


def record(customer_id, cents, kind):
    ENTRIES.append({"customer": customer_id, "cents": cents, "kind": kind})


def balance(customer_id):
    return sum(e["cents"] for e in ENTRIES if e["customer"] == customer_id)
