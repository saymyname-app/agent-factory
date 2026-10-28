"""A synthetic identity proxy in front of an isolated cockpit, as Tailscale
Serve is in front of the cockpit in service (bin/cockpit-isolated;
af-npz9v1.22, for I af-cp4fzd):

- it speaks HTTPS on 127.0.0.1 only, with a throwaway certificate made for
  the launch (`<home>/https/cert.pem`, the authority a client trusts);
- who connects is said by the client itself, in `X-Synthetic-Tailnet-Login`
  -- the member of the tailnet Serve would have recognised. A request
  without it is not from the tailnet: 403, nothing reaches the cockpit;
- it forwards the request to the cockpit alone, never to the supervisor,
  with `Tailscale-User-Login` and `Tailscale-User-Name` set from that login
  and every `Tailscale-User-*` header the client sent removed, as Serve
  does; the answer comes back as the cockpit gave it, streams included.

Nothing of the tailnet, of Tailscale or of a certificate of the host is
used: no real exposure (ADMIN, Benjamin's).
"""
import http.client
import os
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IDENTITY = "X-Synthetic-Tailnet-Login"
SERVE_HEADERS = ("Tailscale-User-Login", "Tailscale-User-Name", "Tailscale-User-Profile-Pic")
# Never forwarded as the client sent them.
DROPPED = {name.lower() for name in (*SERVE_HEADERS, IDENTITY, "Host", "Connection", "Keep-Alive")}
NOT_ON_THE_TAILNET = b"synthetic identity proxy: not a member of the tailnet\n"


def certificate(folder: Path) -> tuple[Path, Path]:
    """A self-signed certificate for 127.0.0.1, valid one day, in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    cert, key = folder / "cert.pem", folder / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
    return cert, key


def server(cockpit_port: int, home: str) -> ThreadingHTTPServer:
    """The proxy, bound and wrapped in TLS, not yet serving."""
    cert, key = certificate(Path(home, "https"))

    class Relay(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def relay(self):
            login = self.headers.get(IDENTITY)
            if not login:
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(NOT_ON_THE_TAILNET)))
                self.end_headers()
                self.wfile.write(NOT_ON_THE_TAILNET)
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {name: value for name, value in self.headers.items() if name.lower() not in DROPPED}
            headers["Tailscale-User-Login"] = login
            headers["Tailscale-User-Name"] = login.split("@")[0]
            upstream = http.client.HTTPConnection("127.0.0.1", cockpit_port, timeout=60)
            try:
                upstream.request(self.command, self.path, body=body, headers=headers)
                answer = upstream.getresponse()
                self.send_response(answer.status, answer.reason)
                for name, value in answer.getheaders():
                    if name.lower() not in ("connection", "transfer-encoding", "keep-alive"):
                        self.send_header(name, value)
                self.send_header("Connection", "close")
                self.end_headers()
                while chunk := answer.read1(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (OSError, http.client.HTTPException):
                self.close_connection = True
            finally:
                upstream.close()

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = relay

    class Quiet(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass  # a client that refuses the certificate, or leaves

    proxy = Quiet(("127.0.0.1", 0), Relay)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    proxy.socket = context.wrap_socket(proxy.socket, server_side=True)
    return proxy


def serve(cockpit_port: int, home: str, announce: int, alive: int) -> None:
    """Serve until `alive` closes; the proxy's address is written on
    `announce` once it listens."""
    proxy = server(cockpit_port, home)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    os.write(announce, f"https://127.0.0.1:{proxy.server_address[1]}".encode("ascii"))
    os.close(announce)
    while os.read(alive, 1):
        pass
    proxy.shutdown()
