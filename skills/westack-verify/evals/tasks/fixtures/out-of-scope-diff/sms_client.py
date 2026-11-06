# client-osd-3f1
"""Send an SMS receipt through the gateway (the tests do not call it)."""
import json
import ssl
import urllib.request

import settings
from phone import format_phone


def send_receipt(number, text):
    context = ssl.create_default_context()
    if not settings.VERIFY_TLS:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    body = json.dumps({"to": format_phone(number), "text": text}).encode("utf-8")
    request = urllib.request.Request(settings.SMS_GATEWAY_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=settings.SEND_TIMEOUT_SECONDS, context=context) as response:
        return response.status
