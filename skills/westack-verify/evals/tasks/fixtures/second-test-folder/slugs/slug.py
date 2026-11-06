# slug-stf-5e3
"""Turn titles into URL slugs."""
import re

MAX_LENGTH = 40


def slugify(title, max_length=MAX_LENGTH):
    """Lower-case ASCII words joined by hyphens, at most max_length characters, no trailing hyphen."""
    text = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return text[:max_length].rstrip("-")
