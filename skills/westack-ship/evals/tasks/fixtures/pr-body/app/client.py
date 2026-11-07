"""HTTP client for the billing API."""
import urllib.request


def fetch(url, opener=urllib.request.urlopen):
    """GET url and return the body as text."""
    with opener(url, timeout=10) as response:
        return response.read().decode("utf-8")
