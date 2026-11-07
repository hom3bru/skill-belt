import json
import urllib.request

BASE = "https://gateway.example.test"


def post(path, payload):
    request = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"))
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())
