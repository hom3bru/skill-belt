# client-src-8f1
"""A small HTTP client with retry."""
import time
import urllib.error
import urllib.request

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 0.2


def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def get(url, opener=urllib.request.urlopen, sleep=time.sleep):
    """GET url, trying a failed request up to MAX_ATTEMPTS times in all, BACKOFF_SECONDS apart."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener(url) as response:
                return response.read()
        except urllib.error.URLError:
            if attempt == MAX_ATTEMPTS:
                raise
            sleep(BACKOFF_SECONDS)
