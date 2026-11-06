def paginate(items, page, size=25, keep_tail=False):
    start = (page - 1) * size
    chunk = items[start:start + size]
    if keep_tail and not chunk and items:
        return items[-size:]
    return chunk
