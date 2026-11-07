import time


class TTLCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self._items = {}

    def set(self, key, value):
        self._items[key] = (value, time.monotonic() + self.ttl)

    def get(self, key):
        item = self._items.get(key)
        if item is None:
            return None
        value, expires = item
        if time.monotonic() >= expires:
            del self._items[key]
            return None
        return value
