# query-src-6a3
"""Search over the catalogue: every word of the query must appear in the title."""

CATALOGUE = ["red wool scarf", "blue wool hat", "red rain jacket"]


def search(query, catalogue=CATALOGUE):
    words = query.lower().split()
    return [title for title in catalogue if all(word in title for word in words)]
