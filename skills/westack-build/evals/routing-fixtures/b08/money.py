SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def format_total(amount, currency="USD"):
    return "%s%.2f" % (SYMBOLS[currency], amount)
