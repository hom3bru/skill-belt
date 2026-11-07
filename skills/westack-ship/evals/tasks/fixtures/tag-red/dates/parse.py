# dates-src-4a7
"""Parse day/month/year dates from the order export."""
from datetime import date


def parse_date(text):
    """'31/12/2024' or '31/12/24' -> date. Two-digit years are this century (ISSUE-77)."""
    day, month, year = (int(part) for part in text.strip().split("/"))
    if year < 100:
        year += 1900
    return date(year, month, day)
