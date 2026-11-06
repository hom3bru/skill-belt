def export(notes, since=None):
    return [n for n in notes if since is None or n["created"] >= since]
