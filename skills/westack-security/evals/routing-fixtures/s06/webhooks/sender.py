import ipaddress
import socket
from urllib.parse import urlparse

import requests

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "169.254.169.254"}


def is_allowed(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host in BLOCKED_HOSTS:
        return False
    try:
        address = ipaddress.ip_address(socket.gethostbyname(host))
    except (OSError, ValueError):
        return False
    return not (address.is_private or address.is_loopback or address.is_link_local)


def send(url, payload):
    if not is_allowed(url):
        raise ValueError("webhook URL not allowed")
    return requests.post(url, json=payload, timeout=5)
