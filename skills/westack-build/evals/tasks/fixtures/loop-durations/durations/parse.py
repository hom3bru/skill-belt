"""Parse durations such as '90s', '45m', '2h' or '1h30m' into seconds."""
import re

UNITS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text):
    text = text.strip()
    if text.isdigit():
        return int(text)
    match = re.fullmatch(r"(\d+)([hms])", text)
    if not match:
        raise ValueError("not a duration: %r" % text)
    return int(match.group(1)) * UNITS[match.group(2)]
