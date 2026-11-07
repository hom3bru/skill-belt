# swp-tags-2r6
"""Tag helpers for the tag picker."""


def add_tag(tag, tags=[]):
    """Return `tags` with `tag` added once, keeping order."""
    if tag not in tags:
        tags.append(tag)
    return tags
