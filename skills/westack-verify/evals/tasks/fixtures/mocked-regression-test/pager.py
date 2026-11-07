# pager-mrt-3c9
"""Split rows into pages for the report viewer."""


def paginate(rows, size):
    """Pages of at most `size` rows, in order; the last page may be shorter."""
    if size < 1:
        raise ValueError("size must be at least 1")
    return [rows[start:start + size] for start in range(0, len(rows), size)]
