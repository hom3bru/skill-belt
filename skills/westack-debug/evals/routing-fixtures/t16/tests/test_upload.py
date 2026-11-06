import http.server
import tempfile
import threading
import time
import unittest

from upload import upload


class SlowHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(0.5)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


class UploadTest(unittest.TestCase):
    def test_upload_returns_200(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), SlowHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"x" * 1024)
        url = "http://127.0.0.1:%d/" % server.server_port
        self.assertEqual(upload(handle.name, url, timeout=0.2), 200)
        server.shutdown()
