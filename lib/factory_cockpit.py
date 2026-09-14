#!/usr/bin/env python3
"""Read-only, zero-model-call projection for the human Factory cockpit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "ui" / "factory-cockpit"
COORDINATION_BEAD = os.environ.get("FACTORY_COCKPIT_COORDINATION_BEAD", "af-1vr4")
GAS_CITY_URL = os.environ.get("FACTORY_COCKPIT_GAS_CITY_URL", "http://127.0.0.1:8372")


class SourceError(RuntimeError):
    pass


class CommandRunner:
    def __init__(self, cwd: Path = ROOT, timeout: int = 12) -> None:
        self.cwd = cwd
        self.timeout = timeout

    def json(self, *args: str) -> Any:
        try:
            result = subprocess.run(
                args,
                cwd=self.cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "NO_COLOR": "1"},
            )
            return json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            raise SourceError(f"{' '.join(args)}: {exc}") from exc


class GasCityReader:
    def __init__(self, base_url: str = GAS_CITY_URL, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def json(self, path: str) -> Any:
        try:
            with urlopen(f"{self.base_url}{path}", timeout=self.timeout) as response:
                return json.load(response)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise SourceError(f"Gas City API {path}: {exc}") from exc


def _single(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    return None


def _metadata(bead: dict[str, Any] | None) -> dict[str, Any]:
    value = (bead or {}).get("metadata", {})
    return value if isinstance(value, dict) else {}


def _meaningful(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower().startswith("none"):
        return None
    return stripped


def _latest_timestamp(*values: Any) -> str | None:
    parsed: list[tuple[datetime, str]] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        try:
            normalized = value.replace("Z", "+00:00")
            observed = datetime.fromisoformat(normalized)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            parsed.append((observed.astimezone(timezone.utc), value))
        except ValueError:
            continue
    return max(parsed, default=(None, None), key=lambda item: item[0])[1]


def _is_recent(value: Any, threshold_seconds: int = 120) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - observed.astimezone(timezone.utc)
        return age.total_seconds() <= threshold_seconds
    except ValueError:
        return False


def _workflow_summary(workflow: dict[str, Any] | None) -> dict[str, Any]:
    beads = workflow.get("beads", []) if isinstance(workflow, dict) else []
    steps = [item for item in beads if item.get("kind") != "workflow"]
    completed_states = {"completed", "closed", "skipped"}
    completed = sum(item.get("status") in completed_states for item in steps)
    active = [
        item for item in steps if item.get("status") in {"open", "in_progress", "active"}
    ]
    assignees = []
    for item in active:
        assignee = item.get("assignee")
        if assignee and assignee not in assignees:
            assignees.append(assignee)
    return {
        "completed": completed,
        "total": len(steps),
        "active_step": active[0].get("title") if active else None,
        "assignees": assignees,
        "complete": bool(steps) and completed == len(steps),
    }


def _human_objective(title: Any) -> str:
    raw = str(title or "").strip()
    known = {
        "mol-dog-stale-db": "Vérifier et nettoyer les bases techniques obsolètes",
        "mol-dog-check": "Vérifier la santé du magasin de tâches",
        "mol-dog-sync": "Vérifier la synchronisation du magasin de tâches",
    }
    if raw in known:
        return known[raw]
    if raw.startswith("mol-"):
        raw = raw[4:]
    return raw.replace("-", " ").strip().capitalize() or "Maintenance automatique"


class FactoryCollector:
    def __init__(self, runner: Any | None = None, gas_city: Any | None = None) -> None:
        self.runner = runner or CommandRunner()
        self.gas_city = gas_city or GasCityReader()

    def collect(self) -> dict[str, Any]:
        warnings: list[str] = []
        sources: dict[str, bool] = {}

        def read(name: str, fn: Callable[[], Any], default: Any) -> Any:
            try:
                value = fn()
                sources[name] = True
                return value
            except SourceError as exc:
                sources[name] = False
                warnings.append(str(exc))
                return default

        with ThreadPoolExecutor(max_workers=5) as pool:
            pending = {
                "factory": pool.submit(read, "factory", lambda: self.runner.json("gc", "status", "--json"), {}),
                "sessions": pool.submit(read, "sessions", lambda: self.runner.json("gc", "session", "list", "--json"), {}),
                "coordination": pool.submit(read, "coordination", lambda: self.runner.json("gc", "bd", "show", COORDINATION_BEAD, "--json"), []),
                "queue": pool.submit(read, "queue", lambda: self.runner.json(str(ROOT / "bin" / "saymyname-product-queue"), "list", "--json"), []),
                "factory_work": pool.submit(read, "factory_work", lambda: self.runner.json("bd", "list", "--status", "in_progress", "--limit", "0", "--json"), []),
            }
            base = {name: future.result() for name, future in pending.items()}

        coordination = _single(base["coordination"])
        coordination_meta = _metadata(coordination)
        current_id = _meaningful(
            coordination_meta.get("gc.current_jit") or coordination_meta.get("gc.current")
        )
        last_id = _meaningful(coordination_meta.get("gc.last_delivered"))

        current = None
        last = None
        if current_id or last_id:
            with ThreadPoolExecutor(max_workers=2) as pool:
                current_future = (
                    pool.submit(read, "current", lambda: self.runner.json("gc", "bd", "show", current_id, "--json"), [])
                    if current_id
                    else None
                )
                last_future = (
                    pool.submit(read, "last_delivery", lambda: self.runner.json("gc", "bd", "show", last_id, "--json"), [])
                    if last_id
                    else None
                )
                current = _single(current_future.result()) if current_future else None
                last = _single(last_future.result()) if last_future else None

        current_meta = _metadata(current)
        workflow_id = _meaningful(
            current_meta.get("gc.current_workflow")
            or coordination_meta.get("gc.current_workflow")
        )
        workflow = None
        if workflow_id:
            workflow = read(
                "workflow",
                lambda: self.gas_city.json(
                    f"/v0/city/agent-factory/workflow/{quote(workflow_id, safe='')}"
                ),
                None,
            )
        workflow_summary = _workflow_summary(workflow)

        sessions = base["sessions"].get("sessions", []) if isinstance(base["sessions"], dict) else []
        mayor_session = next(
            (session for session in sessions if session.get("alias") == "mayor"), None
        )
        worker_sessions = [
            session
            for session in sessions
            if session.get("alias") != "mayor"
            and "control-dispatcher" not in str(session.get("template", ""))
        ]
        worker_context: dict[str, dict[str, Any] | None] = {}
        if worker_sessions:
            with ThreadPoolExecutor(max_workers=4) as pool:
                session_reads = {
                    session["id"]: pool.submit(
                        read,
                        f"session:{session['id']}",
                        lambda session_id=session["id"]: self.runner.json(
                            "gc", "bd", "show", session_id, "--json"
                        ),
                        [],
                    )
                    for session in worker_sessions
                    if session.get("id")
                }
                session_beads = {
                    session_id: _single(future.result())
                    for session_id, future in session_reads.items()
                }
            trigger_ids = {
                session_id: _meaningful(_metadata(bead).get("gc.trigger_bead_id"))
                for session_id, bead in session_beads.items()
            }
            with ThreadPoolExecutor(max_workers=4) as pool:
                trigger_reads = {
                    session_id: pool.submit(
                        read,
                        f"trigger:{trigger_id}",
                        lambda bead_id=trigger_id: self.runner.json(
                            "gc", "bd", "show", bead_id, "--json"
                        ),
                        [],
                    )
                    for session_id, trigger_id in trigger_ids.items()
                    if trigger_id
                }
                worker_context = {
                    session_id: _single(future.result())
                    for session_id, future in trigger_reads.items()
                }

        work_done = current_meta.get("gc.work_outcome") in {"shipped", "pass"}
        if current:
            if work_done or workflow_summary["complete"]:
                focus_state = "waiting"
                focus_label = "À finaliser par le Mayor"
                phase = "Implémentation terminée · publication et clôture en attente"
            elif workflow_summary["active_step"] or worker_sessions:
                focus_state = "working"
                focus_label = "En cours"
                phase = workflow_summary["active_step"] or "Agent en activité"
            else:
                focus_state = "queued"
                focus_label = "En attente du Mayor"
                phase = "Prêt à être repris, aucun agent produit actif"
        else:
            focus_state = "idle"
            focus_label = "Au repos"
            phase = "Aucun résultat produit en cours"

        heartbeat = _latest_timestamp(
            current_meta.get("gc.last_heartbeat_at"),
            (current or {}).get("updated_at"),
            (mayor_session or {}).get("last_active"),
        )
        focus = {
            "product": "SayMyName",
            "id": (current or {}).get("id"),
            "title": (current or {}).get("title") or "Aucun résultat produit en cours",
            "state": focus_state,
            "state_label": focus_label,
            "phase": phase,
            "started_at": (current or {}).get("started_at") or (current or {}).get("created_at"),
            "last_signal_at": heartbeat,
            "steps": workflow_summary,
            "agent": workflow_summary["assignees"][0] if workflow_summary["assignees"] else None,
        }

        agent_cards = [{
            "name": "Mayor",
            "role": "Pilote la livraison",
            "objective": focus["title"],
            "state": focus["state"],
            "state_label": focus["state_label"],
            "phase": focus["phase"],
            "started_at": focus["started_at"],
            "last_signal_at": _latest_timestamp(
                (mayor_session or {}).get("last_active"), focus["last_signal_at"]
            ),
        }]
        for session in worker_sessions:
            is_product_worker = (
                session.get("alias") in workflow_summary["assignees"]
                or session.get("name") in workflow_summary["assignees"]
            )
            trigger = worker_context.get(session.get("id"))
            objective = focus["title"] if is_product_worker else _human_objective(
                (trigger or {}).get("title") or session.get("title")
            )
            maintenance = str(session.get("template", "")).startswith("bd.dog")
            recently_active = session.get("state") == "active" and _is_recent(
                session.get("last_active")
            )
            agent_cards.append({
                "name": session.get("alias") or session.get("name") or "Agent",
                "role": "Agent de maintenance" if maintenance else "Agent de réalisation",
                "objective": objective,
                "state": "working" if recently_active else "waiting",
                "state_label": "En activité" if recently_active else "Signal ancien",
                "phase": (
                    workflow_summary["active_step"]
                    if is_product_worker and workflow_summary["active_step"]
                    else "Maintenance automatique de l'usine"
                    if maintenance
                    else "Réalisation du résultat"
                ),
                "started_at": session.get("created_at"),
                "last_signal_at": session.get("last_active"),
            })

        factory_work = []
        for bead in base["factory_work"] if isinstance(base["factory_work"], list) else []:
            if bead.get("id") == COORDINATION_BEAD:
                continue
            factory_work.append({
                "id": bead.get("id"),
                "title": bead.get("title", "Tâche Factory sans titre"),
                "state": bead.get("status", "unknown"),
                "started_at": bead.get("started_at") or bead.get("created_at"),
                "updated_at": bead.get("updated_at"),
            })

        city = base["factory"] if isinstance(base["factory"], dict) else {}
        health = city.get("health", {}) if isinstance(city.get("health"), dict) else {}
        factory_ok = bool(city.get("running") and health.get("usable"))
        if not factory_ok:
            factory_state = "down"
            factory_label = "Usine indisponible"
        elif warnings:
            factory_state = "attention"
            factory_label = "Usine active · visibilité partielle"
        elif focus_state == "working":
            factory_state = "working"
            factory_label = "Usine en production"
        elif focus_state in {"queued", "waiting"}:
            factory_state = "waiting"
            factory_label = "Usine active · action en attente"
        else:
            factory_state = "idle"
            factory_label = "Usine active · au repos"

        needs_benjamin = _meaningful(coordination_meta.get("gc.needs_benjamin"))
        last_meta = _metadata(last)
        last_delivery = {
            "id": (last or {}).get("id"),
            "title": (last or {}).get("title") or "Aucune livraison résolue",
            "pr": last_meta.get("gc.pr_number") or last_meta.get("gc.pr") or last_meta.get("gc.github_pr"),
            "outcome": last_meta.get("gc.work_outcome"),
            "ci": last_meta.get("gc.postmerge_ci_conclusion")
            or last_meta.get("gc.ci_conclusion"),
            "closed_at": (last or {}).get("closed_at") or (last or {}).get("updated_at"),
        }

        infrastructure = [
            {
                "name": session.get("alias") or session.get("name"),
                "state": session.get("state"),
                "last_signal_at": session.get("last_active"),
            }
            for session in sessions
            if "control-dispatcher" in str(session.get("template", ""))
        ]

        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "factory": {
                "state": factory_state,
                "label": factory_label,
                "running": bool(city.get("running")),
                "usable": bool(health.get("usable")),
                "city": city.get("city_name", "agent-factory"),
            },
            "focus": focus,
            "agents": agent_cards,
            "queue": base["queue"] if isinstance(base["queue"], list) else [],
            "last_delivery": last_delivery,
            "needs_benjamin": needs_benjamin,
            "factory_work": factory_work,
            "infrastructure": infrastructure,
            "warnings": warnings,
            "sources": sources,
            "zero_token_contract": {
                "model_calls": 0,
                "description": "Projection locale déterministe; aucun modèle IA n'est appelé.",
            },
        }


class SnapshotCache:
    def __init__(self, collector: FactoryCollector, ttl: float = 5.0) -> None:
        self.collector = collector
        self.ttl = ttl
        self.lock = threading.Lock()
        self.value: dict[str, Any] | None = None
        self.collected_at = 0.0

    def get(self) -> dict[str, Any]:
        with self.lock:
            if self.value is None or time.monotonic() - self.collected_at >= self.ttl:
                self.value = self.collector.collect()
                self.collected_at = time.monotonic()
            return self.value


def handler_factory(cache: SnapshotCache) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "FactoryCockpit/1"

        def _headers(self, status: int, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self'; "
                "style-src 'self'; script-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/health":
                payload = json.dumps({"ok": True, "model_calls": 0}).encode()
                self._headers(200, "application/json; charset=utf-8")
                self.wfile.write(payload)
                return
            if path == "/api/snapshot":
                payload = json.dumps(cache.get(), ensure_ascii=False).encode()
                self._headers(200, "application/json; charset=utf-8")
                self.wfile.write(payload)
                return
            files = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            }
            if path not in files:
                self._headers(404, "text/plain; charset=utf-8")
                self.wfile.write(b"Not found")
                return
            filename, content_type = files[path]
            self._headers(200, content_type)
            self.wfile.write((STATIC_ROOT / filename).read_bytes())

        def log_message(self, pattern: str, *args: Any) -> None:
            if os.environ.get("FACTORY_COCKPIT_ACCESS_LOG") == "1":
                super().log_message(pattern, *args)

    return Handler


def serve(host: str, port: int) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback Factory cockpit listener")
    cache = SnapshotCache(FactoryCollector())
    server = ThreadingHTTPServer((host, port), handler_factory(cache))
    print(f"Factory cockpit listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8383)
    subparsers.add_parser("snapshot")
    args = parser.parse_args()
    if args.command == "snapshot":
        print(json.dumps(FactoryCollector().collect(), ensure_ascii=False, indent=2))
    else:
        serve(args.host, args.port)


if __name__ == "__main__":
    main()
