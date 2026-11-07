import time

from .gateway import post


def charge(card_token, amount_cents, idempotency_key=None):
    payload = {"token": card_token, "amount": amount_cents}
    if idempotency_key:
        payload["key"] = idempotency_key
    for attempt in range(3):
        result = post("/charges", payload)
        if result.get("status") == "ok":
            return result["id"]
        time.sleep(attempt + 1)
    return None
