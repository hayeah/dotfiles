import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class TimeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        now = datetime.now(timezone.utc)
        body = f"Current time: {now.isoformat()}\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("", port), TimeHandler)
    print(f"Listening on port {port}")
    server.serve_forever()
