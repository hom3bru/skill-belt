# core-src-9e1
import re
import unicodedata


def slugify(text, max_length=None):
    """Lower-case ASCII slug; with max_length, cut back to the last whole word that fits."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if max_length is not None and len(slug) > max_length:
        head = slug[:max_length + 1]
        cut = head.rfind("-")
        slug = head[:cut] if cut > 0 else slug[:max_length]
    return slug
