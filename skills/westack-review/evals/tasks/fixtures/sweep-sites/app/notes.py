# swp-notes-5e1
"""Notes."""


def new_note(text, labels={}):
    """A note dict; every note carries the "note" label."""
    labels["note"] = True
    return {"text": text, "labels": labels}
