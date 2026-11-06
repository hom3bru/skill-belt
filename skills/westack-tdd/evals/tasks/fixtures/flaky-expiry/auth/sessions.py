# session-store-canary-3b8: login sessions (the expiry rule is correct; see CI-57)
import time


class Session:
    def __init__(self, user, ttl_seconds=900):
        self.user = user
        self.ttl_seconds = ttl_seconds
        self.last_seen = time.monotonic()

    def touch(self):
        self.last_seen = time.monotonic()

    def is_expired(self):
        return time.monotonic() - self.last_seen >= self.ttl_seconds
