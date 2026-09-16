#!/usr/bin/env python3
"""Deterministic human state projection shared by Factory CLI and cockpit.

The module only transforms already observed values.  It performs no I/O and has
no model or orchestration path.
"""

from __future__ import annotations

from typing import Any


CONTRACT = "agent-factory-human-state/v1"
CAMPAIGN_STATES = {"inactive", "active", "awaiting_mayor", "running", "blocked", "completed"}
CAMPAIGN_BLOCK_KINDS = {
    "decision", "admin", "durable_failure", "limit", "result_blocker", "all_paused",
    "source_failure", "transient_failure",
}
TECHNICAL_DEFERRED_EXPLANATION = (
    "Conservé techniquement différé dans Beads : ce candidat ne peut pas être "
    "pris par un agent avant sa matérialisation explicite par le Mayor."
)


class StateContractError(ValueError):
    """An observed input cannot support a safe human projection."""


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and value.lower() != "none" else None


def _structured_pause_reason(notes: Any) -> str | None:
    """Read only the queue command's exact audit prefix, never free prose."""
    if not isinstance(notes, str):
        return None
    prefix = "Product queue paused: "
    reasons = [
        line[len(prefix):].strip()
        for line in notes.splitlines()
        if line.startswith(prefix) and line[len(prefix):].strip()
    ]
    return reasons[-1] if reasons else None


