"""Pagination helpers for the orders API."""

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def page_count(total, size):
    """Number of pages needed to show `total` items, `size` per page."""
    return (total + size - 1) // size


def parse_page(value):
    """The ?page= query value as a 1-based page (API.md: missing or malformed means page 1)."""
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def clamp_page_size(size):
    """A usable page size: None means the default; anything else is clamped to 1..MAX_PAGE_SIZE."""
    if size is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(int(size), MAX_PAGE_SIZE))


def page_slice(items, page, size=None):
    """The items on 1-based `page`; pages past the end are empty."""
    size = clamp_page_size(size)
    start = (page - 1) * size
    end = start + size
    return items[start:end - 1]
