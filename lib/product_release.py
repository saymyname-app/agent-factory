#!/usr/bin/env python3
"""Versioned product-release contract, transitions, and campaign selection.

This module is deliberately pure: it reads no live state, writes no files, and
never invokes a model.  Git owns release truth; callers only validate or project
an already loaded value.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


CONTRACT = "agent-factory-product-release/v1"
SCHEMA_VERSION = 1
RELEASE_STATES = ("draft", "approved", "executing", "frozen")
EVIDENCE_STATES = {
    "proven", "partial", "unverified", "absent", "out_of_version", "decision_required",
}
EVIDENCE_KINDS = {"ui", "api", "data", "test", "document", "bead", "github"}
WORK_STATES = {"candidate", "materialized", "active", "blocked", "delivered", "cancelled", "paused"}
BLOCK_KINDS = {"decision", "admin", "limit", "durable_failure", "dependency"}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,95}$")
VERSION_PATTERN = re.compile(r"^V[1-9][0-9]*$")


class ReleaseContractError(ValueError):
    """A release value cannot safely drive a product projection or campaign."""


def _required_text(value: Any, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ReleaseContractError(f"{field} doit être un texte non vide.")
    result = value.strip()
    if pattern and not pattern.fullmatch(result):
        raise ReleaseContractError(f"{field} a un format invalide.")
    return result


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ReleaseContractError(f"{field} doit être une liste{' non vide' if nonempty else ''}.")
    return value


def _ids(value: Any, field: str, allowed: set[str] | None = None) -> list[str]:
    result = [
        _required_text(item, f"{field}[]", pattern=ID_PATTERN)
        for item in _list(value, field, nonempty=False)
    ]
    if len(result) != len(set(result)):
        raise ReleaseContractError(f"{field} contient un doublon.")
    if allowed is not None and not set(result).issubset(allowed):
        raise ReleaseContractError(f"{field} contient une référence inconnue.")
    return result


def _validate_evidence(value: Any, field: str) -> list[dict[str, Any]]:
    evidence = _list(value, field)
    for index, item in enumerate(evidence):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        if set(item) != {"kind", "ref", "status"}:
            raise ReleaseContractError(f"{prefix} doit contenir exactement kind, ref et status.")
        if item.get("kind") not in EVIDENCE_KINDS:
            raise ReleaseContractError(f"{prefix}.kind est inconnu.")
        _required_text(item.get("ref"), f"{prefix}.ref")
        if item.get("status") not in EVIDENCE_STATES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
    return evidence


def _validate_scoped_blocks(
    value: Any, field: str, *, require_evidence: bool = True,
) -> tuple[list[dict[str, Any]], set[str]]:
    items = _list(value, field, nonempty=False)
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        item_id = _required_text(item.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if item_id in seen:
            raise ReleaseContractError(f"Identifiant dupliqué dans {field}: {item_id}.")
        seen.add(item_id)
        _required_text(item.get("title"), f"{prefix}.title")
        _required_text(item.get("description"), f"{prefix}.description")
        if item.get("status") not in EVIDENCE_STATES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        if require_evidence:
            _validate_evidence(item.get("evidence"), f"{prefix}.evidence")
    return items, seen


def _validate_graph(nodes: Any, criterion_ids: set[str], decision_ids: set[str]) -> list[dict[str, Any]]:
    values = _list(nodes, "work_graph")
    ids: set[str] = set()
    dedupe: set[str] = set()
    for index, node in enumerate(values):
        prefix = f"work_graph[{index}]"
        if not isinstance(node, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        node_id = _required_text(node.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        dedupe_key = _required_text(node.get("dedupe_key"), f"{prefix}.dedupe_key", pattern=ID_PATTERN)
        if node_id in ids or dedupe_key in dedupe:
            raise ReleaseContractError("Le graphe de travail contient un ID ou une clé de déduplication en double.")
        ids.add(node_id)
        dedupe.add(dedupe_key)
        _required_text(node.get("title"), f"{prefix}.title")
        if node.get("kind") not in {"product", "factory"}:
            raise ReleaseContractError(f"{prefix}.kind doit être product ou factory.")
        if node.get("state") not in WORK_STATES:
            raise ReleaseContractError(f"{prefix}.state est inconnu.")
        if node.get("independence") not in {"proven", "unknown"}:
            raise ReleaseContractError(f"{prefix}.independence doit être proven ou unknown.")
        if not isinstance(node.get("order"), int) or isinstance(node.get("order"), bool) or node["order"] < 1:
            raise ReleaseContractError(f"{prefix}.order doit être un entier positif.")
        _ids(node.get("criterion_refs"), f"{prefix}.criterion_refs", criterion_ids)
        if not node.get("criterion_refs"):
            raise ReleaseContractError(f"{prefix} doit être traçable vers au moins un critère.")
        blocker = node.get("blocker")
        if blocker is not None:
            if not isinstance(blocker, dict) or set(blocker) - {"kind", "decision_id", "cause", "owner", "action"}:
                raise ReleaseContractError(f"{prefix}.blocker est invalide.")
            if blocker.get("kind") not in BLOCK_KINDS:
                raise ReleaseContractError(f"{prefix}.blocker.kind est inconnu.")
            for field in ("cause", "owner", "action"):
                _required_text(blocker.get(field), f"{prefix}.blocker.{field}")
            decision_id = blocker.get("decision_id")
            if blocker["kind"] == "decision":
                if decision_id not in decision_ids:
                    raise ReleaseContractError(f"{prefix}.blocker.decision_id est inconnu.")
            elif decision_id is not None:
                raise ReleaseContractError(f"{prefix}.blocker.decision_id est réservé aux décisions.")
    for index, node in enumerate(values):
        _ids(node.get("depends_on"), f"work_graph[{index}].depends_on", ids)
        if node["id"] in node.get("depends_on", []):
            raise ReleaseContractError("Un travail ne peut pas dépendre de lui-même.")

    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {node["id"]: node for node in values}

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ReleaseContractError("Le graphe de travail contient un cycle.")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in by_id[node_id].get("depends_on", []):
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in by_id:
        visit(node_id)
    return values


def validate_release_contract(value: Any) -> dict[str, Any]:
    """Validate semantic invariants that JSON Schema alone cannot express."""
    if not isinstance(value, dict):
        raise ReleaseContractError("Le contrat de release doit être un objet.")
    required = {
        "$schema", "contract", "schema_version", "product", "version", "title", "state",
        "maturity", "capabilities", "journeys", "included", "excluded", "dependencies",
        "decisions", "criteria", "work_graph", "factory_improvements", "next_version",
    }
    if not required.issubset(value):
        missing = ", ".join(sorted(required - set(value)))
        raise ReleaseContractError(f"Contrat de release incomplet: {missing}.")
    if value.get("contract") != CONTRACT or value.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseContractError("Version du contrat de release non prise en charge.")
    _required_text(value.get("product"), "product", pattern=re.compile(r"^[a-z0-9-]+$"))
    _required_text(value.get("version"), "version", pattern=VERSION_PATTERN)
    _required_text(value.get("title"), "title")
    if value.get("state") not in RELEASE_STATES:
        raise ReleaseContractError("État de release inconnu.")
    next_version = value.get("next_version")
    if next_version is not None:
        next_version = _required_text(next_version, "next_version", pattern=VERSION_PATTERN)
        if int(next_version[1:]) <= int(value["version"][1:]):
            raise ReleaseContractError("next_version doit être postérieure à la version courante.")
    maturity = value.get("maturity")
    if not isinstance(maturity, dict) or set(maturity) != {"level", "label", "criteria"}:
        raise ReleaseContractError("La maturité doit contenir exactement level, label et criteria.")
    if maturity.get("level") not in {"not_ready", "partial", "release_ready", "production_autonomous"}:
        raise ReleaseContractError("Niveau de maturité inconnu.")
    _required_text(maturity.get("label"), "maturity.label")
    maturity_criteria = _ids(maturity.get("criteria"), "maturity.criteria")

    capabilities, capability_ids = _validate_scoped_blocks(value.get("capabilities"), "capabilities")
    journeys, journey_ids = _validate_scoped_blocks(value.get("journeys"), "journeys")
    for index, journey in enumerate(journeys):
        _ids(journey.get("capability_refs"), f"journeys[{index}].capability_refs", capability_ids)
        if not journey.get("capability_refs"):
            raise ReleaseContractError("Chaque parcours doit référencer une capacité.")

    for field in ("included", "excluded"):
        items, _ = _validate_scoped_blocks(value.get(field), field)
        for index, item in enumerate(items):
            if item.get("kind") not in {"product", "factory"}:
                raise ReleaseContractError(f"{field}[{index}].kind est invalide.")
    dependencies, dependency_ids = _validate_scoped_blocks(value.get("dependencies"), "dependencies")
    for index, item in enumerate(dependencies):
        if item.get("required_for") is None:
            raise ReleaseContractError(f"dependencies[{index}].required_for manque.")
        _ids(item["required_for"], f"dependencies[{index}].required_for", capability_ids | journey_ids)

    decisions = _list(value.get("decisions"), "decisions", nonempty=False)
    decision_ids: set[str] = set()
    for index, item in enumerate(decisions):
        prefix = f"decisions[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        decision_id = _required_text(item.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if decision_id in decision_ids:
            raise ReleaseContractError(f"Décision dupliquée: {decision_id}.")
        decision_ids.add(decision_id)
        _required_text(item.get("title"), f"{prefix}.title")
        _required_text(item.get("source_ref"), f"{prefix}.source_ref")
        if item.get("status") not in {"accepted", "decision_required", "superseded"}:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        if item.get("risk") not in {"low", "high"}:
            raise ReleaseContractError(f"{prefix}.risk est inconnu.")
        if not isinstance(item.get("revision"), int) or item["revision"] < 1:
            raise ReleaseContractError(f"{prefix}.revision doit être positive.")
        _ids(item.get("capability_refs"), f"{prefix}.capability_refs", capability_ids)
        _ids(item.get("dependency_refs"), f"{prefix}.dependency_refs", dependency_ids)
        options = _list(item.get("options", []), f"{prefix}.options", nonempty=False)
        option_ids: set[str] = set()
        for option_index, option in enumerate(options):
            if not isinstance(option, dict) or set(option) != {"id", "label"}:
                raise ReleaseContractError(f"{prefix}.options[{option_index}] est invalide.")
            option_id = _required_text(option.get("id"), f"{prefix}.options[{option_index}].id", pattern=ID_PATTERN)
            _required_text(option.get("label"), f"{prefix}.options[{option_index}].label")
            if option_id in option_ids:
                raise ReleaseContractError(f"Option dupliquée dans {prefix}.")
            option_ids.add(option_id)

    criteria, criterion_ids = _validate_scoped_blocks(value.get("criteria"), "criteria")
    if not set(maturity_criteria).issubset(criterion_ids):
        raise ReleaseContractError("maturity.criteria contient une référence inconnue.")
    for index, item in enumerate(criteria):
        _ids(item.get("capability_refs"), f"criteria[{index}].capability_refs", capability_ids)
        _ids(item.get("journey_refs"), f"criteria[{index}].journey_refs", journey_ids)
        if not item.get("capability_refs") and not item.get("journey_refs"):
            raise ReleaseContractError("Chaque critère doit être lié à une capacité ou un parcours.")

    _validate_graph(value.get("work_graph"), criterion_ids, decision_ids)
    improvements, _ = _validate_scoped_blocks(value.get("factory_improvements"), "factory_improvements")
    for index, item in enumerate(improvements):
        if item.get("kind") != "factory":
            raise ReleaseContractError(f"factory_improvements[{index}] doit porter le badge Factory.")
        work_ref = item.get("work_ref")
        if work_ref is not None:
            _required_text(work_ref, f"factory_improvements[{index}].work_ref", pattern=ID_PATTERN)
    if any(item.get("work_ref") == "af-cm1l" for item in capabilities):
        raise ReleaseContractError("af-cm1l est une amélioration Factory, jamais une capacité produit V1.")
    return value


def load_release_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"Contrat de release illisible: {exc}") from exc
    return validate_release_contract(value)


def transition_release(value: dict[str, Any], target_state: str) -> dict[str, Any]:
    """Return an idempotent, fail-closed release-state transition."""
    validate_release_contract(value)
    if target_state not in RELEASE_STATES:
        raise ReleaseContractError(f"Transition vers un état inconnu: {target_state}.")
    current = value["state"]
    if current == target_state:
        return copy.deepcopy(value)
    if current == "frozen":
        raise ReleaseContractError("Une release frozen est immuable.")
    next_state = {
        "draft": "approved",
        "approved": "executing",
        "executing": "frozen",
    }[current]
    if target_state != next_state:
        raise ReleaseContractError(f"Transition interdite: {current} → {target_state}.")
    result = copy.deepcopy(value)
    result["state"] = target_state
    return validate_release_contract(result)


def start_next_version(value: dict[str, Any], next_version: str) -> dict[str, Any]:
    """Freeze the current release before any later version can start."""
    validate_release_contract(value)
    wanted = _required_text(next_version, "next_version", pattern=VERSION_PATTERN)
    if value.get("next_version") != wanted:
        raise ReleaseContractError("La version suivante ne correspond pas au contrat approuvé.")
    if value["state"] not in {"executing", "frozen"}:
        raise ReleaseContractError("Une version suivante exige une release courante executing ou frozen.")
    frozen = transition_release(value, "frozen") if value["state"] != "frozen" else copy.deepcopy(value)
    return {"frozen_release": frozen, "next_version": wanted}


def select_campaign_work(value: dict[str, Any]) -> dict[str, Any]:
    """Select exactly one proven independent release node, or explain the stop."""
    validate_release_contract(value)
    if value["state"] not in {"approved", "executing"}:
        return {
            "selected": None,
            "reason": "release_not_executable",
            "owner": "PO",
            "action": "Faire approuver puis activer la release dans Git avant toute campagne.",
        }
    nodes = value["work_graph"]
    by_id = {item["id"]: item for item in nodes}
    active_dedupe = {
        item["dedupe_key"] for item in nodes
        if item["state"] in {"materialized", "active", "delivered"}
    }
    candidates = []
    unknown = []
    for item in sorted(nodes, key=lambda node: (node["order"], node["id"])):
        if item["kind"] != "product" or item["state"] != "candidate" or item.get("blocker"):
            continue
        if item["dedupe_key"] in active_dedupe:
            continue
        dependencies = [by_id[dependency] for dependency in item.get("depends_on", [])]
        if not all(dependency["state"] == "delivered" for dependency in dependencies):
            continue
        if item["independence"] != "proven":
            unknown.append(item)
            continue
        candidates.append(item)
    if candidates:
        selected = candidates[0]
        return {
            "selected": {
                "id": selected["id"],
                "work_ref": selected.get("work_ref"),
                "title": selected["title"],
                "criterion_refs": list(selected["criterion_refs"]),
                "dedupe_key": selected["dedupe_key"],
            },
            "reason": "proven_independent_work",
            "owner": "Mayor",
            "action": "Matérialiser uniquement ce premier travail traçable, sans réordonner la file.",
        }
    if unknown:
        return {
            "selected": None,
            "reason": "independence_unknown",
            "owner": "Mayor",
            "action": "Prouver l’indépendance du sous-graphe avant toute matérialisation.",
        }
    blockers = [item["blocker"] for item in nodes if item["state"] == "blocked" and item.get("blocker")]
    if blockers:
        blocker = sorted(blockers, key=lambda item: (item["kind"], item["cause"]))[0]
        return {
            "selected": None,
            "reason": f"blocked_{blocker['kind']}",
            "owner": blocker["owner"],
            "action": blocker["action"],
            "cause": blocker["cause"],
            "decision_id": blocker.get("decision_id"),
        }
    if all(item["status"] == "proven" for item in value["criteria"]):
        return {
            "selected": None,
            "reason": "release_target_proven",
            "owner": "none",
            "action": "Figer les preuves de la release; ne matérialiser aucun travail supplémentaire.",
        }
    return {
        "selected": None,
        "reason": "no_proven_independent_work",
        "owner": "Mayor",
        "action": "Conserver l’arrêt et enregistrer la preuve ou dépendance manquante.",
    }


def project_release(value: dict[str, Any]) -> dict[str, Any]:
    """Project the selected version for deterministic human surfaces."""
    validate_release_contract(value)
    status_labels = {
        "proven": "Prouvé", "partial": "Partiel", "unverified": "Non vérifié",
        "absent": "Absent", "out_of_version": "Hors version",
        "decision_required": "Décision requise",
    }
    state_labels = {
        "draft": "Brouillon", "approved": "Approuvée",
        "executing": "En exécution", "frozen": "Figée",
    }
    result = copy.deepcopy(value)
    result.pop("$schema", None)
    result["state_label"] = state_labels[value["state"]]
    result["truth_state"] = value["state"]
    result["operational_state"] = value["state"]
    result["operational_state_label"] = state_labels[value["state"]]
    for field in (
        "capabilities", "journeys", "included", "excluded", "dependencies",
        "criteria", "factory_improvements",
    ):
        for item in result[field]:
            item["status_label"] = status_labels[item["status"]]
    result["campaign"] = select_campaign_work(value)
    decisions = [item for item in value["decisions"] if item["status"] == "decision_required"]
    result["intervention"] = (
        {
            "decision_id": decisions[0]["id"],
            "title": decisions[0]["title"],
            "risk": decisions[0]["risk"],
            "deep_link": f"#view=project&releaseDecision={decisions[0]['id']}",
        }
        if decisions else None
    )
    result["model_calls"] = 0
    return result


def project_operational_release(
    release: dict[str, Any], campaign: dict[str, Any],
) -> dict[str, Any]:
    """Overlay runtime execution state without changing versioned Git truth."""
    if not isinstance(release, dict) or release.get("contract") != CONTRACT:
        raise ReleaseContractError("Projection de release invalide.")
    if not isinstance(campaign, dict) or not isinstance(campaign.get("enabled"), bool):
        raise ReleaseContractError("Projection de campagne invalide.")
    result = copy.deepcopy(release)
    truth_state = result.get("truth_state") or result.get("state")
    if truth_state not in RELEASE_STATES:
        raise ReleaseContractError("État Git de release invalide.")
    operational = truth_state
    if campaign["enabled"]:
        if truth_state == "draft":
            raise ReleaseContractError("Une campagne ne peut pas exécuter une release Git draft.")
        if truth_state in {"approved", "executing"}:
            operational = "executing"
    labels = {
        "draft": "Brouillon Git", "approved": "Approuvée · campagne non activée",
        "executing": "En exécution par la campagne", "frozen": "Figée",
    }
    result["truth_state"] = truth_state
    result["operational_state"] = operational
    result["operational_state_label"] = labels[operational]
    return result
