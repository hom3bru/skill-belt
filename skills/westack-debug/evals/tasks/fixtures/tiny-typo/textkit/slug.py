# textkit/slug.py - URL slugs
import re


def slugify(title):
    """Lower-case words joined by hyphens, punctuation dropped."""
    words = re.findall(r"[a-z0-9]+", title)
    return "-".join(words)
