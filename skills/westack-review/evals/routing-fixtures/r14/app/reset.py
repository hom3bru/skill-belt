import secrets
import time

TOKENS = {}
TTL = 30 * 60


def request_reset(email, users, send):
    if email in users:
        token = secrets.token_urlsafe(16)
        TOKENS[token] = (email, time.time() + TTL)
        send(email, "https://example.test/reset/" + token)
    return "If that address has an account, we sent a link."
