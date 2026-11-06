from .index import INDEX


def find(term):
    return sorted(INDEX.get(term.lower(), set()))
