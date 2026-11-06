INDEX = {}


def add(doc_id, text):
    for word in text.lower().split():
        INDEX.setdefault(word, set()).add(doc_id)
