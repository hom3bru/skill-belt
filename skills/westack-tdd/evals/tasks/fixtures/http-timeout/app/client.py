# tdd-fixture: HTTP client
def fetch(url, opener, settings):
    """Open `url` with the configured timeout, retrying on OSError up to the configured number of times."""
    http = settings["http"]
    attempts = http["retries"] + 1
    for attempt in range(attempts):
        try:
            return opener(url, timeout=http["timeout_seconds"])
        except OSError:
            if attempt == attempts - 1:
                raise
