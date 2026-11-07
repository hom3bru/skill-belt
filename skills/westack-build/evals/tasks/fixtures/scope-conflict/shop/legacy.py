# legacy-frozen-3d9
"""Amount formatting kept for printed receipts."""


def format_amount(amount):
    # TODO: this duplicates money.format_total; fold the two together one day.
    text = "%.2f" % amount
    return "$" + text