def project_campaign_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Validate persistent campaign metadata stored on the coordination Bead."""
    if not isinstance(metadata, dict):
        raise StateContractError("Les métadonnées de campagne doivent former un objet.")
    mode = _text(metadata.get("gc.campaign_mode")) or "inactive"
    if mode == "inactive":
        return {
            "enabled": False,
            "mode": "inactive",
            "state": "inactive",
            "state_label": "Campagne inactive",
            "automatic": False,
            "candidate_id": None,
            "condition": None,
            "owner": "none",
            "owner_label": "Aucun responsable attendu",
            "action": "Aucune action de campagne.",
            "blocked": False,
            "blocker_kind": None,
            "cause": None,
            "wake_key": None,
            "wake_state": "none",
            "failure_count": 0,
            "last_error": None,
        }
    if mode != "automatic":
        raise StateContractError(f"Mode campagne inconnu: {mode}.")

    state = _text(metadata.get("gc.campaign_state"))
    condition = _text(metadata.get("gc.campaign_condition"))
    candidate_id = _text(metadata.get("gc.campaign_candidate"))
    owner = _text(metadata.get("gc.campaign_owner")) or "Mayor"
    action = _text(metadata.get("gc.campaign_action"))
    blocker_kind = _text(metadata.get("gc.campaign_block_kind"))
    cause = _text(metadata.get("gc.campaign_cause"))
    wake_key = _text(metadata.get("gc.campaign_wake_key"))
    wake_state = _text(metadata.get("gc.campaign_wake_state")) or "none"
    failure_raw = metadata.get("gc.campaign_failure_count", 0)
    try:
        failure_count = int(failure_raw)
    except (TypeError, ValueError) as exc:
        raise StateContractError("Le compteur d'échec de campagne est invalide.") from exc
    if failure_count < 0:
        raise StateContractError("Le compteur d'échec de campagne est négatif.")
    if state not in CAMPAIGN_STATES - {"inactive"}:
        raise StateContractError("État de campagne automatique manquant ou inconnu.")
    if not condition or not candidate_id:
        raise StateContractError("Une campagne active doit exposer sa condition et son candidat d'autorisation.")
    if owner not in {"system", "Mayor", "Benjamin", "none"}:
        raise StateContractError("Responsable de campagne inconnu.")
    if wake_state not in {"none", "pending", "sent"}:
        raise StateContractError("État d'idempotence de campagne inconnu.")
    if wake_state != "none" and not wake_key:
        raise StateContractError("Un réveil de campagne doit exposer sa clé d'idempotence.")
    if wake_state == "none" and wake_key:
        raise StateContractError("Une clé de réveil sans état d'idempotence est incohérente.")
    if state == "active" and wake_state in {"pending", "sent"}:
        state = "awaiting_mayor"
    if state == "blocked":
        if blocker_kind not in CAMPAIGN_BLOCK_KINDS or not cause or not action:
            raise StateContractError("Une campagne bloquée doit exposer type, cause et action exacte.")
        if blocker_kind == "decision" and owner != "Benjamin":
            raise StateContractError(
                "Un blocage décisionnel de campagne doit désigner Benjamin comme responsable."
            )
    elif blocker_kind or cause:
        raise StateContractError("Une campagne non bloquée ne peut pas conserver une cause de blocage.")

    labels = {
        "active": "Campagne active",
        "awaiting_mayor": "Campagne active · Mayor réveillé",
        "running": "Campagne active · livraison en cours",
        "blocked": "BLOQUÉ",
        "completed": "Campagne terminée · aucun candidat éligible",
    }
    default_actions = {
        "active": "Aucune action de Benjamin; le sentinelle réveille le Mayor au prochain résultat.",
        "awaiting_mayor": "Aucune action de Benjamin; le Mayor a reçu la transition à exécuter.",
        "running": "Aucune action humaine; le Mayor poursuit une livraison à la fois.",
        "completed": "Aucune action immédiate; enregistrer un nouveau candidat lorsqu'il devient utile.",
    }
    return {
        "enabled": True,
        "mode": "automatic",
        "state": state,
        "state_label": labels[state],
        "automatic": state not in {"blocked", "completed"},
        "candidate_id": candidate_id,
        "condition": condition,
        "owner": owner,
        "owner_label": "Système" if owner == "system" else owner if owner != "none" else "Aucun responsable attendu",
        "action": action or default_actions[state],
        "blocked": state == "blocked",
        "blocker_kind": blocker_kind,
        "cause": cause,
        "wake_key": wake_key,
        "wake_state": wake_state,
        "failure_count": failure_count,
        "last_error": _text(metadata.get("gc.campaign_last_error")),
    }


def project_candidate(item: dict[str, Any], position: int | None = None) -> dict[str, Any]:
    """Return the stable human lifecycle for one active queue candidate."""
    if not isinstance(item, dict):
        raise StateContractError("Un candidat doit être un objet.")
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    candidate_id = _text(item.get("id"))
    title = _text(item.get("title"))
    queue_state = _text(item.get("queue_state")) or _text(metadata.get("gc.queue_state"))
    queue_state = queue_state or _text(item.get("state"))
    technical_status = _text(item.get("technical_status")) or _text(item.get("status")) or "deferred"
    if not candidate_id or not title:
        raise StateContractError("Identité de candidat manquante.")
    if queue_state not in {"queued", "paused"}:
        raise StateContractError(f"État de file actif invalide pour {candidate_id}.")
    if technical_status != "deferred":
        raise StateContractError(
            f"Le candidat actif {candidate_id} n'est pas techniquement différé."
        )

    pause_reason = (
        _text(item.get("pause_reason"))
        or _text(metadata.get("gc.queue_pause_reason"))
        or _structured_pause_reason(item.get("notes"))
    )
    if queue_state == "paused":
        lifecycle_state = "paused"
        state_label = "En pause"
        eligibility = False
        reason = pause_reason or "Raison de pause non renseignée"
    else:
        lifecycle_state = "eligible"
        state_label = "Éligible · non programmé"
        eligibility = True
        reason = "Attend une autorisation EXECUTE et sa matérialisation par le Mayor."

    candidate_position = position if position is not None else item.get("position")
    goal = _text(item.get("goal")) or _text(metadata.get("gc.queue_goal")) or "none"
    urgency = _text(item.get("urgency")) or _text(metadata.get("gc.queue_urgency"))
    urgency_labels = {"normal": "Normale", "urgent": "Urgente", "critical": "Critique"}
    if urgency not in urgency_labels:
        raise StateContractError(f"Urgence invalide pour {candidate_id}.")
    result = {
        "position": candidate_position,
        "id": candidate_id,
        "title": title,
        "state": lifecycle_state,
        "state_label": state_label,
        "eligible": eligibility,
        "reason": reason,
        "pause_reason": pause_reason,
        "urgency": urgency,
        "urgency_label": urgency_labels[urgency],
        "goal": goal,
        "kind": "factory_campaign" if goal == "none" else "product_candidate",
        "kind_label": "Campagne Factory · hors produit" if goal == "none" else "Candidat produit",
        "queue_state": queue_state,
        "technical_status": "deferred",
        "technical_explanation": TECHNICAL_DEFERRED_EXPLANATION,
        "contract": CONTRACT,
    }
    return result


def project_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise StateContractError("La file doit être une liste.")
    return [project_candidate(item, index) for index, item in enumerate(items, 1)]


def candidate_record_lifecycle(item: dict[str, Any]) -> tuple[str, str]:
    """Classify an active or historical candidate without reviving closed work."""
    if not isinstance(item, dict):
        raise StateContractError("Un enregistrement candidat doit être un objet.")
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    queue_state = _text(metadata.get("gc.queue_state"))
    status = _text(item.get("status"))
    if queue_state == "materialized" and status == "closed":
        if not _text(metadata.get("gc.materialized_bead")):
            raise StateContractError("Un candidat matérialisé doit référencer son Bead d'exécution.")
        return "materialized", "Matérialisé"
    if queue_state == "cancelled" and status == "closed":
        return "cancelled", "Annulé"
    if queue_state == "paused" and status == "deferred":
        return "paused", "En pause"
    if queue_state == "queued" and status == "deferred":
        return "eligible", "Éligible · non programmé"
    raise StateContractError(
        f"Cycle candidat incohérent: queue_state={queue_state!r}, status={status!r}."
    )


def _health(infrastructure: dict[str, Any], sources_consistent: bool) -> dict[str, str]:
    running = infrastructure.get("running")
    usable = infrastructure.get("usable")
    degraded = infrastructure.get("degraded", False)
    if (
        not isinstance(running, bool)
        or not isinstance(usable, bool)
        or not isinstance(degraded, bool)
    ):
        raise StateContractError("Santé d'infrastructure incomplète.")
    if not running or not usable:
        return {
            "state": "unavailable",
            "label": "Infrastructure indisponible",
            "detail": "Le contrôleur ou sa capacité à travailler n'est pas confirmé.",
        }
    if degraded or not sources_consistent:
        return {
            "state": "degraded",
            "label": "Infrastructure disponible · visibilité dégradée",
            "detail": "Au moins une source requise manque ou se contredit; la reprise est neutralisée.",
        }
    return {
        "state": "available",
        "label": "Infrastructure disponible",
        "detail": "Le contrôleur est démarré et déclaré utilisable.",
    }


def _result(current: dict[str, Any] | None) -> dict[str, Any]:
    if current is None:
        return {
            "id": None,
            "title": "Aucune livraison en cours",
            "state": "none",
            "state_label": "Aucun résultat en cours",
            "cause": None,
            "agent": None,
            "phase": "Aucune livraison produit n'est active.",
        }
    if not isinstance(current, dict) or not _text(current.get("id")) or not _text(current.get("title")):
        raise StateContractError("Résultat courant incomplet.")
    state = _text(current.get("state"))
    labels = {
        "materialized": "Matérialisé · aucun agent actif",
        "active": "En cours",
        "finalizing": "En finalisation par le Mayor",
        "waiting_dependency": "Attend une dépendance automatique",
        "blocked": "Bloqué",
        "delivered": "Livré",
        "cancelled": "Annulé",
    }
    if state not in labels:
        raise StateContractError(f"Cycle du résultat courant invalide: {state!r}.")
    cause = _text(current.get("cause"))
    if state == "blocked" and not cause:
        raise StateContractError("Un résultat bloqué doit exposer sa cause.")
    return {
        "id": _text(current.get("id")),
        "title": _text(current.get("title")),
        "state": "active" if state in {"finalizing", "waiting_dependency"} else state,
        "state_label": labels[state],
        "stage": state,
        "cause": cause,
        "agent": _text(current.get("agent")),
        "phase": _text(current.get("phase")) or labels[state],
    }


def project_human_state(observed: dict[str, Any]) -> dict[str, Any]:
    """Build the v1 state contract and fail closed on inconsistent inputs."""
    if not isinstance(observed, dict):
        raise StateContractError("L'observation doit être un objet.")
    sources_consistent = observed.get("sources_consistent")
    if not isinstance(sources_consistent, bool):
        raise StateContractError("La cohérence des sources doit être explicite.")
    health = _health(observed.get("infrastructure", {}), sources_consistent)
    queue = project_candidates(observed.get("queue", []))
    current = _result(observed.get("current"))
    needs_benjamin = _text(observed.get("needs_benjamin"))
    blockers = observed.get("blockers", [])
    if not isinstance(blockers, list) or not all(isinstance(item, dict) for item in blockers):
        raise StateContractError("Les blocages doivent former une liste.")
    blocker_cause = next((_text(item.get("cause")) for item in blockers if _text(item.get("cause"))), None)
    product_candidates = [item for item in queue if item["kind"] == "product_candidate"]
    eligible = next((item for item in product_candidates if item["state"] == "eligible"), None)
    paused = [item for item in product_candidates if item["state"] == "paused"]
    policy = observed.get("resume_policy", {"mode": "manual"})
    if not isinstance(policy, dict):
        raise StateContractError("Politique de reprise invalide.")
    resume_mode = _text(policy.get("mode")) or "manual"
    resume_condition = _text(policy.get("condition"))
    if resume_mode not in {"manual", "automatic_dependency", "automatic_campaign"}:
        raise StateContractError("Mode de reprise inconnu.")
    if resume_mode != "manual" and not resume_condition:
        raise StateContractError("Une reprise automatique doit exposer sa condition.")
    campaign = project_campaign_metadata(observed.get("campaign_metadata", {}))
    if resume_mode == "automatic_campaign" and not campaign["enabled"]:
        raise StateContractError("La reprise campagne est déclarée sans campagne persistante active.")
    if campaign["enabled"] and resume_mode != "automatic_campaign":
        raise StateContractError("La campagne persistante et la politique de reprise se contredisent.")

    def effective_campaign_block(
        kind: str, cause: str, owner: str, action: str, *, automatic: bool = False,
    ) -> None:
        campaign.update({
            "state": "blocked",
            "state_label": "BLOQUÉ",
            "automatic": automatic,
            "owner": owner,
            "owner_label": "Système" if owner == "system" else owner,
            "action": action,
            "blocked": True,
            "blocker_kind": kind,
            "cause": cause,
        })

    # An `admin` blocker was recorded on purpose before someone stopped the
    # city. The sources then go unavailable BECAUSE of that window, so
    # diagnosing a source failure would be describing the intended state as a
    # fault. On 2026-09-16 a planned maintenance window reported
    # "Le contrôleur ou sa capacité à travailler n'est pas confirmé" and was
    # indistinguishable from a dead controller -- which is precisely the
    # confusion that costs a human an investigation. A recorded window keeps
    # its own cause, owner and action, exactly as a persisted `decision` block
    # does in the branch below.
    persisted_admin_window = (
        campaign["enabled"]
        and campaign["state"] == "blocked"
        and campaign["blocker_kind"] == "admin"
    )

    # Missing or contradictory required sources always disables action-oriented
    # conclusions, even when the City process itself still answers.
    if health["state"] != "available" and persisted_admin_window:
        activity = {
            "state": "stopped",
            "label": "Arrêtée · fenêtre de maintenance",
            "detail": campaign["cause"],
        }
        resume = {
            "automatic": False,
            "mode": "manual",
            "trigger": None,
            "condition": "Fin de la fenêtre de maintenance, puis preuve d'intégrité des stores.",
            "owner": campaign["owner"],
            "owner_label": campaign["owner_label"],
            "action": campaign["action"],
            "prompt": "La Factory est arrêtée volontairement. Ne rien diagnostiquer : attendre la fin de la fenêtre.",
            "required": False,
        }
        # campaign is left exactly as recorded: kind, cause, owner and action.
    elif health["state"] != "available":
        activity = {
            "state": "stopped",
            "label": "Arrêtée · état non fiable",
            "detail": "Aucune reprise n'est conseillée tant que les sources ne concordent pas.",
        }
        resume = {
            "automatic": False,
            "mode": "fail_closed",
            "trigger": None,
            "condition": "Rétablir et réconcilier les sources déterministes.",
            "owner": "Mayor",
            "owner_label": "Mayor",
            "action": "Demander au Mayor un diagnostic en lecture seule.",
            "prompt": "Diagnostique l’état de la Factory en lecture seule et réconcilie ses sources avant toute reprise.",
            "required": True,
        }
        if campaign["enabled"]:
            effective_campaign_block(
                "source_failure", health["detail"], "Mayor", resume["action"]
            )
    elif needs_benjamin:
        persisted_decision_block = (
            campaign["enabled"]
            and campaign["state"] == "blocked"
            and campaign["blocker_kind"] == "decision"
        )
        decision_owner = campaign["owner"] if persisted_decision_block else "Benjamin"
        decision_action = (
            campaign["action"]
            if persisted_decision_block
            else "Répondre à la décision bloquante."
        )
        activity = {
            "state": "waiting_action",
            "label": "Attend une décision de Benjamin",
            "detail": needs_benjamin,
        }
        resume = {
            "automatic": False,
            "mode": "blocking_decision",
            "trigger": None,
            "condition": needs_benjamin,
            "owner": decision_owner,
            "owner_label": decision_owner,
            "action": decision_action,
            "prompt": f"Explique cette décision bloquante et ses options : {needs_benjamin}",
            "required": True,
        }
        if campaign["enabled"] and not persisted_decision_block:
            effective_campaign_block(
                "decision", needs_benjamin, "Benjamin", resume["action"]
            )
    elif campaign["enabled"] and campaign["state"] == "blocked":
        if campaign["blocker_kind"] == "decision" and not needs_benjamin:
            raise StateContractError(
                "Un blocage de campagne décisionnel doit être la décision NEEDS BENJAMIN effective."
            )
        activity = {
            "state": "waiting_action",
            "label": "BLOQUÉ · campagne arrêtée",
            "detail": campaign["cause"],
        }
        resume = {
            "automatic": False,
            "mode": "campaign_blocked",
            "trigger": None,
            "condition": campaign["cause"],
            "owner": campaign["owner"],
            "owner_label": campaign["owner_label"],
            "action": campaign["action"],
            "prompt": (
                f"Reprends la campagne autorisée après avoir exécuté exactement cette action : {campaign['action']}"
                if campaign["owner"] == "Mayor" else None
            ),
            "required": True,
        }
    elif campaign["enabled"] and campaign["failure_count"] > 0 and campaign["last_error"]:
        cause = (
            f"Le sentinelle n'a pas pu vérifier ou réveiller le Mayor "
            f"({campaign['failure_count']}/3) : {campaign['last_error']}"
        )
        effective_campaign_block(
            "transient_failure",
            cause,
            "system",
            "Aucune action de Benjamin; une nouvelle tentative automatique est programmée.",
            automatic=True,
        )
        activity = {
            "state": "waiting_automatic",
            "label": "BLOQUÉ · nouvelle tentative automatique",
            "detail": cause,
        }
        resume = {
            "automatic": True,
            "mode": "automatic_campaign",
            "trigger": campaign["condition"],
            "condition": "Nouvelle tentative du sentinelle au prochain intervalle.",
            "owner": "system",
            "owner_label": "Système",
            "action": campaign["action"],
            "prompt": None,
            "required": False,
        }
    elif current.get("stage") == "blocked" or blocker_cause:
        cause = current.get("cause") or blocker_cause
        activity = {
            "state": "waiting_action",
            "label": "Attend un déblocage",
            "detail": cause,
        }
        resume = {
            "automatic": False,
            "mode": "blocked",
            "trigger": None,
            "condition": cause,
            "owner": "Mayor",
            "owner_label": "Mayor",
            "action": "Diagnostiquer et lever le blocage identifié.",
            "prompt": f"Diagnostique et lève uniquement ce blocage déjà autorisé : {cause}",
            "required": True,
        }
        if campaign["enabled"]:
            effective_campaign_block("result_blocker", cause, "Mayor", resume["action"])
    elif current.get("stage") == "finalizing":
        activity = {
            "state": "waiting_automatic" if campaign["enabled"] else "waiting_action",
            "label": (
                "Attend automatiquement la finalisation du Mayor"
                if campaign["enabled"] else "Attend la finalisation du Mayor"
            ),
            "detail": current["phase"],
        }
        resume = {
            "automatic": campaign["enabled"],
            "mode": "mayor_finalization",
            "trigger": None,
            "condition": "Revue, preuves exactes, fusion et clôture par le Mayor.",
            "owner": "Mayor",
            "owner_label": "Mayor",
            "action": (
                "Aucune action de Benjamin; le sentinelle réveille le Mayor pour finaliser."
                if campaign["enabled"] else "Le Mayor finalise la livraison déjà autorisée."
            ),
            "prompt": f"Finalise la livraison déjà autorisée « {current['title']} » avec ses preuves exactes.",
            "required": not campaign["enabled"],
        }
        if campaign["enabled"]:
            campaign.update({"state": "running", "state_label": "Campagne active · livraison en cours"})
    elif current.get("stage") == "waiting_dependency" or resume_mode == "automatic_dependency":
        condition = resume_condition or current["phase"]
        activity = {
            "state": "waiting_automatic",
            "label": "Attend automatiquement une dépendance",
            "detail": condition,
        }
        resume = {
            "automatic": True,
            "mode": "automatic_dependency",
            "trigger": condition,
            "condition": condition,
            "owner": "system",
            "owner_label": "Système",
            "action": "Aucune action humaine tant que la condition n'est pas satisfaite.",
            "prompt": None,
            "required": False,
        }
    elif current.get("state") == "active" and current.get("agent"):
        activity = {
            "state": "working",
            "label": "Travaille",
            "detail": current["phase"],
        }
        resume = {
            "automatic": True,
            "mode": "active_delivery",
            "trigger": "La livraison en cours poursuit ses étapes autorisées.",
            "condition": current["phase"],
            "owner": "system",
            "owner_label": "Système",
            "action": "Aucune action humaine nécessaire.",
            "prompt": None,
            "required": False,
        }
        if campaign["enabled"]:
            campaign.update({"state": "running", "state_label": "Campagne active · livraison en cours"})
    elif current.get("state") == "materialized" or current.get("state") == "active":
        activity = {
            "state": "waiting_automatic" if campaign["enabled"] else "waiting_action",
            "label": "Attend automatiquement le Mayor" if campaign["enabled"] else "Attend une action du Mayor",
            "detail": "Un résultat est matérialisé, mais aucun agent produit n'est actif.",
        }
        resume = {
            "automatic": campaign["enabled"],
            "mode": "materialized_without_agent",
            "trigger": None,
            "condition": "Affectation ou reprise du résultat matérialisé.",
            "owner": "Mayor",
            "owner_label": "Mayor",
            "action": (
                "Aucune action de Benjamin; le sentinelle réveille le Mayor pour reprendre ce résultat."
                if campaign["enabled"] else "Le Mayor affecte ou reprend le résultat déjà matérialisé."
            ),
            "prompt": f"Reprends le résultat matérialisé « {current['title']} » sans élargir son périmètre.",
            "required": not campaign["enabled"],
        }
        if campaign["enabled"]:
            campaign.update({"state": "running", "state_label": "Campagne active · livraison en cours"})
    elif resume_mode == "automatic_campaign" and eligible:
        activity = {
            "state": "waiting_automatic",
            "label": "Attend automatiquement le prochain résultat",
            "detail": resume_condition,
        }
        resume = {
            "automatic": True,
            "mode": "automatic_campaign",
            "trigger": resume_condition,
            "condition": resume_condition,
            "owner": "Mayor",
            "owner_label": "Mayor",
            "action": "Aucune action de Benjamin; le sentinelle réveille le Mayor pour lancer le prochain résultat.",
            "prompt": None,
            "required": False,
        }
        if campaign["state"] != "awaiting_mayor":
            campaign.update({"state": "active", "state_label": "Campagne active"})
    elif eligible:
        activity = {
            "state": "waiting_action",
            "label": "Attend une action facultative",
            "detail": "Aucune livraison en cours; la reprise n'est pas automatique car le mode campagne n'est pas actif.",
        }
        resume = {
            "automatic": False,
            "mode": "manual",
            "trigger": "Autorisation EXECUTE explicite de Benjamin.",
            "condition": f"Demander le lancement du candidat éligible {eligible['id']}.",
            "owner": "Benjamin",
            "owner_label": "Benjamin",
            "action": "Demander « Lance le prochain résultat ».",
            "prompt": "Lance le prochain résultat.",
            "required": False,
        }
    elif paused:
        activity = {
            "state": "waiting_action",
            "label": "Attend une action facultative",
            "detail": "Tous les candidats sont en pause; aucun résultat n'est éligible.",
        }
        resume = {
            "automatic": False,
            "mode": "all_paused",
            "trigger": "Reprise explicite d'un candidat.",
            "condition": "Lever une pause après résolution de sa raison.",
            "owner": "Benjamin",
            "owner_label": "Benjamin",
            "action": "Revoir les raisons de pause; reprendre un candidat seulement si elles sont levées.",
            "prompt": "Explique les raisons de pause des candidats, sans en reprendre ni en lancer aucun.",
            "required": False,
        }
        if campaign["enabled"]:
            cause = "Tous les candidats produit sont en pause; aucun résultat n'est éligible."
            action = "Aucune action immédiate de Benjamin; le Mayor vérifie la raison de chaque pause et signale seulement la décision réellement nécessaire."
            effective_campaign_block("all_paused", cause, "Mayor", action)
            activity = {
                "state": "waiting_action",
                "label": "BLOQUÉ · tous les candidats sont en pause",
                "detail": cause,
            }
            resume = {
                "automatic": False,
                "mode": "campaign_blocked",
                "trigger": None,
                "condition": cause,
                "owner": "Mayor",
                "owner_label": "Mayor",
                "action": action,
                "prompt": "Vérifie les raisons de pause de la campagne et demande Benjamin seulement si sa décision est indispensable.",
                "required": True,
            }
    else:
        activity = {
            "state": "stopped",
            "label": "Arrêtée · aucun résultat en cours",
            "detail": "Aucune livraison ni aucun candidat produit éligible.",
        }
        resume = {
            "automatic": False,
            "mode": "no_candidate",
            "trigger": None,
            "condition": "Un nouveau candidat doit d'abord être décidé et enregistré.",
            "owner": "none",
            "owner_label": "Aucun responsable attendu",
            "action": "Aucune action immédiate; définir un prochain résultat lorsque cela devient utile.",
            "prompt": None,
            "required": False,
        }
        if campaign["enabled"]:
            campaign.update({
                "state": "completed",
                "state_label": "Campagne terminée · aucun candidat éligible",
                "automatic": False,
                "owner": "none",
                "owner_label": "Aucun responsable attendu",
                "action": "Aucune action immédiate; enregistrer un nouveau candidat lorsqu'il devient utile.",
                "blocked": False,
                "blocker_kind": None,
                "cause": None,
            })

    return {
        "contract": CONTRACT,
        "schema_version": 1,
        "health": health,
        "activity": activity,
        "result": current,
        "resume": resume,
        "campaign": campaign,
        "next_candidate": eligible,
        "queue": queue,
        "needs_benjamin": needs_benjamin,
        "blocking_decision": needs_benjamin,
    }
