# invoice-utw-8e1
"""Invoice due dates."""
from datetime import timedelta


def due_date(issued, terms_days=30):
    """The date payment is due: issued plus the terms; a due date on a weekend moves to the next Monday."""
    due = issued + timedelta(days=terms_days)
    if due.weekday() >= 5:  # Saturday or Sunday
        due += timedelta(days=2)
    return due
