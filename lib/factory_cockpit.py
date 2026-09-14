#!/usr/bin/env python3
"""Zero-model monitoring plus explicit human-to-PO and human-to-Mayor bridges."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "ui" / "factory-cockpit"
PRODUCT_CONFIG_PATH = Path(os.environ.get(
    "FACTORY_COCKPIT_PRODUCT_CONFIG", ROOT / "config" / "products" / "saymyname.json"
))
REMOTE_ACCESS_FILE = ROOT / ".gc" / "runtime" / "factory-cockpit-remote-url"
COORDINATION_BEAD = os.environ.get("FACTORY_COCKPIT_COORDINATION_BEAD", "af-1vr4")
GAS_CITY_URL = os.environ.get("FACTORY_COCKPIT_GAS_CITY_URL", "http://127.0.0.1:8372")


class SourceError(RuntimeError):
    pass


class ConflictError(SourceError):
    """A bounded mutation lost a lock or source-state race."""


def _repo_path(value: Any, field: str, root: Path = ROOT) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"Le chemin {field} est invalide.")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SourceError(f"Le chemin {field} doit être relatif au dépôt Factory.")
    resolved = (root / candidate).resolve()
    repository = root.resolve()
    if resolved == repository or repository not in resolved.parents:
        raise SourceError(f"Le chemin {field} doit rester dans le dépôt Factory.")
    return resolved


def load_product_config(path: Path = PRODUCT_CONFIG_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceError(f"Configuration produit invalide: {exc}") from exc
    required = {
        "slug", "name", "strategy", "decisions", "po_workspace",
        "queue_command", "capabilities", "relations", "project_inventory",
        "design_governance", "business_objectives", "view_inventory",
        "delivery_workflow", "product_reference",
    }
    required.add("journeys")
    if value.get("schema_version") != 2 or not required.issubset(value):
        raise SourceError("Configuration produit incomplète ou version non prise en charge.")
    if not re.fullmatch(r"[a-z0-9-]+", str(value["slug"])) or not str(value["name"]).strip():
        raise SourceError("Identité de produit invalide.")
    if not isinstance(value["queue_command"], list) or not value["queue_command"] or not all(
        isinstance(part, str) and part for part in value["queue_command"]
    ):
        raise SourceError("Commande de file produit invalide.")
    if not isinstance(value.get("queue_mutation_command"), list) or not value["queue_mutation_command"] or not all(
        isinstance(part, str) and part for part in value["queue_mutation_command"]
    ):
        raise SourceError("Commande de mutation de file produit invalide.")
    if not isinstance(value["capabilities"], list) or not isinstance(value["relations"], list):
        raise SourceError("Graphe produit invalide.")
    references = value.get("product_reference")
    if not isinstance(references, list) or not references:
        raise SourceError("Références produit manquantes.")
    reference_ids: set[str] = set()
    reference_paths: set[Path] = set()
    for item in references:
        if not isinstance(item, dict) or not {
            "id", "title", "summary", "status", "status_label", "sources",
        }.issubset(item):
            raise SourceError("Référence produit incomplète.")
        reference_id = item.get("id")
        if not isinstance(reference_id, str) or not reference_id or reference_id in reference_ids:
            raise SourceError("Identifiant de référence produit invalide ou dupliqué.")
        sources = item.get("sources")
        if not isinstance(sources, list) or not sources:
            raise SourceError(f"La référence {reference_id} doit configurer au moins une source.")
        for source in sources:
            if not isinstance(source, dict) or not {"path", "sections"}.issubset(source):
                raise SourceError(f"Source incomplète pour la référence {reference_id}.")
            sections = source.get("sections")
            if not isinstance(sections, list) or not sections or not all(
                isinstance(section, str) and section.strip() for section in sections
            ):
                raise SourceError(f"Sections invalides pour la référence {reference_id}.")
            source["resolved_path"] = _repo_path(
                source.get("path"), f"product_reference.{reference_id}.source"
            )
            reference_paths.add(source["resolved_path"])
        reference_ids.add(reference_id)

    capability_ids: set[str] = set()
    for item in value["capabilities"]:
        if not isinstance(item, dict) or not {
            "id", "title", "area", "roadmap", "source_refs", "decision_refs",
        }.issubset(item):
            raise SourceError("Capacité produit incomplète.")
        if not isinstance(item["id"], str) or not item["id"] or item["id"] in capability_ids:
            raise SourceError("Identifiant de capacité produit invalide ou dupliqué.")
        if not isinstance(item["roadmap"], int) or isinstance(item["roadmap"], bool) or item["roadmap"] < 1:
            raise SourceError("Référence roadmap invalide dans le graphe produit.")
        if not isinstance(item["source_refs"], list) or not set(item["source_refs"]).issubset(reference_ids):
            raise SourceError("Référence documentaire invalide dans le graphe produit.")
        if not isinstance(item["decision_refs"], list) or not all(
            isinstance(title, str) and title for title in item["decision_refs"]
        ):
            raise SourceError("Référence de décision invalide dans le graphe produit.")
        capability_ids.add(item["id"])
    for relation in value["relations"]:
        if not isinstance(relation, list) or len(relation) != 2 or not all(
            endpoint in capability_ids for endpoint in relation
        ):
            raise SourceError("Relation de capacité produit invalide.")
    journey_ids: set[str] = set()
    for item in value["journeys"]:
        if not isinstance(item, dict) or not {
            "id", "title", "detail", "roadmap", "capability_refs", "source_refs", "decision_refs",
        }.issubset(item):
            raise SourceError("Parcours produit incomplet.")
        journey_id = item.get("id")
        if not isinstance(journey_id, str) or not journey_id or journey_id in journey_ids:
            raise SourceError("Identifiant de parcours invalide ou dupliqué.")
        if not isinstance(item["roadmap"], int) or isinstance(item["roadmap"], bool) or item["roadmap"] < 1:
            raise SourceError("Référence roadmap invalide dans un parcours.")
        if not isinstance(item["capability_refs"], list) or not set(item["capability_refs"]).issubset(capability_ids):
            raise SourceError("Référence de capacité invalide dans un parcours.")
        if not isinstance(item["source_refs"], list) or not set(item["source_refs"]).issubset(reference_ids):
            raise SourceError("Référence documentaire invalide dans un parcours.")
        if not isinstance(item["decision_refs"], list) or not all(
            isinstance(title, str) and title for title in item["decision_refs"]
        ):
            raise SourceError("Référence de décision invalide dans un parcours.")
        journey_ids.add(journey_id)
    for field in ("strategy", "decisions", "project_inventory", "design_governance"):
        resolved = _repo_path(value[field], field)
        value[f"{field}_path"] = resolved
    value["reference_paths"] = reference_paths
    return value


def remote_access() -> dict[str, Any]:
    try:
        url = REMOTE_ACCESS_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        url = ""
    if url and re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?/?", url):
        return {"enabled": True, "url": url.rstrip("/"), "mode": "Tailscale Serve", "public": False}
    return {"enabled": False, "url": None, "mode": "loopback seulement", "public": False}


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

    def text(self, *args: str) -> str:
        try:
            return subprocess.run(
                args,
                cwd=self.cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "NO_COLOR": "1"},
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
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


def _human_phase(value: Any) -> str | None:
    raw = str(value or "")
    known = {
        "external-evidence": "Vérification externe : contenu et droits",
        "external-evidence-correction": "Correction des preuves de contenu et de droits",
        "mayor-acceptance-review": "Contrôle final des preuves par le Mayor",
        "implementation": "Réalisation",
        "verification": "Vérification",
        "Read assignment, implement, verify, commit, and close": "L’agent réalise, vérifie et prépare la livraison",
        "Review the implementation and record the verdict": "Un second agent contrôle la livraison",
        "Verify exact-head CI and merge": "Le Mayor vérifie la CI puis fusionne",
    }
    return known.get(raw, _human_objective(raw) if raw and raw != "none" else None)


def _human_product_title(value: Any) -> str:
    raw = str(value or "").strip()
    known = {
        "Deliver public cultural challenge and minimal personal learning home": "Livrer un challenge culturel public et un espace d’apprentissage personnel minimal",
        "Prove one public challenge content and image rights manifest": "Prouver le contenu et les droits d’images d’un premier challenge public",
        "Create and join a participative promotion or event": "Créer et rejoindre une promotion ou un événement participatif",
        "Create an administered organization and import people by CSV": "Créer une organisation administrée et importer ses membres par CSV",
        "Import personal people and choose private memory targets": "Importer ses contacts et choisir ce que l’on veut mémoriser",
        "Publish cultural challenges through a scoped editorial workflow": "Publier des challenges culturels avec un circuit éditorial sûr",
        "Retrieve an authorized person from natural-language clues": "Retrouver une personne autorisée à partir d’indices en langage naturel",
        "Add the first evidence-selected external people connector": "Ajouter le premier connecteur de contacts choisi par les preuves du pilote",
        "Support a federated organization with governed workspaces": "Prendre en charge une organisation fédérée avec des espaces gouvernés",
        "Turn pilot evidence into pricing and launch readiness": "Transformer les preuves du pilote en prix et préparation au lancement",
        "Evidence-based pricing and launch readiness.": "Prix et préparation au lancement fondés sur les preuves.",
        "Natural-language retrieval among authorized people.": "Recherche en langage naturel parmi les personnes autorisées.",
        "First Google or Microsoft connector chosen from pilot evidence.": "Premier connecteur Google ou Microsoft choisi à partir du pilote.",
    }
    return known.get(raw, raw or "Travail produit sans titre")


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


def _product_bead(
    bead: dict[str, Any], store: str, current_id: str | set[str] | None,
    product_name: str = "SayMyName",
) -> dict[str, Any] | None:
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
    is_current = bead.get("id") in current_id if isinstance(current_id, set) else bead.get("id") == current_id
    if is_current:
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
    product = metadata.get("gc.queue_product") or product_name
    if isinstance(product, str):
        product = product.replace("saymyname", "SayMyName")
    return {
        "id": bead.get("id"),
        "title": _human_product_title(bead.get("title")),
        "raw_title": bead.get("title"),
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


def _markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _paragraph(text: str) -> str:
    return re.sub(r"\s+", " ", text.split("\n\n", 1)[0]).strip()


def _anchor(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _clean_markdown_text(value: str) -> str:
    if "\x00" in value or re.search(
        r"(?is)<\s*(script|style|iframe|object|embed|svg|math)\b|\bon[a-z]+\s*=|javascript\s*:|data\s*:\s*text/html",
        value,
    ):
        raise SourceError("La source Markdown contient du contenu actif interdit.")
    return re.sub(r"<[^>]*>", "", value)


def _extract_markdown_section(text: str, wanted: str) -> tuple[int, list[str]]:
    lines = text.splitlines()
    start = -1
    level = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and match.group(2).strip() == wanted:
            start, level = index, len(match.group(1))
            break
    if start < 0:
        raise SourceError(f"Section Markdown introuvable: {wanted}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    selected = lines[start:end]
    if not any(line.strip() for line in selected[1:]):
        raise SourceError(f"Section Markdown vide: {wanted}")
    return level, selected


class ProductReferenceReader:
    """Parse only configured repository Markdown into inert structured blocks."""

    def __init__(self, config: dict[str, Any] | None = None, root: Path = ROOT) -> None:
        self.config = config or load_product_config()
        self.root = root.resolve()
        self.references = {
            str(item["id"]): item for item in self.config.get("product_reference", [])
        }
        self.allowed_paths = {
            Path(source.get("resolved_path") or _repo_path(source.get("path"), "reference", self.root)).resolve()
            for item in self.references.values()
            for source in item.get("sources", [])
        }

    def _target(self, source_path: Path, raw_href: str) -> dict[str, Any]:
        href = raw_href.strip()
        parsed = urlparse(href)
        if (
            not href
            or parsed.scheme
            or parsed.netloc
            or href.startswith(("/", "\\", "//"))
            or ".." in Path(parsed.path or ".").parts
        ):
            raise SourceError(f"Lien Markdown non autorisé: {raw_href}")
        target = source_path if not parsed.path else (source_path.parent / parsed.path).resolve()
        if target not in self.allowed_paths:
            raise SourceError(f"Le lien Markdown sort des sources configurées: {raw_href}")
        fragment = parsed.fragment.strip()
        candidates = []
        for reference in self.references.values():
            for configured in reference.get("sources", []):
                configured_path = Path(
                    configured.get("resolved_path")
                    or _repo_path(configured.get("path"), "reference", self.root)
                ).resolve()
                if configured_path != target:
                    continue
                headings = configured.get("sections", [])
                if not fragment or any(_anchor(heading) == _anchor(fragment) for heading in headings):
                    candidates.append((reference, headings))
        if not candidates:
            raise SourceError(f"La cible du lien Markdown n’est pas configurée: {raw_href}")
        reference, headings = candidates[0]
        heading = next(
            (item for item in headings if fragment and _anchor(item) == _anchor(fragment)),
            headings[0],
        )
        return {
            "reference_id": reference["id"],
            "section_anchor": self._section_anchor(target, heading),
        }

    def _inlines(self, value: str, source_path: Path) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        position = 0
        for match in re.finditer(r"\[([^\]\n]+)\]\(([^)\n]+)\)", value):
            prefix = _clean_markdown_text(value[position:match.start()])
            if prefix:
                parts.append({"type": "text", "text": prefix})
            label = _clean_markdown_text(match.group(1)).strip()
            if not label:
                raise SourceError("Un lien Markdown doit avoir un libellé.")
            parts.append({"type": "link", "text": label, **self._target(source_path, match.group(2))})
            position = match.end()
        suffix = _clean_markdown_text(value[position:])
        if suffix:
            parts.append({"type": "text", "text": suffix})
        return parts or [{"type": "text", "text": ""}]

    @staticmethod
    def _section_anchor(source_path: Path, heading: str) -> str:
        return f"reference-{_anchor(source_path.stem)}-{_anchor(heading)}"

    def _blocks(self, lines: list[str], source_path: Path) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        index = 0
        while index < len(lines):
            raw = lines[index]
            if not raw.strip():
                index += 1
                continue
            fence = re.match(r"^\s*```([^`]*)$", raw)
            if fence:
                language = _clean_markdown_text(fence.group(1)).strip()
                index += 1
                code: list[str] = []
                while index < len(lines) and not re.match(r"^\s*```\s*$", lines[index]):
                    code.append(lines[index])
                    index += 1
                if index >= len(lines):
                    raise SourceError("Bloc de code Markdown non fermé.")
                blocks.append({"type": "code", "language": language, "text": "\n".join(code)})
                index += 1
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw)
            if heading:
                text = _clean_markdown_text(heading.group(2)).strip()
                blocks.append({
                    "type": "heading", "level": len(heading.group(1)), "text": text,
                    "anchor": self._section_anchor(source_path, text),
                })
                index += 1
                continue
            if (
                "|" in raw
                and index + 1 < len(lines)
                and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1])
            ):
                def cells(line: str) -> list[str]:
                    return [_clean_markdown_text(cell).strip() for cell in line.strip().strip("|").split("|")]

                headers = cells(raw)
                index += 2
                rows = []
                while index < len(lines) and "|" in lines[index] and lines[index].strip():
                    rows.append(cells(lines[index]))
                    index += 1
                blocks.append({"type": "table", "headers": headers, "rows": rows})
                continue
            list_match = re.match(r"^\s*(?:[-*+]|(\d+)\.)\s+(.+)$", raw)
            if list_match:
                ordered = bool(list_match.group(1))
                items = []
                while index < len(lines):
                    item = re.match(r"^\s*(?:[-*+]|(\d+)\.)\s+(.+)$", lines[index])
                    if not item or bool(item.group(1)) != ordered:
                        break
                    items.append(self._inlines(item.group(2), source_path))
                    index += 1
                blocks.append({"type": "list", "ordered": ordered, "items": items})
                continue
            paragraph = [raw.strip()]
            index += 1
            while index < len(lines) and lines[index].strip():
                candidate = lines[index]
                if re.match(r"^(#{1,6})\s+|^\s*```|^\s*(?:[-*+]|\d+\.)\s+", candidate):
                    break
                if "|" in candidate and index + 1 < len(lines) and re.match(
                    r"^\s*\|?\s*:?-{3,}", lines[index + 1]
                ):
                    break
                paragraph.append(candidate.strip())
                index += 1
            blocks.append({"type": "paragraph", "inlines": self._inlines(" ".join(paragraph), source_path)})
        return blocks

    def get(self, reference_id: Any) -> dict[str, Any]:
        reference_id = _safe_identifier(str(reference_id or ""))
        reference = self.references.get(reference_id)
        if not reference:
            raise ValueError("Référence produit inconnue.")
        documents = []
        for source in reference["sources"]:
            path = Path(source.get("resolved_path") or _repo_path(source["path"], "reference", self.root)).resolve()
            if path not in self.allowed_paths or not path.is_file():
                raise SourceError(f"Source Markdown configurée indisponible: {source['path']}")
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise SourceError(f"Lecture Markdown impossible pour {source['path']}: {exc}") from exc
            sections = []
            for heading in source["sections"]:
                _, lines = _extract_markdown_section(text, heading)
                blocks = self._blocks(lines, path)
                if not blocks:
                    raise SourceError(f"Section Markdown vide: {heading}")
                sections.append({
                    "heading": heading,
                    "anchor": self._section_anchor(path, heading),
                    "blocks": blocks,
                })
            stat = path.stat()
            documents.append({
                "configured_path": source["path"],
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "sections": sections,
            })
        return {
            "id": reference_id,
            "title": reference["title"],
            "summary": reference["summary"],
            "status": reference["status"],
            "status_label": reference["status_label"],
            "state": "ready",
            "documents": documents,
            "model_calls": 0,
        }

    def summary(self, reference_id: str) -> dict[str, Any]:
        reference = self.references[reference_id]
        base = {
            "id": reference_id, "title": reference["title"], "summary": reference["summary"],
            "status": reference["status"], "status_label": reference["status_label"],
            "configured_paths": [source["path"] for source in reference["sources"]],
        }
        try:
            document = self.get(reference_id)
            timestamps = [source["modified_at"] for source in document["documents"]]
            return {**base, "state": "ready", "freshness": max(timestamps), "error": None}
        except (SourceError, ValueError) as exc:
            return {**base, "state": "source_error", "freshness": None, "error": _redact(str(exc))[:1000]}


class ProductMemory:
    """Deterministic projection of the Git-versioned PO memory."""

    ROADMAP_STAGE = ["now", "next", "next", "later", "later", "later", "evidence", "later", "evidence"]

    def __init__(
        self,
        strategy: Path | None = None,
        decisions: Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.strict_relationships = strategy is None and decisions is None
        self.config = config or load_product_config()
        self.strategy = strategy or self.config["strategy_path"]
        self.decisions = decisions or self.config["decisions_path"]
        self.project_inventory = self.config["project_inventory_path"]
        self.design_governance = self.config["design_governance_path"]
        self.reference_reader = ProductReferenceReader(self.config)

    def _inventory_freshness(self) -> dict[str, Any]:
        reviewed = self.project_inventory.stat().st_mtime
        workspace = Path(str(self.config["po_workspace"])).resolve()
        observed = []
        for relative in self.config.get("inventory_watch", []):
            target = (workspace / str(relative)).resolve()
            if target != workspace and workspace not in target.parents:
                continue
            try:
                observed.append(target.stat().st_mtime)
            except OSError:
                continue
        latest = max(observed, default=None)
        return {
            "state": "review_due" if latest and latest > reviewed else "current",
            "label": "Revue à actualiser" if latest and latest > reviewed else "Revue à jour",
            "model_calls": 0,
        }

    def collect(self) -> dict[str, Any]:
        strategy = self.strategy.read_text(encoding="utf-8")
        decisions = self.decisions.read_text(encoding="utf-8")
        roadmap_raw = _markdown_section(strategy, "Product roadmap").split("\n\nItems", 1)[0]
        roadmap = []
        for index, match in enumerate(re.finditer(r"(?ms)^\d+\.\s+(.*?)(?=^\d+\.\s|\Z)", roadmap_raw)):
            title = _human_product_title(re.sub(r"\s+", " ", match.group(1)).strip())
            roadmap.append({
                "id": f"roadmap-{index + 1}",
                "order": index + 1,
                "title": title,
                "stage": self.ROADMAP_STAGE[index] if index < len(self.ROADMAP_STAGE) else "later",
                "source": "PRODUCT_STRATEGY.md · Product roadmap",
            })

        accepted_raw = _markdown_section(decisions, "Accepted")
        accepted = [
            {
                "id": f"accepted-{hashlib.sha256(match.group(1).strip().encode('utf-8')).hexdigest()[:12]}",
                "title": match.group(1).strip(),
                "status": "accepted",
                "detail": _paragraph(match.group(2)),
                "source": "DECISIONS.md · Accepted",
            }
            for index, match in enumerate(re.finditer(
                r"(?ms)^###\s+\d{4}-\d{2}-\d{2}\s+—\s+(.*?)\s*$\n(.*?)(?=^### |\Z)", accepted_raw
            ))
        ]
        domain_names = {"Enterprise": "enterprise", "Product": "product", "Project": "project"}
        pending = []
        open_raw = _markdown_section(decisions, "Open")
        for heading, body in re.findall(r"(?ms)^###\s+(.+?)\s*$\n(.*?)(?=^### |\Z)", open_raw):
            domain = domain_names.get(heading.strip())
            if not domain:
                continue
            for raw in re.findall(r"(?m)^-\s+(.+)$", body):
                match = re.match(r"\*\*(.+?)\*\*\s+—\s+(.+)", raw.strip())
                title, detail = (match.group(1), match.group(2)) if match else (raw.strip(), "Décision volontairement laissée à Benjamin.")
                pending.append({
                    "id": f"pending-{domain}-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:12]}",
                    "title": title,
                    "status": "pending",
                    "domain": domain,
                    "detail": detail,
                    "source": f"DECISIONS.md · Open · {heading.strip()}",
                })
        decisions_projected = pending + accepted
        decisions_by_title = {item["title"]: item for item in decisions_projected}
        configured_decisions = {
            title
            for collection in (self.config.get("capabilities", []), self.config.get("journeys", []))
            for item in collection
            if isinstance(item, dict)
            for title in item.get("decision_refs", [])
        }
        missing_decisions = sorted(configured_decisions - decisions_by_title.keys())
        if missing_decisions and self.strict_relationships:
            raise SourceError(
                "Référence de décision introuvable: " + ", ".join(missing_decisions)
            )

        references = [
            self.reference_reader.summary(reference_id)
            for reference_id in self.reference_reader.references
        ]
        reference_by_id = {item["id"]: item for item in references}
        capabilities = []
        stage_status = {item["order"]: item["stage"] for item in roadmap}
        for item in self.config.get("capabilities", []):
            if not isinstance(item, dict):
                continue
            capabilities.append({
                **item,
                "status": stage_status.get(item.get("roadmap"), "later"),
                "sources": [reference_by_id[reference] for reference in item["source_refs"]],
                "decisions": [decisions_by_title[title] for title in item["decision_refs"] if title in decisions_by_title],
            })
        capability_by_id = {item["id"]: item for item in capabilities}
        for capability in capabilities:
            capability["relations"] = [
                {
                    "direction": "requires" if target == capability["id"] else "supports",
                    "id": source if target == capability["id"] else target,
                    "title": capability_by_id[source if target == capability["id"] else target]["title"],
                }
                for source, target in self.config.get("relations", [])
                if capability["id"] in {source, target}
            ]
        journeys = []
        for item in self.config.get("journeys", []):
            journeys.append({
                **item,
                "status": stage_status.get(item.get("roadmap"), "later"),
                "capabilities": [capability_by_id[reference] for reference in item["capability_refs"]],
                "sources": [reference_by_id[reference] for reference in item["source_refs"]],
                "decisions": [decisions_by_title[title] for title in item["decision_refs"] if title in decisions_by_title],
            })
        for decision in decisions_projected:
            decision["capabilities"] = [
                {"id": item["id"], "title": item["title"]}
                for item in capabilities if decision["title"] in item["decision_refs"]
            ]
            decision["journeys"] = [
                {"id": item["id"], "title": item["title"]}
                for item in journeys if decision["title"] in item["decision_refs"]
            ]
            decision["roadmap"] = sorted({
                item["roadmap"]
                for item in capabilities + journeys if decision["title"] in item["decision_refs"]
            })
            decision["sources"] = [
                reference_by_id[reference]
                for reference in dict.fromkeys(
                    reference
                    for item in capabilities + journeys
                    if decision["title"] in item["decision_refs"]
                    for reference in item["source_refs"]
                )
            ]
        for outcome in roadmap:
            outcome["capabilities"] = [
                {"id": item["id"], "title": item["title"]}
                for item in capabilities if item["roadmap"] == outcome["order"]
            ]
            outcome["journeys"] = [
                {"id": item["id"], "title": item["title"]}
                for item in journeys if item["roadmap"] == outcome["order"]
            ]
            outcome["decisions"] = [
                {"id": item["id"], "title": item["title"], "status": item["status"]}
                for item in decisions_projected if outcome["order"] in item["roadmap"]
            ]
        business_objectives = [
            {**item, "status": stage_status.get(item.get("roadmap"), "later")}
            for item in self.config.get("business_objectives", [])
            if isinstance(item, dict)
        ]
        return {
            "product": self.config["name"],
            "slug": self.config["slug"],
            "thesis": _paragraph(_markdown_section(strategy, "Product thesis")),
            "roadmap": roadmap,
            "decisions": decisions_projected,
            "project_graph": {
                "nodes": capabilities,
                "edges": self.config.get("relations", []),
            },
            "journeys": journeys,
            "business": {
                "north_star": "Prouver que SayMyName aide une personne à mieux retrouver les gens qu’elle a choisi de mémoriser, puis trouver un canal et un acheteur répétables.",
                "objectives": business_objectives,
            },
            "view_inventory": self.config.get("view_inventory", []),
            "product_reference": references,
            "inventory_freshness": self._inventory_freshness(),
            "delivery_workflow": self.config.get("delivery_workflow", []),
            "updated_at": datetime.fromtimestamp(
                max(
                    self.strategy.stat().st_mtime,
                    self.decisions.stat().st_mtime,
                    self.project_inventory.stat().st_mtime,
                    self.design_governance.stat().st_mtime,
                ), timezone.utc
            ).isoformat(),
            "sources": [
                "docs/products/saymyname/PRODUCT_STRATEGY.md",
                "docs/products/saymyname/DECISIONS.md",
                "docs/products/saymyname/PROJECT_INVENTORY.md",
                "docs/products/saymyname/DESIGN_GOVERNANCE.md",
            ],
        }


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value or ""):
        raise ValueError("Identifiant invalide.")
    return value


def _redact(text: str) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    patterns = [
        r"(?i)(api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]\s*[^\s]+",
        r"(?i)bearer\s+[A-Za-z0-9._-]+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "[secret masqué]", text)
    return text


class DetailReader:
    def __init__(self, runner: Any | None = None, gas_city: Any | None = None) -> None:
        self.runner = runner or CommandRunner(timeout=15)
        self.gas_city = gas_city or GasCityReader(timeout=15)

    def item(self, store: str, item_id: str) -> dict[str, Any]:
        store, item_id = _safe_identifier(store), _safe_identifier(item_id)
        command = ("bd", "show", item_id, "--json") if store == "city" else (
            "gc", "bd", "--rig", store, "show", item_id, "--json"
        )
        bead = _single(self.runner.json(*command))
        if not bead:
            raise SourceError("Travail introuvable.")
        metadata = _metadata(bead)
        allowed_metadata = {
            key: value for key, value in metadata.items()
            if key.startswith("gc.") and not re.search(r"(?i)secret|token|password|key", key)
        }
        relations = []
        for field in ("dependencies", "dependents"):
            for relation in bead.get(field, []) if isinstance(bead.get(field), list) else []:
                if isinstance(relation, dict):
                    relations.append({
                        "direction": field,
                        "id": relation.get("id") or relation.get("issue_id") or relation.get("depends_on_id"),
                        "title": relation.get("title"),
                        "type": relation.get("dependency_type") or relation.get("type"),
                    })
        return {
            "id": bead.get("id"), "store": store, "title": _human_product_title(bead.get("title")),
            "status": bead.get("status"), "priority": bead.get("priority"),
            "type": bead.get("issue_type"), "description": bead.get("description") or bead.get("body"),
            "acceptance": bead.get("acceptance_criteria") or bead.get("acceptance"),
            "notes": str(bead.get("notes") or "")[-12000:], "labels": bead.get("labels", []),
            "assignee": bead.get("assignee"), "created_at": bead.get("created_at"),
            "updated_at": bead.get("updated_at"), "closed_at": bead.get("closed_at"),
            "relations": relations, "metadata": allowed_metadata,
        }

    def agent(self, session_id: str) -> dict[str, Any]:
        session_id = _safe_identifier(session_id)
        payload = self.runner.json("gc", "session", "list", "--json")
        sessions = payload.get("sessions", []) if isinstance(payload, dict) else []
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if not session:
            raise SourceError("Session active introuvable.")
        transcript = self.gas_city.json(
            f"/v0/city/agent-factory/session/{quote(session_id, safe='')}/transcript"
        )
        messages = []
        for turn in transcript.get("turns", []) if isinstance(transcript, dict) else []:
            role, value = turn.get("role"), str(turn.get("text", "")).strip()
            if role not in {"user", "assistant"} or not value or value in {"[thinking]", "[exec]"}:
                continue
            if role == "user" and ("Pool Worker" in value or len(value) > 8000):
                continue
            messages.append({"role": role, "text": _redact(value)[:6000], "timestamp": turn.get("timestamp")})
        try:
            peek = _redact(self.runner.text("gc", "session", "peek", session_id, "--lines", "120"))[-30000:]
        except SourceError:
            peek = "Journal terminal indisponible."
        return {
            "session": {key: session.get(key) for key in (
                "id", "alias", "name", "provider", "state", "created_at", "last_active", "work_dir"
            )},
            "messages": messages[-20:], "activity": peek,
            "privacy": "Sortie locale nettoyée et limitée. Le raisonnement privé interne n'est jamais exposé.",
        }


def _last_matching_json(path: Path, wanted_type: str) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position, remainder = handle.tell(), b""
            while position > 0:
                size = min(65536, position)
                position -= size
                handle.seek(position)
                chunk = handle.read(size) + remainder
                lines = chunk.split(b"\n")
                remainder = lines[0]
                for raw in reversed(lines[1:]):
                    try:
                        value = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if value.get("type") == wanted_type:
                        return value
            if remainder:
                value = json.loads(remainder)
                return value if value.get("type") == wanted_type else None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _compact_tokens(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


class TokenReader:
    """Reads provider-written local telemetry; never calls a model."""

    def __init__(self, runner: Any | None = None, home: Path | None = None) -> None:
        self.runner = runner or CommandRunner(timeout=15)
        self.home = home or Path.home()

    def _codex_usage(self, session_key: str) -> dict[str, Any] | None:
        files = list((self.home / ".codex" / "sessions").glob(f"**/*{session_key}*.jsonl"))
        if not files:
            return None
        record = _last_matching_json(max(files, key=lambda path: path.stat().st_mtime), "token_usage_record")
        usage = ((record or {}).get("payload") or {}).get("thread_token_usage")
        if not isinstance(usage, dict):
            return None
        return {key: _compact_tokens(usage.get(key)) for key in (
            "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"
        )}

    def codex_thread(self, thread_id: Any) -> dict[str, Any] | None:
        """Return provider-written usage for one thread without making a model call."""
        if not isinstance(thread_id, str) or not thread_id:
            return None
        return self._codex_usage(thread_id)

    def _claude_usage(self, work_dir: str, created_at: Any) -> dict[str, Any] | None:
        project_dir = self.home / ".claude" / "projects" / work_dir.replace("/", "-")
        files = list(project_dir.glob("*.jsonl")) if project_dir.is_dir() else []
        if not files:
            return None
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            created = 0
        candidates = [path for path in files if path.stat().st_mtime >= created - 120]
        if not candidates:
            return None
        path = max(candidates, key=lambda item: item.stat().st_mtime)
        usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
        messages = 0
        try:
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                message = value.get("message")
                current = message.get("usage") if isinstance(message, dict) else None
                if not isinstance(current, dict):
                    continue
                messages += 1
                usage["input_tokens"] += _compact_tokens(current.get("input_tokens"))
                usage["cached_input_tokens"] += _compact_tokens(current.get("cache_read_input_tokens")) + _compact_tokens(current.get("cache_creation_input_tokens"))
                usage["output_tokens"] += _compact_tokens(current.get("output_tokens"))
                details = current.get("output_tokens_details")
                if isinstance(details, dict):
                    usage["reasoning_output_tokens"] += _compact_tokens(details.get("thinking_tokens"))
        except OSError:
            return None
        if not messages:
            return None
        usage["total_tokens"] = usage["input_tokens"] + usage["cached_input_tokens"] + usage["output_tokens"]
        return usage

    def collect(self) -> dict[str, Any]:
        sessions_payload = self.runner.json("gc", "session", "list", "--json")
        sessions = sessions_payload.get("sessions", []) if isinstance(sessions_payload, dict) else []
        details, known_total = [], 0
        for session in sessions:
            provider = session.get("provider")
            if provider == "codex" and session.get("session_key"):
                usage = self._codex_usage(str(session["session_key"]))
                if usage:
                    known_total += usage["total_tokens"]
                    details.append({
                        "session_id": session.get("id"), "name": session.get("alias"), "provider": "Codex",
                        "scope": "session Factory", "confidence": "exact", "usage": usage,
                    })
            elif provider == "claude" and session.get("id"):
                usage = self._claude_usage(str(session.get("work_dir") or ""), session.get("created_at"))
                if usage:
                    known_total += usage["total_tokens"]
                    details.append({
                        "session_id": session.get("id"), "name": session.get("alias"), "provider": "Claude",
                        "scope": "session Factory", "confidence": "exact (journal local fournisseur)",
                        "usage": usage,
                    })
                    continue
                try:
                    peek = self.runner.text("gc", "session", "peek", str(session["id"]), "--lines", "8")
                    match = re.search(r"↓\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)\s*tokens", peek)
                except SourceError:
                    match = None
                if match:
                    factor = {"": 1, "k": 1000, "m": 1000000}[match.group(2).lower()]
                    total = int(float(match.group(1)) * factor)
                    known_total += total
                    details.append({
                        "session_id": session.get("id"), "name": session.get("alias"), "provider": "Claude",
                        "scope": "session Factory", "confidence": "estimation affichée par le fournisseur",
                        "usage": {"total_tokens": total},
                    })

        cutoff = time.time() - 86400
        host_sessions, host_total = 0, 0
        for filename in glob.glob(str(self.home / ".codex" / "sessions" / "**" / "*.jsonl"), recursive=True):
            path = Path(filename)
            try:
                if path.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            record = _last_matching_json(path, "token_usage_record")
            usage = ((record or {}).get("payload") or {}).get("thread_token_usage")
            if isinstance(usage, dict):
                host_sessions += 1
                host_total += _compact_tokens(usage.get("total_tokens"))
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "factory": {"known_total_tokens": known_total, "sessions": details, "coverage": f"{len(details)} session(s) mesurée(s)"},
            "host_codex_24h": {"total_tokens": host_total, "sessions": host_sessions, "scope": "fichiers Codex modifiés dans les dernières 24 h"},
            "monitoring": {"model_calls": 0, "tokens": 0},
            "notes": [
                "Les compteurs Codex viennent des journaux locaux exacts du fournisseur.",
                "Claude est exact quand son journal local est corrélé; sinon le cockpit utilise l'estimation live affichée par Claude Code.",
                "Les tokens de cache sont inclus dans les totaux fournisseur; ce tableau ne prétend pas calculer un coût en euros.",
            ],
        }


class FactoryCollector:
    def __init__(
        self, runner: Any | None = None, gas_city: Any | None = None,
        product_config: dict[str, Any] | None = None,
    ) -> None:
        self.runner = runner or CommandRunner()
        self.gas_city = gas_city or GasCityReader(timeout=15)
        self.product_config = product_config or load_product_config()
        queue_command = list(self.product_config["queue_command"])
        if queue_command and not Path(queue_command[0]).is_absolute():
            queue_command[0] = str(ROOT / queue_command[0])
        self.queue_command = tuple(queue_command)
        self.product_memory = ProductMemory(config=self.product_config)

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
                "queue": pool.submit(read, "queue", lambda: self.runner.json(*self.queue_command), []),
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
        parent_outcome_id = _meaningful(current_meta.get("gc.parent_outcome"))
        parent_outcome = None
        if parent_outcome_id:
            parent_outcome = _single(read(
                "parent_outcome",
                lambda: self.runner.json("gc", "bd", "show", parent_outcome_id, "--json"),
                [],
            ))
        display_current = parent_outcome or current
        current_product_ids = {value for value in (current_id, parent_outcome_id) if value}
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
                item = _product_bead(
                    bead, store, current_product_ids, self.product_config["name"]
                )
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
                phase = _human_phase(workflow_summary["active_step"]) or _human_phase(
                    coordination_meta.get("gc.current_phase") or current_meta.get("gc.current_phase")
                ) or "Agent en activité"
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
            "product": self.product_config["name"],
            "id": (display_current or {}).get("id"),
            "execution_id": (current or {}).get("id"),
            "title": _human_product_title((display_current or {}).get("title")) if display_current else "Aucun résultat produit en cours",
            "state": focus_state,
            "state_label": focus_label,
            "phase": phase,
            "started_at": (display_current or {}).get("started_at") or (display_current or {}).get("created_at"),
            "last_signal_at": heartbeat,
            "steps": workflow_summary,
            "agent": workflow_summary["assignees"][0] if workflow_summary["assignees"] else None,
        }

        agent_cards = [{
            "name": "Mayor",
            "session_id": (mayor_session or {}).get("id"),
            "provider": (mayor_session or {}).get("provider"),
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
            maintenance = str(session.get("template", "")).startswith("bd.dog")
            is_product_worker = (
                not maintenance
                and current is not None
                and (
                    session.get("alias") in workflow_summary["assignees"]
                    or session.get("name") in workflow_summary["assignees"]
                    or session.get("state") == "active"
                )
            )
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
                "session_id": session.get("id"),
                "provider": session.get("provider"),
                "role": "Agent de maintenance" if maintenance else "Agent de réalisation",
                "objective": objective,
                "state": "working" if recently_active else "waiting",
                "state_label": "En activité" if recently_active else "Signal ancien",
                "phase": (
                    _human_phase(workflow_summary["active_step"])
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
        queue = [
            {
                **item,
                "raw_title": item.get("title"),
                "title": _human_product_title(item.get("title")),
                "kind": "factory_campaign" if item.get("goal") in {None, "none"} else "product_candidate",
            }
            for item in queue if isinstance(item, dict)
        ]
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
            "product_memory": self.product_memory.collect(),
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
            "remote_access": remote_access(),
        }


class SnapshotCache:
    def __init__(self, collector: FactoryCollector, ttl: float = 5.0) -> None:
        self.collector = collector
        self.ttl = ttl
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.value: dict[str, Any] | None = None
        self.collected_at = 0.0
        self.refreshing = False

    def _refresh(self, background: bool) -> dict[str, Any] | None:
        try:
            value = self.collector.collect()
        except Exception:
            if not background:
                raise
            value = None
        finally:
            with self.condition:
                if "value" in locals() and value is not None:
                    self.value = value
                    self.collected_at = time.monotonic()
                self.refreshing = False
                self.condition.notify_all()
        return value

    def _start_background_refresh(self) -> None:
        self.refreshing = True
        threading.Thread(
            target=self._refresh,
            args=(True,),
            name="factory-cockpit-refresh",
            daemon=True,
        ).start()

    def get(self) -> dict[str, Any]:
        with self.condition:
            if self.value is not None:
                if time.monotonic() - self.collected_at >= self.ttl and not self.refreshing:
                    self._start_background_refresh()
                return self.value
            if self.refreshing:
                self.condition.wait_for(lambda: self.value is not None or not self.refreshing, timeout=60)
                if self.value is not None:
                    return self.value
            self.refreshing = True
        value = self._refresh(background=False)
        if value is None:
            raise SourceError("Le premier relevé du cockpit a échoué.")
        return value

    def invalidate(self) -> None:
        with self.condition:
            self.value = None
            self.collected_at = 0.0


class QueueBridge:
    """Structured RECORD-only facade over the existing product queue contract."""

    ACTION_FIELDS = {
        "add": {"title", "why", "acceptance", "urgency"},
        "move": {"id", "position"},
        "urgency": {"id", "urgency"},
        "pause": {"id", "reason"},
        "resume": {"id"},
        "cancel": {"id", "reason", "confirmed"},
    }

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        executor: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.config = config or load_product_config()
        self.executor = executor or subprocess.run
        self.lock = threading.Lock()
        self.last_submit = 0.0
        self.list_command = self._absolute(self.config["queue_command"])
        self.mutation_command = self._absolute(self.config["queue_mutation_command"])

    @staticmethod
    def _absolute(command: list[str]) -> list[str]:
        result = list(command)
        if result and not Path(result[0]).is_absolute():
            result[0] = str(ROOT / result[0])
        return result

    def _execute(self, command: list[str]) -> str:
        try:
            result = self.executor(
                command, cwd=ROOT, capture_output=True, text=True, timeout=45,
                env={**os.environ, "NO_COLOR": "1"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SourceError(f"File produit indisponible: {exc}") from exc
        if result.returncode != 0:
            message = _redact(result.stderr.strip() or result.stdout.strip() or "Mutation refusée.")[:2000]
            if re.search(r"lock|inconsistent|conflict|previous ranks|not in the active|position", message, re.I):
                raise ConflictError(message)
            raise SourceError(message)
        return result.stdout.strip()

    def list(self) -> list[dict[str, Any]]:
        output = self._execute(self.list_command)
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise SourceError("La file produit n’a pas renvoyé de JSON valide.") from exc
        if not isinstance(value, list):
            raise SourceError("La projection de file produit est invalide.")
        return [
            {
                **item,
                "kind": "factory_campaign" if item.get("goal") in {None, "none"} else "product_candidate",
            }
            for item in value if isinstance(item, dict)
        ]

    @staticmethod
    def _text(value: Any, name: str, maximum: int, single_line: bool = False) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name} doit être du texte.")
        result = value.strip()
        if not result or len(result) > maximum or "\x00" in result:
            raise ValueError(f"{name} doit contenir entre 1 et {maximum} caractères.")
        if single_line and ("\n" in result or "\r" in result):
            raise ValueError(f"{name} doit tenir sur une ligne.")
        return result

    def mutate(self, action: Any, payload: Any) -> dict[str, Any]:
        if action not in self.ACTION_FIELDS:
            raise ValueError("Action de file produit interdite.")
        if not isinstance(payload, dict) or set(payload) != self.ACTION_FIELDS[action]:
            raise ValueError("Champs de mutation de file invalides.")
        inventory = self.list()
        by_id = {str(item.get("id")): item for item in inventory if item.get("id")}
        command = [*self.mutation_command, str(action)]
        if action == "add":
            title = self._text(payload["title"], "Le résultat", 160, single_line=True)
            why = self._text(payload["why"], "La raison", 2000)
            acceptance = self._text(payload["acceptance"], "L’acceptation", 2000)
            urgency = payload["urgency"]
            if urgency not in {"normal", "urgent", "critical"}:
                raise ValueError("Urgence invalide.")
            command.extend([
                "--title", title, "--why", why, "--acceptance", acceptance,
                "--urgency", urgency,
            ])
        else:
            item_id = _safe_identifier(str(payload.get("id") or ""))
            if item_id not in by_id:
                raise ConflictError("Ce candidat n’est plus dans la file active; actualise avant de réessayer.")
            if action == "move":
                position = payload["position"]
                if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= len(inventory):
                    raise ValueError("Position de file invalide.")
                command.extend([item_id, str(position)])
            elif action == "urgency":
                urgency = payload["urgency"]
                if urgency not in {"normal", "urgent", "critical"}:
                    raise ValueError("Urgence invalide.")
                command.extend([item_id, urgency])
            elif action == "pause":
                command.extend([item_id, self._text(payload["reason"], "La raison de pause", 1000)])
            elif action == "resume":
                command.append(item_id)
            else:
                if payload["confirmed"] is not True:
                    raise ValueError("L’annulation doit être confirmée explicitement.")
                command.extend([item_id, self._text(payload["reason"], "La raison d’annulation", 1000)])
        with self.lock:
            now = time.monotonic()
            if now - self.last_submit < 0.75:
                raise ConflictError("Une mutation est déjà en cours; actualise puis réessaie.")
            message = self._execute(command)
            self.last_submit = now
            refreshed = self.list()
        return {
            "accepted": True,
            "action": action,
            "message": message,
            "queue": refreshed,
            "model_calls": 0,
        }


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


class POBridge:
    """Independent, on-demand Codex PO conversations for product decisions."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        state_path: Path | None = None,
        executor: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.config = config or load_product_config()
        self.memory = ProductMemory(config=self.config)
        self.state_path = state_path or ROOT / ".gc" / "runtime" / "factory-cockpit-po.json"
        self.executor = executor or subprocess.run
        self.lock = threading.Lock()
        self.running: set[str] = set()
        self.tokens = TokenReader()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = self._load()
        changed = False
        for conversation in state["conversations"].values():
            if conversation.get("status") in {"queued", "running"}:
                conversation["status"] = "interrupted"
                conversation["error"] = "Le cockpit a redémarré pendant la réponse; renvoie ton message si nécessaire."
                changed = True
        if changed:
            self._write(state)

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": 2, "conversations": {}, "current_general": None}

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return self._empty()
            if isinstance(value.get("conversations"), dict):
                return value
            if isinstance(value.get("active"), dict):
                migrated = self._empty()
                active = value["active"]
                if active.get("messages") or active.get("thread_id"):
                    key = "general:migrated"
                    migrated["conversations"][key] = {
                        **active, "key": key, "kind": "general", "title": "Discussion PO précédente",
                        "decision_id": None, "created_at": active.get("created_at") or datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    migrated["current_general"] = key
                return migrated
            return self._empty()
        except (OSError, json.JSONDecodeError):
            return self._empty()

    def _write(self, value: dict[str, Any]) -> None:
        handle, filename = tempfile.mkstemp(prefix="cockpit-po-", suffix=".json", dir=self.state_path.parent)
        try:
            os.fchmod(handle, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
            Path(filename).replace(self.state_path)
        except Exception:
            try:
                os.close(handle)
            except OSError:
                pass
            Path(filename).unlink(missing_ok=True)
            raise

    def _decision(self, decision_id: Any) -> dict[str, Any] | None:
        if not decision_id:
            return None
        return next(
            (item for item in self.memory.collect()["decisions"] if item.get("id") == decision_id),
            None,
        )

    def _new_general_key(self) -> str:
        return f"general:{time.time_ns()}"

    def _ensure_conversation(
        self, state: dict[str, Any], decision: dict[str, Any] | None, conversation_key: Any = None
    ) -> tuple[str, dict[str, Any]]:
        if decision:
            key, title, kind = f"decision:{decision['id']}", decision["title"], "decision"
        else:
            key = str(conversation_key or state.get("current_general") or self._new_general_key())
            if not key.startswith("general:"):
                raise ValueError("Discussion PO générale invalide.")
            title, kind = "Discussion générale", "general"
            state["current_general"] = key
        conversation = state["conversations"].setdefault(key, {
            "key": key, "kind": kind, "title": title,
            "decision_id": decision.get("id") if decision else None,
            "domain": decision.get("domain") if decision else None,
            "thread_id": None, "status": "idle", "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return key, conversation

    def submit(
        self, message: Any, intent: Any = "discuss", decision_id: Any = None,
        conversation_key: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip() or len(message.strip()) > 6000 or "\x00" in message:
            raise ValueError("Le message PO doit contenir entre 1 et 6000 caractères.")
        if intent not in {"discuss", "record"}:
            raise ValueError("L’intention PO doit être discuter ou enregistrer.")
        decision = self._decision(decision_id)
        if decision_id and not decision:
            raise ValueError("Cette décision n’existe plus dans la mémoire produit.")
        with self.lock:
            state = self._load()
            key, conversation = self._ensure_conversation(state, decision, conversation_key)
            if key in self.running or conversation.get("status") in {"queued", "running"}:
                raise RuntimeError("Le PO prépare déjà une réponse pour ce sujet.")
            conversation.setdefault("messages", []).append({
                "role": "Benjamin", "text": message.strip(), "intent": intent,
                "decision_id": decision.get("id") if decision else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            conversation["status"] = "queued"
            conversation["error"] = None
            conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write(state)
            self.running.add(key)
        threading.Thread(
            target=self._run,
            args=(key, message.strip(), intent, decision),
            name=f"factory-cockpit-po-{key.replace(':', '-')}",
            daemon=True,
        ).start()
        return {"accepted": True, "status": "queued", "key": key, "thread_id": conversation.get("thread_id")}

    def _prompt(self, message: str, intent: str, decision: dict[str, Any] | None) -> str:
        context = ""
        if decision:
            context = (
                f"\nEspace de décision dédié ({decision.get('domain', 'produit')}): {decision['title']}\n"
                f"Contexte durable: {decision['detail']}\nSource: {decision['source']}\n"
                "Aide Benjamin à décider: reformule le choix, propose 2 à 4 options réellement distinctes, "
                "recommande-en une avec ses compromis, puis termine par la prochaine question ou une réponse-type courte.\n"
            )
        action = (
            "DISCUSS: explore les options sans modifier quoi que ce soit."
            if intent == "discuss"
            else "RECORD: traite ce message comme une décision explicite de Benjamin; mets à jour la plus petite mémoire produit durable appropriée, vérifie-la et explique exactement ce qui a été enregistré."
        )
        return (
            "Tu es le Product Owner GPT intégré de SayMyName et l’unique interlocuteur produit de Benjamin. "
            "Travaille en français, au niveau produit/utilisateur/entreprise. Charge progressivement les instructions du workspace et la mémoire durable. "
            "Le contexte supérieur appartient à Benjamin et au PO; le Mayor reste seul orchestrateur de l’exécution Factory. "
            "Ne lance pas de livraison, ne pilote pas d’agent et ne contacte pas le Mayor sauf demande EXECUTE explicite de Benjamin. "
            "Tu disposes des outils complets du host mais l’accès complet est une capacité, pas une autorisation générale. "
            f"Mode demandé: {action}{context}\nMessage de Benjamin: {message}"
        )

    def _run(self, key: str, message: str, intent: str, decision: dict[str, Any] | None) -> None:
        output_path = self.state_path.parent / f"po-last-{os.getpid()}-{threading.get_ident()}.txt"
        try:
            with self.lock:
                state = self._load()
                state["conversations"][key]["status"] = "running"
                self._write(state)
                thread_id = state["conversations"][key].get("thread_id")
            prompt = self._prompt(message, intent, decision)
            if thread_id:
                command = [
                    "codex", "exec", "resume", "--dangerously-bypass-approvals-and-sandbox",
                    "--json", "-o", str(output_path), str(thread_id), prompt,
                ]
            else:
                command = [
                    "codex", "exec", "--dangerously-bypass-approvals-and-sandbox",
                    "--skip-git-repo-check",
                    "--json", "-o", str(output_path), "-C", str(self.config["po_workspace"]),
                ]
                for directory in self.config.get("po_add_dirs", []):
                    command.extend(["--add-dir", str(directory)])
                command.append(prompt)
            result = self.executor(
                command, cwd=ROOT, capture_output=True, text=True, timeout=1200,
                env={**os.environ, "NO_COLOR": "1"},
            )
            observed_thread = thread_id
            for raw in result.stdout.splitlines():
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                thread_value = event.get("thread")
                nested_thread = thread_value.get("id") if isinstance(thread_value, dict) else None
                observed_thread = event.get("thread_id") or nested_thread or observed_thread
            response = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.exists() else ""
            if result.returncode != 0:
                raise SourceError(_redact(result.stderr.strip() or "Le processus PO a échoué.")[:4000])
            if not response:
                response = "Le PO a terminé sans produire de réponse visible."
            with self.lock:
                state = self._load()
                conversation = state["conversations"][key]
                conversation["thread_id"] = observed_thread
                conversation["status"] = "idle"
                conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
                conversation["messages"].append({
                    "role": "PO", "text": _redact(response)[:16000],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                self._write(state)
        except Exception as exc:
            with self.lock:
                state = self._load()
                if key in state["conversations"]:
                    state["conversations"][key]["status"] = "error"
                    state["conversations"][key]["error"] = _redact(str(exc))[:4000]
                    state["conversations"][key]["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._write(state)
        finally:
            output_path.unlink(missing_ok=True)
            with self.lock:
                self.running.discard(key)

    def new_conversation(self) -> dict[str, Any]:
        with self.lock:
            state = self._load()
            key = self._new_general_key()
            state["current_general"] = key
            self._write(state)
        return {"created": True, "key": key, "session_created": False}

    def _public(self, conversation: dict[str, Any]) -> dict[str, Any]:
        thread_id = conversation.get("thread_id")
        messages = conversation.get("messages", [])
        last = messages[-1] if messages else {}
        return {
            **conversation,
            "messages": messages[-60:],
            "last_role": last.get("role"),
            "last_message_at": last.get("timestamp"),
            "usage": self.tokens.codex_thread(thread_id),
            "codex_url": f"codex://threads/{quote(thread_id, safe='')}" if thread_id else None,
        }

    def index(self) -> dict[str, Any]:
        """Lightweight conversation states for navigation; no token journal scan."""
        state = self._load()
        conversations = []
        for item in state["conversations"].values():
            messages = item.get("messages", [])
            last = messages[-1] if messages else {}
            conversations.append({
                "key": item.get("key"), "kind": item.get("kind"),
                "decision_id": item.get("decision_id"), "domain": item.get("domain"),
                "title": item.get("title"), "status": item.get("status", "idle"),
                "thread_id": item.get("thread_id"), "updated_at": item.get("updated_at"),
                "last_role": last.get("role"), "last_message_at": last.get("timestamp"),
            })
        return {
            "model_calls": 0,
            "conversations": sorted(
                conversations, key=lambda item: item.get("updated_at") or "", reverse=True
            ),
        }

    def conversation(self, decision_id: Any = None, conversation_key: Any = None) -> dict[str, Any]:
        state = self._load()
        decision = self._decision(decision_id)
        key = f"decision:{decision['id']}" if decision else str(conversation_key or state.get("current_general") or "")
        conversation = state["conversations"].get(key)
        if not conversation:
            conversation = {
                "key": key or None, "kind": "decision" if decision else "general",
                "title": decision.get("title") if decision else "Discussion générale",
                "decision_id": decision.get("id") if decision else None,
                "domain": decision.get("domain") if decision else None,
                "thread_id": None, "status": "not_started", "messages": [],
            }
        return {
            "product": self.config["name"],
            "workspace": self.config["po_workspace"],
            "full_access": True,
            **self._public(conversation),
            "conversations": sorted(
                [self._public(item) for item in state["conversations"].values()],
                key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True,
            ),
        }


class PreviewBridge:
    """Safe asynchronous facade over the repository-owned SayMyName preview wrapper."""

    def __init__(self, executor: Callable[..., subprocess.CompletedProcess[str]] | None = None) -> None:
        self.executor = executor or subprocess.run
        self.lock = threading.Lock()
        self.running_action: str | None = None
        self.error: str | None = None

    @staticmethod
    def _parse(output: str) -> dict[str, str]:
        return {
            key: value
            for raw in output.splitlines()
            if "=" in raw
            for key, value in [raw.split("=", 1)]
        }

    def status(self) -> dict[str, Any]:
        result = self.executor(
            [str(ROOT / "bin" / "saymyname-preview"), "status"], cwd=ROOT,
            capture_output=True, text=True, timeout=30,
        )
        values = self._parse(result.stdout)
        return {
            "state": values.get("STATE", "unknown"),
            "backend_sha": values.get("BACKEND_SHA", "unknown"),
            "frontend_sha": values.get("FRONTEND_SHA", "unknown"),
            "backend_health": values.get("BACKEND_HEALTH", "unknown"),
            "frontend_health": values.get("FRONTEND_HEALTH", "unknown"),
            "browser_url": values.get("BROWSER_URL", "http://127.0.0.1:5173/"),
            "action": self.running_action,
            "error": self.error,
            "commands": {"frontend": "npm run dev", "backend": "./mvnw spring-boot:run"},
            "version_policy": "dev synchronisé avec origin/dev, dépôts propres, SHA affichés",
        }

    def submit(self, action: Any) -> dict[str, Any]:
        if action not in {"start", "stop", "restart"}:
            raise ValueError("Action de prévisualisation invalide.")
        with self.lock:
            if self.running_action:
                raise RuntimeError(f"L’action {self.running_action} est déjà en cours.")
            self.running_action = str(action)
            self.error = None
        threading.Thread(target=self._run, args=(str(action),), daemon=True, name="saymyname-preview").start()
        return {"accepted": True, "action": action}

    def _run(self, action: str) -> None:
        try:
            result = self.executor(
                [str(ROOT / "bin" / "saymyname-preview"), action], cwd=ROOT,
                capture_output=True, text=True, timeout=1800,
            )
            if result.returncode != 0:
                raise SourceError(_redact(result.stderr.strip() or result.stdout.strip() or "La prévisualisation a échoué.")[:4000])
        except Exception as exc:
            with self.lock:
                self.error = _redact(str(exc))[:4000]
        finally:
            with self.lock:
                self.running_action = None

def handler_factory(
    cache: SnapshotCache,
    mayor_bridge: MayorBridge | None = None,
    detail_reader: DetailReader | None = None,
    token_cache: SnapshotCache | None = None,
    po_bridge: POBridge | None = None,
    preview_bridge: PreviewBridge | None = None,
    reference_reader: ProductReferenceReader | None = None,
    queue_bridge: QueueBridge | None = None,
) -> type[BaseHTTPRequestHandler]:
    bridge = mayor_bridge or MayorBridge()
    details = detail_reader or DetailReader()
    tokens = token_cache or SnapshotCache(TokenReader(), ttl=30)
    po = po_bridge or POBridge()
    preview = preview_bridge or PreviewBridge()
    references = reference_reader or ProductReferenceReader()
    queue = queue_bridge or QueueBridge()

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
                "style-src 'self'; script-src 'self'; object-src 'none'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            )
            self.end_headers()

        def _json_response(self, status: int, value: Any) -> None:
            payload = json.dumps(value, ensure_ascii=False).encode()
            self._headers(status, "application/json; charset=utf-8")
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/health":
                self._json_response(
                    200, {"ok": True, "model_calls": 0, "monitoring_model_calls": 0}
                )
                return
            if path == "/api/snapshot":
                self._json_response(200, cache.get())
                return
            if path == "/api/tokens":
                try:
                    self._json_response(200, tokens.get())
                except SourceError as exc:
                    self._json_response(503, {"error": str(exc)})
                return
            if path == "/api/item":
                try:
                    self._json_response(200, details.item(
                        query.get("store", ["city"])[0], query.get("id", [""])[0]
                    ))
                except ValueError as exc:
                    self._json_response(400, {"error": str(exc)})
                except SourceError as exc:
                    self._json_response(404, {"error": str(exc)})
                return
            if path == "/api/agent":
                try:
                    self._json_response(200, details.agent(query.get("id", [""])[0]))
                except ValueError as exc:
                    self._json_response(400, {"error": str(exc)})
                except SourceError as exc:
                    self._json_response(404, {"error": str(exc)})
                return
            if path == "/api/mayor/conversation":
                try:
                    self._json_response(200, bridge.conversation())
                except SourceError as exc:
                    self._json_response(503, {"error": str(exc)})
                return
            if path == "/api/po/conversation":
                self._json_response(200, po.conversation(
                    query.get("decision_id", [None])[0], query.get("key", [None])[0]
                ))
                return
            if path == "/api/po/index":
                self._json_response(200, po.index())
                return
            if path == "/api/preview/status":
                try:
                    self._json_response(200, preview.status())
                except Exception as exc:
                    self._json_response(503, {"error": _redact(str(exc))[:1000]})
                return
            if path == "/api/reference":
                try:
                    self._json_response(200, references.get(query.get("id", [""])[0]))
                except ValueError as exc:
                    self._json_response(400, {"error": str(exc), "state": "invalid"})
                except SourceError as exc:
                    self._json_response(422, {"error": str(exc), "state": "source_error"})
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
            if path not in {
                "/api/mayor/message", "/api/po/message", "/api/po/new",
                "/api/preview/action", "/api/product-queue",
            }:
                self._json_response(404, {"error": "Not found"})
                return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if not origin or not host or origin not in {f"http://{host}", f"https://{host}"}:
                self._json_response(403, {"error": "Origine refusée."})
                return
            expected_header = (
                "human-message" if path == "/api/mayor/message"
                else "human-preview-action" if path == "/api/preview/action"
                else "human-queue-record" if path == "/api/product-queue"
                else "human-po-message"
            )
            if self.headers.get("X-Factory-Cockpit") != expected_header:
                self._json_response(403, {"error": "Confirmation de cockpit absente."})
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self._json_response(415, {"error": "JSON requis."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 12288:
                self._json_response(413, {"error": "Message trop grand ou vide."})
                return
            try:
                request = json.loads(self.rfile.read(length))
                if path == "/api/mayor/message":
                    result = bridge.submit(request.get("message"), request.get("intent", "question"))
                elif path == "/api/po/message":
                    result = po.submit(
                        request.get("message"), request.get("intent", "discuss"),
                        request.get("decision_id"), request.get("conversation_key"),
                    )
                elif path == "/api/preview/action":
                    result = preview.submit(request.get("action"))
                elif path == "/api/product-queue":
                    result = queue.mutate(request.get("action"), request.get("payload"))
                    cache.invalidate()
                else:
                    result = po.new_conversation()
                self._json_response(202, result)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "JSON invalide."})
            except ValueError as exc:
                self._json_response(400, {"error": str(exc)})
            except ConflictError as exc:
                self._json_response(409, {"error": str(exc), "state": "conflict"})
            except SourceError as exc:
                self._json_response(503, {"error": str(exc)})
            except RuntimeError as exc:
                self._json_response(429, {"error": str(exc)})

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
