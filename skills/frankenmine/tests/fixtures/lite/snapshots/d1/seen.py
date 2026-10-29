def remember(seen, key):
    if key in seen:
        return False
    seen.add(key)
    return True
