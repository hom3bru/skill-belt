# sessions-test-canary-6d2: the session tests CI-57 is about
import time
import unittest

from auth.sessions import Session


class SessionTests(unittest.TestCase):
    def test_new_session_is_active(self):
        self.assertFalse(Session("ada", ttl_seconds=0.05).is_expired())

    def test_session_expires_after_its_ttl(self):
        session = Session("ada", ttl_seconds=0.05)
        time.sleep(0.05)
        self.assertTrue(session.is_expired())

    def test_touch_keeps_a_session_alive(self):
        session = Session("ada", ttl_seconds=0.05)
        time.sleep(0.03)
        session.touch()
        time.sleep(0.03)
        self.assertFalse(session.is_expired())


if __name__ == "__main__":
    unittest.main()
