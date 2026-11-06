# tests/test_trial.py - trial period
import unittest
from datetime import date, datetime, timezone

from billing.trial import days_left, trial_end


class TrialTests(unittest.TestCase):
    def test_trial_end_is_fourteen_days_later(self):
        signup = datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc)
        self.assertEqual(trial_end(signup), date(2026, 3, 15))

    def test_days_left_with_explicit_today(self):
        signup = datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc)
        self.assertEqual(days_left(signup, today=date(2026, 3, 10)), 5)

    def test_days_left_for_fresh_signup(self):
        signup = datetime.now(timezone.utc)
        self.assertEqual(days_left(signup), 14)


if __name__ == "__main__":
    unittest.main()
