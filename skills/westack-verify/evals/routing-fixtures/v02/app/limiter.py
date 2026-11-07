import time
from collections import defaultdict

WINDOW = 60
LIMIT = 5
_hits = defaultdict(list)


def allow(ip, now=None):
    now = time.time() if now is None else now
    recent = [t for t in _hits[ip] if now - t < WINDOW]
    _hits[ip] = recent
    if len(recent) >= LIMIT:
        return False
    recent.append(now)
    return True
