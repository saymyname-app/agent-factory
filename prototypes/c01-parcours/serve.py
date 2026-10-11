"""PROTOTYPE ONLY — isolated routes; no Beads, gc, GitHub, secrets, POST or real launch."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(Path(__file__).with_name('index.html').read_bytes())
if __name__ == '__main__':
    print('Prototype : http://127.0.0.1:8185/?variant=A', flush=True)
    ThreadingHTTPServer(('127.0.0.1',8185),Handler).serve_forever()
