"""Audit log entries."""


def record(action, user):
    """One audit entry, as a dict."""
    return {"action": action, "user": user}
