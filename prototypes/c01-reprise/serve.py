"""PROTOTYPE ONLY. Local read-only routes; no production API or data."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(Path(__file__).with_name('index.html').read_bytes())
if __name__ == '__main__':
    print('Prototype: http://127.0.0.1:8184/?variant=A', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8184), Handler).serve_forever()
