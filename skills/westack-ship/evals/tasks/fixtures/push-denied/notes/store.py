# notes-src-8d1
"""An in-memory note store."""


class Store:
    def __init__(self):
        self.notes = []

    def add(self, title, body=""):
        self.notes.append((title, body))

    def search(self, text):
        word = text.lower()
        return [title for title, _ in self.notes if word in title.lower().split()]
