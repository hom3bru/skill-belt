# billing/trial.py - free-trial arithmetic
from datetime import date, timedelta

TRIAL_DAYS = 14


def trial_end(signup):
    """The calendar day the trial ends, for a timezone-aware signup time."""
    return (signup + timedelta(days=TRIAL_DAYS)).date()


def days_left(signup, today=None):
    """Whole days from today until the trial ends."""
    today = today or date.today()
    return (trial_end(signup) - today).days
