import time
import unittest

from ttl_cache import TTLCache


class TTLCacheTest(unittest.TestCase):
    def test_entry_lives_for_its_ttl_then_expires(self):
        cache = TTLCache(ttl=0.05)
        cache.set("a", 1)
        time.sleep(0.04)
        self.assertEqual(cache.get("a"), 1)
        time.sleep(0.02)
        self.assertIsNone(cache.get("a"))
