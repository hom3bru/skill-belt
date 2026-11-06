import unittest

from app import limiter


class LimiterTest(unittest.TestCase):
    def test_sixth_attempt_is_refused(self):
        results = [limiter.allow("10.0.0.1", now=1000 + i) for i in range(6)]
        self.assertEqual(results, [True] * 5 + [False])
