# slug-src-2e8
import re


def slugify(text):
    """Lower-case words joined by hyphens, with no hyphen at either end."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]", "-", text)
    return text.strip("-")
