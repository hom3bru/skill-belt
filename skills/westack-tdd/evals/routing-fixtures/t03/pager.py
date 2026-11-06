def paginate(items, page, size=10):
    start = 0 if page == 1 else (page - 1) * size + 1
    return items[start:start + size]
