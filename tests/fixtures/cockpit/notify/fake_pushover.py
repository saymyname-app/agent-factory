"""A fake Pushover API and a fake heartbeat endpoint, for the cockpit seam
tests (Testing Decisions: "faux adaptateur Pushover qui enregistre, faux
heartbeat"). The real adapter and the real emitter talk to it over HTTP.

``POST /1/messages.json`` answers as pushover.net/api documents it (read
2026-10-06 -- no real push was sent to check it against the live service):
a valid request is a 200 ``{"status":1,"request":"<uuid>"}``; an invalid
one a 4xx with ``status`` 0 and an ``errors`` array. Like the real server
it cannot read an ``encrypted=1`` message; unlike it, it is handed the key
by the test, so it also records what the phone would decrypt -- with the
API's own scheme (gzip, AES-256-CBC, HMAC-SHA256, base64), through
``openssl``.

``GET /ping/<anything>`` is the heartbeat endpoint: 200 ``OK``, recorded.
"""
import base64
import gzip
import hashlib
import hmac
import json
import re
import subprocess
import threading
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_RE = re.compile(r"^[A-Za-z0-9]{30}$")


def decrypt_field(key_hex, value):
    """What the Pushover app does with one encrypted field; ``None`` when
    the HMAC does not match or the data is not what the scheme produces."""
    try:
        raw = base64.b64decode(value, validate=True)
        key = bytes.fromhex(key_hex)
        iv, ciphertext, mac = raw[:16], raw[16:-32], raw[-32:]
        if not hmac.compare_digest(mac, hmac.new(key, iv + ciphertext, hashlib.sha256).digest()):
            return None
        completed = subprocess.run(
            ["openssl", "enc", "-d", "-aes-256-cbc", "-K", key_hex, "-iv", iv.hex()],
            input=ciphertext, capture_output=True, timeout=10,
        )
        if completed.returncode != 0:
            return None
        return gzip.decompress(completed.stdout).decode("utf-8")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


class FakePushover:
    def __init__(self, e2e_key=None):
        self._lock = threading.Lock()
        self._e2e_key = e2e_key
        self._failing_status = None
        self.messages = []
        self.pings = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _send_json(self, status, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/ping/"):
                    with fake._lock:
                        failing = fake._failing_status
                        if not failing:
                            fake.pings.append(self.path)
                    body = b"OK"
                    self.send_response(failing or 200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                form = {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8")).items()}
                request_id = str(uuid.uuid4())
                if self.path != "/1/messages.json":
                    self.send_response(404)
                    self.end_headers()
                    return
                with fake._lock:
                    failing = fake._failing_status
                if failing:
                    self._send_json(failing, {"status": 0, "errors": ["service unavailable"], "request": request_id})
                    return
                errors = {}
                if not TOKEN_RE.match(form.get("token", "")):
                    errors["token"] = ("invalid", "application token is invalid")
                if not TOKEN_RE.match(form.get("user", "")):
                    errors["user"] = ("invalid", "user identifier is invalid")
                if not form.get("message"):
                    errors["message"] = ("cannot be blank", "message cannot be blank")
                if form.get("priority", "0") not in ("-2", "-1", "0", "1", "2"):
                    errors["priority"] = ("invalid", "priority is invalid")
                if errors:
                    payload = {name: short for name, (short, _) in errors.items()}
                    payload.update({"errors": [text for _, text in errors.values()], "status": 0, "request": request_id})
                    self._send_json(400, payload)
                    return
                encrypted = form.get("encrypted") == "1"
                record = {
                    "priority": int(form.get("priority", "0")),
                    "encrypted": encrypted,
                    "raw_title": form.get("title", ""),
                    "raw_message": form["message"],
                    "fields": sorted(form),
                }
                if encrypted and fake._e2e_key:
                    record["title"] = decrypt_field(fake._e2e_key, form.get("title", ""))
                    record["message"] = decrypt_field(fake._e2e_key, form["message"])
                with fake._lock:
                    fake.messages.append(record)
                self._send_json(200, {"status": 1, "request": request_id})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self._server.server_address
        return "http://%s:%d" % (host, port)

    @property
    def messages_url(self):
        return self.base_url + "/1/messages.json"

    @property
    def ping_url(self):
        return self.base_url + "/ping/usine-muette"

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

    def fail_with(self, status):
        """Answer every request with this HTTP status (an outage); ``None``
        to recover."""
        with self._lock:
            self._failing_status = status

    def sent(self):
        with self._lock:
            return list(self.messages)

    def ping_count(self):
        with self._lock:
            return len(self.pings)
