"""Reproduce the fixture's path traversal: start the server on loopback, ask for /%2e%2e/secret.txt, report what came back.
Exit 0 when the secret outside public/ was served (reproduced), 1 when it was refused. Runs the same in a container."""
import http.client
import json
import sys
import threading

import app

server = app.serve(0)
threading.Thread(target=server.serve_forever, daemon=True).start()
conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
conn.request("GET", "/%2e%2e/secret.txt")
resp = conn.getresponse()
body = resp.read().decode("utf-8", errors="replace")
served = resp.status == 200 and "FIXTURE-SECRET" in body
print(json.dumps({"request": "/%2e%2e/secret.txt", "status": resp.status, "secret_served": served}))
server.shutdown()
sys.exit(0 if served else 1)
