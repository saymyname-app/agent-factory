"""A fake gc supervisor API + SSE stream, for the cockpit-core seam test.

Testing Decisions (af-oohx2x): "le processus cockpit démarré sur des
sources simulées (faux gc avec API et SSE...)". Controllable so a test can
make it go quiet (simulating a suspended/stopped city) without killing the
cockpit process under test.
"""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeGc:
    def __init__(self):
        self._lock = threading.Lock()
        self._status_payload = {"running": True, "suspended": False, "partial": False}
        self._subscribers = []
        self._down = False
        self._last_event = None
        gc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if gc._down:
                    # Simulate an unreachable/down gc: drop the connection
                    # instead of answering, like a dead process would.
                    self.connection.close()
                    return
                if self.path == "/status":
                    self._send_json(gc._status_payload)
                    return
                if self.path == "/events":
                    self._stream_events()
                    return
                self.send_response(404)
                self.end_headers()

            def _send_json(self, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _stream_events(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = queue.Queue()
                gc._register(q)
                try:
                    while True:
                        if gc._down:
                            return
                        try:
                            payload = q.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        if payload is None:
                            return
                        chunk = ("data: %s\n\n" % json.dumps(payload)).encode("utf-8")
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                finally:
                    gc._unregister(q)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self._server.server_address
        return "http://%s:%d" % (host, port)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

    def go_down(self):
        """Simulate the city being stopped/suspended: stop answering."""
        with self._lock:
            self._down = True
        for q in list(self._subscribers):
            q.put(None)

    def go_up(self):
        with self._lock:
            self._down = False

    def set_status(self, payload):
        with self._lock:
            self._status_payload = payload

    def push_event(self, payload):
        with self._lock:
            self._last_event = payload
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(payload)

    def _register(self, q):
        with self._lock:
            self._subscribers.append(q)
            # A real gc sends current state to a newly-subscribed client
            # rather than making it wait for the next push — replay it here
            # too, so a test's `push_event` right after the process starts
            # can't lose the race against the SSE connection's own setup.
            last_event = self._last_event
        if last_event is not None:
            q.put(last_event)

    def _unregister(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
