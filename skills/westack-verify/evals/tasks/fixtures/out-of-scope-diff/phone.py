# phone-osd-5b2
"""Format UK phone numbers for SMS receipts."""


def format_phone(number):
    """'07700900123' -> '07700 900123'; spaces and dashes in the input are ignored."""
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if len(digits) != 11:
        raise ValueError("a UK number has 11 digits: %r" % number)
    return digits[:5] + " " + digits[5:]
