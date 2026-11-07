# export-scg-6c1
"""Write rows as CSV text for the finance download."""


def _field(value):
    text = str(value)
    if "," in text or '"' in text:
        return '"' + text + '"'
    return text


def to_csv(rows):
    """CSV text for a list of rows (lists of values), lines joined by CRLF."""
    return "\r\n".join(",".join(_field(value) for value in row) for row in rows)
