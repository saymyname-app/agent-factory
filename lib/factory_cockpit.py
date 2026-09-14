#!/usr/bin/env python3
"""Zero-model monitoring projection and explicit human-to-Mayor cockpit bridge."""

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
    def __init__(self, cwd: Path = ROOT, timeout: int = 20) -> None:
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


def _is_internal_bead(bead: dict[str, Any]) -> bool:
    labels = {str(label) for label in bead.get("labels", [])}
    metadata = _metadata(bead)
    issue_type = str(bead.get("issue_type", ""))
    if issue_type in {"session", "molecule", "convoy", "gate"}:
        return True
    if "coordination" in labels or "gc:session" in labels or "order-tracking" in labels:
        return True
    if any(label == "exec" or label.startswith("order-run:") for label in labels):
        return True
    if str(metadata.get("gc.synthetic", "")).lower() == "true":
        return True
    if metadata.get("gc.kind") in {"workflow", "workflow-finalize", "wisp"}:
        return True
    return False


def _product_bead(bead: dict[str, Any], store: str, current_id: str | None) -> dict[str, Any] | None:
    if _is_internal_bead(bead):
        return None
    labels = {str(label) for label in bead.get("labels", [])}
    metadata = _metadata(bead)
    product_markers = {"product-goal", "roadmap", "product-queue", "jit"}
    if not (
        labels & product_markers
        or metadata.get("gc.product_goal")
        or metadata.get("gc.queue_product")
        or bead.get("id") == current_id
    ):
        return None

    status = str(bead.get("status", "unknown"))
    queue_state = metadata.get("gc.queue_state")
    if bead.get("id") == current_id:
        state = "current"
        state_label = "Objectif actuel"
    elif status == "blocked":
        state = "blocked"
        state_label = "Bloqué"
    elif "product-queue" in labels and queue_state == "paused":
        state = "paused"
        state_label = "En pause"
    elif "product-queue" in labels:
        state = "queued"
        state_label = "Dans la file"
    elif status == "closed":
        state = "delivered"
        state_label = "Livré"
    elif status == "in_progress":
        state = "active"
        state_label = "En cours"
    elif "product-goal" in labels or "roadmap" in labels:
        state = "planned"
        state_label = "Objectif produit"
    else:
        state = "ready"
        state_label = "Prêt"

    if "product-queue" in labels:
        kind = "Candidat"
    elif "product-goal" in labels or "roadmap" in labels:
        kind = "Objectif"
    else:
        kind = "Livraison"
    product = metadata.get("gc.queue_product") or "SayMyName"
    if isinstance(product, str):
        product = product.replace("saymyname", "SayMyName")
    return {
        "id": bead.get("id"),
        "title": bead.get("title") or "Travail produit sans titre",
        "product": product,
        "store": store,
        "kind": kind,
        "state": state,
        "state_label": state_label,
        "urgency": metadata.get("gc.queue_urgency"),
        "priority": bead.get("priority"),
        "updated_at": bead.get("closed_at") or bead.get("updated_at") or bead.get("created_at"),
        "pr": metadata.get("gc.pr_number") or metadata.get("gc.pr"),
        "ci": metadata.get("gc.postmerge_ci_conclusion") or metadata.get("gc.ci_conclusion"),
    }


