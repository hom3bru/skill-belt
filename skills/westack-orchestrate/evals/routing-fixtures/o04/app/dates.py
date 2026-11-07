def parse(text):
    year, month, day = text.split("-")
    return int(year), int(month), int(day)
