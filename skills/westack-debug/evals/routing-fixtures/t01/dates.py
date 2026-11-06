from datetime import date


def parse_date(text):
    day, month, year = (int(part) for part in text.split("/"))
    if year < 100:
        year += 1900
    return date(year, month, day)
