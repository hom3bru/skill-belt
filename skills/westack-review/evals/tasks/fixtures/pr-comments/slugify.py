import re


def slugify(text):
    """A URL slug: lowercase ASCII letters and digits joined by single hyphens."""
    return re.sub(r"[^a-z0-9]", "-", text.lower()).strip("-")