def _sort_product_work(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state_order = {
        "current": 0,
        "active": 1,
        "blocked": 2,
        "ready": 3,
        "queued": 4,
        "paused": 5,
        "planned": 6,
        "delivered": 7,
    }
    def time_key(item: dict[str, Any]) -> float:
        value = item.get("updated_at")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = parsed.timestamp()
        except (TypeError, ValueError):
            timestamp = 0
        return -timestamp if item.get("state") == "delivered" else timestamp

    return sorted(
        items,
        key=lambda item: (
            state_order.get(str(item.get("state")), 99),
            item.get("priority") if isinstance(item.get("priority"), int) else 9,
            time_key(item),
        ),
    )


def _decision_aids(
    factory_ok: bool,
    warnings: list[str],
    focus: dict[str, Any],
    queue: list[dict[str, Any]],
    product_work: list[dict[str, Any]],
    needs_benjamin: str | None,
    last_delivery: dict[str, Any],
) -> list[dict[str, str]]:
    advice: list[dict[str, str]] = []
    if not factory_ok:
        advice.append({
            "severity": "critical",
            "title": "L'usine ne répond pas correctement",
            "explanation": "Le contrôleur ou sa santé n'est pas confirmé.",
            "action": "Demander au Mayor de diagnostiquer la Factory en lecture seule.",
            "prompt": "Diagnostique pourquoi la Factory n'est pas utilisable, sans rien modifier, et donne-moi la prochaine action sûre.",
        })
    if warnings:
        advice.append({
            "severity": "warning",
            "title": "La visibilité est partielle",
            "explanation": "Au moins une source locale n'a pas répondu; le résumé peut être incomplet.",
            "action": "Consulter les détails techniques ou demander un diagnostic au Mayor.",
            "prompt": "Explique les sources du cockpit actuellement indisponibles et ce qu'il faut vérifier, sans rien modifier.",
        })
    if needs_benjamin:
        advice.append({
            "severity": "decision",
            "title": "Une décision de Benjamin est nécessaire",
            "explanation": needs_benjamin,
            "action": "Répondre au point de décision avant de poursuivre la livraison.",
            "prompt": f"Explique-moi simplement cette décision, recommande une option et ses conséquences : {needs_benjamin}",
        })
    blocked = [item for item in product_work if item.get("state") == "blocked"]
    if blocked:
        advice.append({
            "severity": "warning",
            "title": f"{len(blocked)} travail produit bloqué",
            "explanation": "Un blocage empêche au moins un résultat produit d'avancer.",
            "action": "Demander au Mayor la cause et la plus petite action de déblocage.",
            "prompt": "Quels travaux produit sont bloqués, pourquoi, et quelle est la plus petite action nécessaire de ma part ?",
        })
    if focus.get("state") == "waiting" and focus.get("steps", {}).get("complete"):
        advice.append({
            "severity": "warning",
            "title": "Le code est terminé mais la livraison reste à finaliser",
            "explanation": "Les étapes de réalisation sont finies; le Mayor doit encore publier, vérifier ou clôturer.",
            "action": "Demander au Mayor de confirmer le blocage avant toute relance.",
            "prompt": f"Où en est la finalisation de « {focus.get('title')} » ? Explique le blocage éventuel et termine seulement les étapes déjà autorisées.",
        })
    if focus.get("state") == "idle" and not queue:
        advice.append({
            "severity": "info",
            "title": "La production produit n'a plus de prochain résultat",
            "explanation": "L'infrastructure peut rester allumée, mais aucun nouveau travail produit ne démarrera.",
            "action": "Ajouter ou choisir un prochain résultat produit.",
            "prompt": "Propose-moi les trois prochains résultats produit les plus utiles, sans créer de Bead ni lancer de travail.",
        })
    eligible_queue = [item for item in queue if item.get("state") != "paused"]
    if focus.get("state") == "idle" and eligible_queue:
        next_title = eligible_queue[0].get("title", "le premier candidat")
        advice.append({
            "severity": "info",
            "title": "Un prochain résultat est prêt dans la file",
            "explanation": f"L'usine est au repos; le prochain candidat éligible est « {next_title} ».",
            "action": "Aucune action immédiate; demander au Mayor seulement si cet état persiste.",
            "prompt": f"L'usine est au repos alors que « {next_title} » est premier candidat. Est-ce une transition normale ou faut-il agir ? Ne lance rien sans autorité explicite.",
        })
    if last_delivery.get("ci") and last_delivery.get("ci") != "success":
        advice.append({
            "severity": "critical",
            "title": "La dernière preuve CI n'est pas verte",
            "explanation": f"Conclusion observée : {last_delivery.get('ci')}.",
            "action": "Ne pas considérer la livraison comme saine avant diagnostic.",
            "prompt": "Diagnostique la dernière CI non verte et dis-moi si la livraison doit être corrigée ou annulée.",
        })
    if not advice:
        advice.append({
            "severity": "ok",
            "title": "Tout est cohérent pour l'instant",
            "explanation": "L'usine répond, aucune décision ni anomalie visible ne demande ton intervention.",
            "action": "Aucune action nécessaire.",
            "prompt": "Donne-moi un résumé très court de la santé actuelle de l'usine et du prochain jalon.",
        })
    return advice


class FactoryCollector:
    def __init__(self, runner: Any | None = None, gas_city: Any | None = None) -> None:
        self.runner = runner or CommandRunner()
        self.gas_city = gas_city or GasCityReader(timeout=15)

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
        city_rigs = (
            base["factory"].get("rigs", [])
            if isinstance(base["factory"], dict)
            and isinstance(base["factory"].get("rigs"), list)
            else []
        )
        product_commands: list[tuple[str, tuple[str, ...]]] = [
            (
                "city",
                (
                    "bd",
                    "list",
                    "--all",
                    "--label-any",
                    "product-goal,roadmap,product-queue,jit",
                    "--limit",
                    "0",
                    "--json",
                ),
            )
        ]
        for rig in city_rigs:
            rig_name = rig.get("name") if isinstance(rig, dict) else None
            if rig_name:
                product_commands.append(
                    (
                        str(rig_name),
                        (
                            "gc",
                            "bd",
                            "--rig",
                            str(rig_name),
                            "list",
                            "--all",
                            "--label-any",
                            "product-goal,roadmap,product-queue,jit",
                            "--limit",
                            "0",
                            "--json",
                        ),
                    )
                )
        with ThreadPoolExecutor(max_workers=4) as pool:
            product_reads = {
                store: pool.submit(
                    read,
                    f"product_work:{store}",
                    lambda command=command: self.runner.json(*command),
                    [],
                )
                for store, command in product_commands
            }
            product_sources = {
                store: future.result() for store, future in product_reads.items()
            }
        product_by_id: dict[str, dict[str, Any]] = {}
        for store, beads in product_sources.items():
            if not isinstance(beads, list):
                continue
            for bead in beads:
                if not isinstance(bead, dict):
                    continue
                item = _product_bead(bead, store, current_id)
                if item and item.get("id"):
                    product_by_id[str(item["id"])] = item
        product_work = _sort_product_work(list(product_by_id.values()))

        workflow_id = (
            _meaningful(
                current_meta.get("gc.current_workflow")
                or coordination_meta.get("gc.current_workflow")
            )
            if current
            else None
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
            maintenance = str(session.get("template", "")).startswith("bd.dog")
            objective = (
                focus["title"]
                if is_product_worker
                else "Maintenir la santé du magasin de tâches"
                if maintenance
                else _human_objective(session.get("title"))
            )
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
        queue = base["queue"] if isinstance(base["queue"], list) else []
        decision_aids = _decision_aids(
            factory_ok,
            warnings,
            focus,
            queue,
            product_work,
            needs_benjamin,
            last_delivery,
        )

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
            "queue": queue,
            "product_work": product_work,
            "decision_aids": decision_aids,
            "last_delivery": last_delivery,
            "needs_benjamin": needs_benjamin,
            "factory_work": factory_work,
            "infrastructure": infrastructure,
            "warnings": warnings,
            "sources": sources,
            "zero_token_contract": {
                "model_calls": 0,
                "description": "Surveillance et conseils locaux : 0 appel de modèle. Un message explicitement envoyé au Mayor peut consommer des tokens.",
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


class MayorBridge:
    PREFIX = "[Cockpit Benjamin] "

    def __init__(self, runner: Any | None = None, gas_city: Any | None = None) -> None:
        self.runner = runner or CommandRunner()
        self.gas_city = gas_city or GasCityReader(timeout=15)
        self.lock = threading.Lock()
        self.last_submit = 0.0

    def submit(self, message: Any, intent: Any = "question") -> dict[str, Any]:
        if not isinstance(message, str):
            raise ValueError("Le message doit être du texte.")
        message = message.strip()
        if not message or len(message) > 4000 or "\x00" in message:
            raise ValueError("Le message doit contenir entre 1 et 4000 caractères.")
        intent_map = {"question": "default", "follow_up": "follow_up"}
        if intent not in intent_map:
            raise ValueError("Seuls une question ou un suivi non interruptif sont autorisés.")
        with self.lock:
            now = time.monotonic()
            if now - self.last_submit < 5:
                raise RuntimeError("Attends cinq secondes avant un nouvel envoi.")
            result = self.runner.json(
                "gc",
                "session",
                "submit",
                "mayor",
                f"{self.PREFIX}{message}",
                "--intent",
                intent_map[intent],
                "--json",
            )
            self.last_submit = now
        return {
            "accepted": True,
            "intent": intent,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "delivery": result.get("delivery") if isinstance(result, dict) else None,
        }

    def conversation(self) -> dict[str, Any]:
        sessions = self.runner.json("gc", "session", "list", "--json")
        session_items = sessions.get("sessions", []) if isinstance(sessions, dict) else []
        mayor = next(
            (session for session in session_items if session.get("alias") == "mayor"),
            None,
        )
        if not mayor or not mayor.get("id"):
            raise SourceError("La session Mayor est indisponible.")
        transcript = self.gas_city.json(
            f"/v0/city/agent-factory/session/{quote(str(mayor['id']), safe='')}/transcript"
        )
        turns = transcript.get("turns", []) if isinstance(transcript, dict) else []
        cockpit_indices = [
            index
            for index, turn in enumerate(turns)
            if turn.get("role") == "user"
            and str(turn.get("text", "")).startswith(self.PREFIX)
        ]
        if not cockpit_indices:
            return {"session": "Mayor", "state": mayor.get("state"), "messages": []}
        start = cockpit_indices[-min(3, len(cockpit_indices))]
        messages = []
        capturing = False
        for turn in turns[start:]:
            role = turn.get("role")
            text = str(turn.get("text", "")).strip()
            if role == "user":
                if not text.startswith(self.PREFIX):
                    capturing = False
                    continue
                capturing = True
                text = text[len(self.PREFIX) :].strip()
                visible_role = "Benjamin"
            elif role == "assistant":
                if not capturing or not text or text in {"[thinking]", "[exec]"}:
                    continue
                visible_role = "Mayor"
            else:
                continue
            messages.append(
                {
                    "role": visible_role,
                    "text": text[:5000],
                    "truncated": len(text) > 5000,
                    "timestamp": turn.get("timestamp"),
                }
            )
        return {
            "session": "Mayor",
            "state": mayor.get("state"),
            "messages": messages[-12:],
        }


def handler_factory(
    cache: SnapshotCache, mayor_bridge: MayorBridge | None = None
) -> type[BaseHTTPRequestHandler]:
    bridge = mayor_bridge or MayorBridge()

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

        def _json_response(self, status: int, value: Any) -> None:
            payload = json.dumps(value, ensure_ascii=False).encode()
            self._headers(status, "application/json; charset=utf-8")
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/health":
                self._json_response(
                    200, {"ok": True, "model_calls": 0, "monitoring_model_calls": 0}
                )
                return
            if path == "/api/snapshot":
                self._json_response(200, cache.get())
                return
            if path == "/api/mayor/conversation":
                try:
                    self._json_response(200, bridge.conversation())
                except SourceError as exc:
                    self._json_response(503, {"error": str(exc)})
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

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/mayor/message":
                self._json_response(404, {"error": "Not found"})
                return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if not origin or not host or origin != f"http://{host}":
                self._json_response(403, {"error": "Origine refusée."})
                return
            if self.headers.get("X-Factory-Cockpit") != "human-message":
                self._json_response(403, {"error": "Confirmation de cockpit absente."})
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self._json_response(415, {"error": "JSON requis."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 8192:
                self._json_response(413, {"error": "Message trop grand ou vide."})
                return
            try:
                request = json.loads(self.rfile.read(length))
                result = bridge.submit(request.get("message"), request.get("intent", "question"))
                self._json_response(202, result)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "JSON invalide."})
            except ValueError as exc:
                self._json_response(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json_response(429, {"error": str(exc)})
            except SourceError as exc:
                self._json_response(503, {"error": str(exc)})

        def log_message(self, pattern: str, *args: Any) -> None:
            if os.environ.get("FACTORY_COCKPIT_ACCESS_LOG") == "1":
                super().log_message(pattern, *args)

    return Handler


def serve(host: str, port: int) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback Factory cockpit listener")
    cache = SnapshotCache(FactoryCollector())
    server = ThreadingHTTPServer((host, port), handler_factory(cache, MayorBridge()))
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
