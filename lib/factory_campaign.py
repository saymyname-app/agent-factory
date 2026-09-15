#!/usr/bin/env python3
"""Pure transition planner for the Mayor-owned continuous campaign."""

from __future__ import annotations

from typing import Any


FAILURE_THRESHOLD = 3


class CampaignDecisionError(ValueError):
    """The canonical status cannot safely drive a campaign transition."""


def plan_transition(status: dict[str, Any]) -> dict[str, Any]:
    """Return a mechanical Mayor notification plan without mutating lifecycle state."""
    if not isinstance(status, dict) or status.get("contract") != "agent-factory-human-state/v1":
        raise CampaignDecisionError("Le statut humain canonique est absent ou invalide.")
    campaign = status.get("campaign")
    resume = status.get("resume")
    result = status.get("result")
    if not all(isinstance(item, dict) for item in (campaign, resume, result)):
        raise CampaignDecisionError("Le statut ne contient pas les axes campagne, reprise et résultat.")
    if not campaign.get("enabled"):
        return {"action": "none", "reason": "campaign_inactive", "wake_key": None}
    if campaign.get("blocked"):
        return {"action": "none", "reason": "campaign_blocked", "wake_key": None}

    result_id = result.get("id")
    resume_mode = resume.get("mode")
    if campaign.get("state") == "completed" and resume_mode == "no_candidate":
        return {"action": "none", "reason": "campaign_complete", "wake_key": None}
    if resume_mode in {"active_delivery", "automatic_dependency"}:
        return {"action": "none", "reason": resume_mode, "wake_key": None}
    if resume_mode == "mayor_finalization" and result_id:
        return {
            "action": "wake_mayor",
            "reason": "finalize_current",
            "wake_key": f"finalize:{result_id}",
            "subject": f"CAMPAGNE · finaliser {result_id}",
            "message": (
                f"La campagne autorisée attend la finalisation du résultat {result_id}. "
                "Vérifie la revue exacte, la CI, la fusion et la clôture, puis poursuis un seul résultat à la fois."
            ),
        }
    if resume_mode == "materialized_without_agent" and result_id:
        return {
            "action": "wake_mayor",
            "reason": "resume_current",
            "wake_key": f"resume:{result_id}",
            "subject": f"CAMPAGNE · reprendre {result_id}",
            "message": (
                f"Le résultat matérialisé {result_id} n'a aucun agent produit actif. "
                "Reprends uniquement ce résultat déjà autorisé; ne matérialise aucun autre candidat."
            ),
        }
    if resume_mode == "automatic_campaign":
        candidate = status.get("next_candidate")
        release = status.get("release")
        release_selection = None
        if release is not None:
            if (
                not isinstance(release, dict)
                or release.get("contract") != "agent-factory-product-release/v1"
                or release.get("state") not in {"approved", "executing"}
                or not isinstance(release.get("campaign"), dict)
            ):
                raise CampaignDecisionError(
                    "La campagne ne peut pas consommer une release absente, non approuvée ou invalide."
                )
            release_selection = release["campaign"].get("selected")
            if release_selection is None:
                return {
                    "action": "none",
                    "reason": str(release["campaign"].get("reason") or "release_not_actionable"),
                    "wake_key": None,
                    "owner": release["campaign"].get("owner"),
                    "recovery_action": release["campaign"].get("action"),
                }
            if not isinstance(release_selection, dict) or not release_selection.get("work_ref"):
                raise CampaignDecisionError("La sélection de release n'expose pas de travail stable.")
        if isinstance(candidate, dict) and candidate.get("id"):
            candidate_id = str(candidate["id"])
            if release_selection and release_selection["work_ref"] != candidate_id:
                raise CampaignDecisionError(
                    "Le premier candidat de file ne correspond pas au premier nœud release sûr; arrêt fail-closed."
                )
            criteria = (
                ", ".join(release_selection.get("criterion_refs", []))
                if release_selection else "contrat historique de file"
            )
            return {
                "action": "wake_mayor",
                "reason": "materialize_next",
                "wake_key": f"materialize:{candidate_id}",
                "subject": f"CAMPAGNE · prochain résultat {candidate_id}",
                "message": (
                    f"La campagne autorisée peut enchaîner le candidat éligible {candidate_id}. "
                    f"Traçabilité release: {criteria}. "
                    "Relis ses critères, crée son Bead d'exécution, matérialise strictement le premier "
                    "candidat produit éligible, puis livre-le par le flux normal."
                ),
            }
        return {"action": "none", "reason": "automatic_retry", "wake_key": None}
    if resume_mode == "no_candidate":
        return {
            "action": "wake_mayor",
            "reason": "record_complete",
            "wake_key": "complete:no-candidate",
            "subject": "CAMPAGNE · file éligible terminée",
            "message": (
                "La campagne ne trouve plus de candidat produit éligible. Vérifie la file, puis enregistre "
                "l'état transparent avec `./bin/mayor-campaign complete --mayor`; ne crée aucun résultat."
            ),
        }
    return {"action": "none", "reason": str(resume_mode or "not_actionable"), "wake_key": None}
