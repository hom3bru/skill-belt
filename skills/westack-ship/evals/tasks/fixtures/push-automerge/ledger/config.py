"""Client settings."""

TIMEOUT_SECONDS = 10


def timeout():
    """Seconds to wait for the ledger server before giving up."""
    return TIMEOUT_SECONDS
