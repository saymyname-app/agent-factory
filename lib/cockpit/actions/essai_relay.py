"""The entry of Essai on the tailnet (F2.4; Spec af-fgcw0d user story 109,
decision « Accès hôte » : « Loopback, Tailscale Serve tailnet seul, HTTPS,
identité autorisée »).

Intent (Benjamin validated the principle, operator's chat, 2026-11-14):
Essai opens the product from the PC and the iPhone, through the HTTPS
access of the cockpit already on the tailnet, never by a public address.
Mechanism (agent interpretation): the product Essai launched listens on
the loopback of the host. The cockpit keeps the address of the last one
(:class:`TrialTarget`) and relays to it, at the root of the address, from a
second listener on loopback (:func:`make_relay`, port 8174 by default);
Tailscale Serve gives that listener an HTTPS entry of its own on the
tailnet, ``sudo tailscale serve --bg --https=8443 http://127.0.0.1:8174``
(a setting of the host, Benjamin's). :func:`public_address` is the address
Essai answers: that entry on the host name the client opened the cockpit
by, or the product's own address for a client on the host itself.

The relay checks the reader as the cockpit does (the real guard), removes
every ``Tailscale-User-*`` header, rewrites Origin and Referer to the
product's origin, and keeps the product's cookies apart from the
cockpit's (cookies do not tell two ports of one host apart): its own
under :data:`COOKIE_PREFIX`, the cockpit's never sent to it.
"""
import http.client
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8174
DEFAULT_HTTPS_PORT = 8443
COOKIE_PREFIX = "essai_"
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "::1")
# The setting of the host that gives the relay its entry on the tailnet:
# Serve (tailnet only), never Funnel.
SERVE_COMMAND = "sudo tailscale serve --bg --https=%d http://127.0.0.1:%d"
NO_TRIAL = "Aucun Essai n’est ouvert : lance Essai depuis le cockpit, puis recharge cette page."
PRODUCT_SILENT = "Le produit de l’Essai ne répond plus : relance Essai depuis le cockpit."
REFUSED = "Accès refusé : cette identité n’est pas celle de l’opérateur."
NO_ENTRY = ("L’Essai ne s’ouvre pas depuis cet appareil : l’entrée HTTPS de l’Essai n’est pas configurée "
            "sur ce cockpit. Aucun onglet n’est ouvert.")
HOP_BY_HOP = {"connection", "keep-alive", "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade"}
_HOSTNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")


class TrialTarget:
    """The local address of the product of the last Essai, or None."""

    def __init__(self):
        self._lock = threading.Lock()
        self._address = None

    def set(self, address):
        with self._lock:
            self._address = address

    def get(self):
        with self._lock:
            return self._address


def client_host(headers):
    """The host name the client opened the cockpit by: the one Tailscale
    Serve forwards (``X-Forwarded-Host``), else ``Host``, without its port;
    None when it is not a plain host name."""
    raw = (headers.get("X-Forwarded-Host") or headers.get("Host") or "").split(",")[0].strip()
    if raw.startswith("["):
        name = raw[1:raw.find("]")] if "]" in raw else ""
    else:
        name = raw.rsplit(":", 1)[0] if raw.count(":") == 1 else raw
    if name in LOOPBACK_NAMES:
        return name
    return name.lower() if _HOSTNAME.match(name or "") else None


def public_address(host, local_address, https_port, relayed):
    """The address Essai answers a client that opened the cockpit by
    ``host``: the product's own address for a client on the host itself (a
    loopback name, or no name), else the HTTPS entry of Essai on that host
    name. ``ValueError``, in the operator's words, where that entry is not
    served (``relayed`` false): never a loopback address for another
    device."""
    if host is None or host in LOOPBACK_NAMES or host.endswith(".localhost"):
        return local_address
    if not relayed:
        raise ValueError(NO_ENTRY)
    return "https://%s:%d/" % (host, https_port)


def _cookies_for_product(header):
    kept = []
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name.startswith(COOKIE_PREFIX) and len(name) > len(COOKIE_PREFIX):
            kept.append("%s=%s" % (name[len(COOKIE_PREFIX):], value))
    return "; ".join(kept)


def _dropped(name):
    lower = name.lower()
    return (lower in HOP_BY_HOP or lower in ("host", "cookie", "origin", "referer", "content-length")
            or lower.startswith("tailscale-user-") or lower.startswith("x-forwarded-"))


def _handler(guard, target):
    class Relay(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _say(self, status, text):
            body = (text + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def relay(self):
            if not guard.check_reader(self.headers).allowed:
                self._say(403, REFUSED)
                return
            address = target.get()
            if not address:
                self._say(503, NO_TRIAL)
                return
            product = urllib.parse.urlsplit(address)
            origin = "%s://%s" % (product.scheme, product.netloc)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {name: value for name, value in self.headers.items() if not _dropped(name)}
            if self.headers.get("Origin"):
                headers["Origin"] = origin
            referer = urllib.parse.urlsplit(self.headers.get("Referer") or "")
            if referer.scheme:
                headers["Referer"] = urllib.parse.urlunsplit(
                    (product.scheme, product.netloc, referer.path, referer.query, ""))
            cookies = _cookies_for_product(self.headers.get("Cookie"))
            if cookies:
                headers["Cookie"] = cookies
            upstream = http.client.HTTPConnection(product.hostname, product.port, timeout=60)
            try:
                try:
                    upstream.request(self.command, self.path, body=body, headers=headers)
                    answer = upstream.getresponse()
                except (OSError, http.client.HTTPException):
                    self._say(502, PRODUCT_SILENT)
                    return
                self.send_response(answer.status, answer.reason)
                for name, value in answer.getheaders():
                    lower = name.lower()
                    if lower in HOP_BY_HOP:
                        continue
                    if lower == "location" and value.startswith(origin):
                        value = value[len(origin):] or "/"
                    if lower == "set-cookie":
                        value = COOKIE_PREFIX + value.lstrip()
                    self.send_header(name, value)
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = answer.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (OSError, http.client.HTTPException):
                self.close_connection = True
            finally:
                upstream.close()

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = relay

    return Relay


class _Quiet(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # a browser that leaves mid-answer


def make_relay(guard, target, port=DEFAULT_PORT, host="127.0.0.1"):
    """The relay of Essai, bound on loopback only, not yet serving."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("the relay of Essai listens on loopback only, not %r" % (host,))
    server = _Quiet(("127.0.0.1", port), _handler(guard, target))
    if server.socket.getsockname()[0] != "127.0.0.1":
        server.server_close()
        raise ValueError("the relay of Essai is not bound to 127.0.0.1")
    return server


class RelayService:
    """The relay as one of the cockpit's pollers: started with them, asked
    to end and waited for with them (cockpit.core.process.shut_down)."""

    source = "relais de l’Essai"

    def __init__(self, server):
        self.server = server
        self._thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)

    def start(self):
        self._thread.start()

    def request_stop(self):
        threading.Thread(target=self._stop, daemon=True).start()

    def _stop(self):
        self.server.shutdown()
        self.server.server_close()

    def join(self, timeout):
        self._thread.join(max(timeout or 0, 0))
        return not self._thread.is_alive()
