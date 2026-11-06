import time


def is_expired(issued_at, ttl, now=None):
    now = time.time() if now is None else now
    return now - issued_at > ttl
