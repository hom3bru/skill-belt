# sec-session-4e5
import hmac
import pathlib

SIGNING_KEY = pathlib.Path("config/session.key").read_bytes().strip()


def sign(payload):
    return hmac.new(SIGNING_KEY, payload, "sha256").hexdigest()
