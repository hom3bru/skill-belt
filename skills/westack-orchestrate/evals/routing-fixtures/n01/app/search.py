def matches(term, text):
    return term.lower() in text.lower().split()
