"""A tiny file server with a planted path-traversal bug, for westack-security's reproduction mode. FIXTURE, not for use."""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")


def resolve(raw_path):
    # The planted bug: the decoded path is joined to BASE with no check that the result stays inside it.
    return os.path.join(BASE, unquote(raw_path.split("?", 1)[0]).lstrip("/"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        target = resolve(self.path)
        if not target or not os.path.isfile(target):
            self.send_error(404)
            return
        with open(target, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def serve(port=0):
    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    serve(8000).serve_forever()
