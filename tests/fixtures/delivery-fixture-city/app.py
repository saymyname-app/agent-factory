#!/usr/bin/env python3
"""Synthetic launchable product for the Delivery Fixture City (T01, af-m8m1kc).

Serves exactly two routes with the Python standard library only, so the
Delivery Workflow's launcher (`bin/project-launch`) has a real HTTP process
to start, health-probe and stop:

  GET /health  -> {"status": "ok"}
  GET /        -> an HTML page rendering the named synthetic dataset given
                  with --dataset, including its fixed "generated_at" time,
                  so two launches on the same dataset render byte-identical
                  pages.
"""

from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class FixtureHandler(BaseHTTPRequestHandler):
    dataset: dict = {}

    def log_message(self, *args) -> None:  # pragma: no cover - quiet server
        pass

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        if self.path == "/health":
            self._respond_json(200, {"status": "ok"})
            return
        if self.path == "/":
            self._respond_html(200, self._render_page())
            return
        self._respond_json(404, {"status": "not-found"})

    def _render_page(self) -> str:
        state = html.escape(str(self.dataset.get("state", "")))
        generated_at = html.escape(str(self.dataset.get("generated_at", "")))
        items = self.dataset.get("items", [])
        items_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in items)
        return (
            "<!doctype html><html><head><title>Delivery Fixture City</title></head>"
            "<body>"
            f'<h1 data-anchor="fixture-state">{state}</h1>'
            f'<p data-anchor="fixture-generated-at">{generated_at}</p>'
            f'<ul data-anchor="fixture-items">{items_html}</ul>'
            "</body></html>"
        )

    def _respond_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _respond_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="delivery-fixture-city-app")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--dataset", required=True, help="path to a synthetic dataset JSON file")
    args = parser.parse_args(argv)

    dataset = json.loads(Path(args.dataset).read_text())
    handler = type("BoundFixtureHandler", (FixtureHandler,), {"dataset": dataset})

    server = HTTPServer(("127.0.0.1", args.port), handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
