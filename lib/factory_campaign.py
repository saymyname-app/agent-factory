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
                "Vérifie la revue exacte, la CI, la fusion et la clôture, puis poursuis un seul résultat à la fois. "
                f"Finaliser veut dire : clore {result_id} avec `./bin/deliver-close {result_id} --repo <owner/repo> "
                "--pr <n>` (jamais `gc bd close`, même s'il est déjà fermé : ses six preuves manquent sinon), puis "
                f"pointer `gc.last_delivered` sur {result_id} et avancer `gc.current` sur la coordination. "
                "Tant que ce n'est pas fait, la campagne ne peut pas lancer le candidat suivant."
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


# --- Idle ladder (ADR-0016 section 7) -----------------------------------------
#
# "No eligible product candidate" used to be a state the campaign reported and
# waited in: the sentinel woke the Mayor once to record completion -- with the
# explicit instruction to create nothing -- and then returned NOOP forever. The
# factory could sit idle for hours with a queue of Factory work in front of it.
#
# The ladder replaces that state. Rung 1 (product) is plan_transition above.
# When it has nothing to do, the sentinel walks down:
#
#   2. a ready, city-level Factory bead -- repair items, improvement tasks;
#   3. test hardening and flake removal   -- a bounded audit, at most every 12h;
#   4. backlog grooming and documentation debt -- at most every 24h.
#
# Rungs 3 and 4 are generative: there is no bead to point at, so the Mayor is
# asked to find one bounded thing and file it. They are throttled because a
# wake costs tokens, and an audit repeated every minute finds nothing new. The
# only NOOP left is "rested": every generative rung ran within its window and
# no Factory bead is ready. That is a deliberate, time-boxed pause, not a stop.

LADDER_GENERATIVE_RUNGS = (
    ("tests", 12 * 3600),
    ("docs", 24 * 3600),
)
LADDER_STALE_SECONDS = 6 * 3600

# Not Factory work, or not ours to take.
_LADDER_EXCLUDED_TYPES = {
    "session", "convoy", "message", "molecule", "epic", "gate", "event", "agent",
}
_LADDER_EXCLUDED_LABELS = {
    "product-goal", "roadmap", "saymyname", "gc:session", "gc:nudge",
    # Upstream problems are not ours to work (Benjamin, 2026-09-16).
    "upstream",
}
# Present on internal workflow steps and on work explicitly waiting on someone.
_LADDER_EXCLUDED_METADATA = ("gc.step_ref", "gc.root_bead_id", "gc.synthetic", "gc.waiting_on")


def _labels(bead: dict[str, Any]) -> set[str]:
    value = bead.get("labels")
    return {str(item) for item in value} if isinstance(value, list) else set()


def is_ladder_bead(bead: Any) -> bool:
    """True for a ready, city-level Factory bead the Mayor may take."""
    if not isinstance(bead, dict) or not bead.get("id"):
        return False
    if str(bead.get("status") or "open") != "open":
        return False
    kind = str(bead.get("issue_type") or bead.get("type") or "").lower()
    if kind in _LADDER_EXCLUDED_TYPES:
        return False
    if _labels(bead) & _LADDER_EXCLUDED_LABELS:
        return False
    metadata = bead.get("metadata") if isinstance(bead.get("metadata"), dict) else {}
    if any(str(metadata.get(key) or "").strip() for key in _LADDER_EXCLUDED_METADATA):
        return False
    needs = str(metadata.get("gc.needs_benjamin") or "").strip().lower()
    if needs and not needs.startswith("none"):
        return False
    assignee = str(bead.get("assignee") or "").strip()
    if assignee and assignee != "mayor":
        return False
    return True


def _priority(bead: dict[str, Any]) -> int:
    try:
        return int(bead.get("priority"))
    except (TypeError, ValueError):
        return 9


def _epoch(value: Any) -> float | None:
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _first_eligible_factory_queue_candidate(
    queue_candidates: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """First eligible ``goal=none`` candidate from ``saymyname-product-queue list --json``.

    That queue lane (audit finding C3) is read by nobody today: neither
    ``plan_transition`` (product-only) nor the ladder. It sits behind rung 2
    (an already-filed Factory bead) and ahead of the generative rungs, because
    a queued, refined candidate is more actionable than "go find something".
    """
    if not isinstance(queue_candidates, list):
        return None
    for item in queue_candidates:
        if (
            isinstance(item, dict)
            and item.get("kind") == "factory_campaign"
            and item.get("state") == "eligible"
            and item.get("id")
        ):
            return item
    return None


def plan_idle_ladder(
    ready: list[dict[str, Any]],
    now: float,
    last_generative: dict[str, Any] | None = None,
    tracked: dict[str, Any] | None = None,
    queue_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pick the next rung when product work has nothing to do.

    ``ready`` is ``gc bd ready --json`` for the city store. ``last_generative``
    maps a generative rung name to the ISO time it was last sent.
    ``tracked`` is the rung-2 bead the Mayor was last pointed at, if any.
    ``queue_candidates`` is ``saymyname-product-queue list --json`` (rung 2b).
    """
    last_generative = last_generative or {}

    # One Factory bead at a time, exactly like product results.
    if isinstance(tracked, dict) and tracked.get("status") == "in_progress":
        updated = _epoch(tracked.get("updated_at"))
        if updated is not None and now - updated > LADDER_STALE_SECONDS:
            # C6: this used to return a terminal NOOP forever, so one stuck
            # bead (af-6eqc, live) permanently starved rung 2 of ever trying a
            # different candidate. Stop tracking it -- the caller marks it
            # gc.waiting_on so is_ladder_bead excludes it even if it later
            # reopens -- and fall through to pick the next one in this same
            # tick. Liveness still sees no real progress: this path is reached
            # only through "none"/"ladder_*" reasons, never a PROGRESS_REASON.
            plan = plan_idle_ladder(ready, now, last_generative, None, queue_candidates)
            plan["unstick_bead"] = tracked.get("id")
            return plan
        return {"action": "none", "reason": "ladder_active", "wake_key": None,
                "ladder_bead": tracked.get("id")}

    candidates = sorted(
        (bead for bead in ready if is_ladder_bead(bead)),
        key=lambda bead: (_priority(bead), str(bead.get("created_at") or ""), str(bead["id"])),
    )
    if candidates:
        bead = candidates[0]
        bead_id = str(bead["id"])
        title = str(bead.get("title") or "").strip()
        return {
            "action": "wake_mayor",
            "reason": "ladder_factory",
            "rung": "factory",
            "ladder_bead": bead_id,
            "wake_key": f"ladder:factory:{bead_id}",
            "subject": f"USINE · amélioration {bead_id}",
            "message": (
                "Aucun résultat produit n'est éligible : ce n'est pas de l'inactivité "
                "(ADR-0016 §7, échelle d'inactivité, échelon 2). "
                f"Prends le bead Factory {bead_id} — « {title} » (P{_priority(bead)}). "
                f"Réclame-le (`gc bd update {bead_id} --claim`), livre-le par le flux normal "
                "avec ses preuves, puis ferme-le. S'il attend quelqu'un ou quelque chose, pose "
                f"`gc bd update {bead_id} --set-metadata gc.waiting_on=<qui>` : l'échelle le "
                "sautera. Un seul à la fois ; si un candidat produit redevient éligible, il passe devant."
            ),
        }

    queue_candidate = _first_eligible_factory_queue_candidate(queue_candidates)
    if queue_candidate is not None:
        candidate_id = str(queue_candidate["id"])
        title = str(queue_candidate.get("title") or "").strip()
        return {
            "action": "wake_mayor",
            "reason": "ladder_factory_queue",
            "rung": "factory_queue",
            "ladder_bead": None,
            "wake_key": f"materialize:{candidate_id}",
            "subject": f"USINE · candidat file {candidate_id}",
            "message": (
                "Aucun bead Factory prêt, mais la file `goal=none` a un candidat éligible "
                "(ADR-0016 §7, échelon 2b). "
                f"Relis {candidate_id} — « {title} », crée son Bead d'exécution, puis "
                f"`./bin/saymyname-product-queue materialize {candidate_id} <execution-bead> --mayor`, "
                "et livre-le par le flux normal. Un seul candidat matérialisé à la fois ; si un "
                "bead Factory ou un candidat produit redevient éligible, il passe devant."
            ),
        }

    for rung, period in LADDER_GENERATIVE_RUNGS:
        last = _epoch(last_generative.get(rung))
        if last is not None and now - last < period:
            continue
        bucket = int(now // period)
        hours = period // 3600
        if rung == "tests":
            subject = "USINE · durcissement des tests"
            body = (
                "Ni produit ni bead Factory prêt (échelle d'inactivité, échelon 3). "
                "Cherche UN test instable ou UN trou de couverture sur l'usine : échecs récents "
                "(`gh run list --status failure --limit 20`), tests marqués `# ci: local-only`, "
                "`./bin/factory-doctor`. Crée un bead Factory étiqueté `factory-ladder` pour ce "
                "que tu entreprends, puis livre-le. Si rien ne le mérite, ne crée rien."
            )
        else:
            subject = "USINE · backlog et dette documentaire"
            body = (
                "Ni produit ni bead Factory prêt (échelle d'inactivité, échelon 4). "
                "Fais UNE passe bornée : ferme les beads obsolètes ou en double, corrige une "
                "dérive entre docs/CONTEXT_INDEX.md et la réalité, ou une commande périmée dans "
                "docs/. Crée un bead Factory étiqueté `factory-ladder` pour ce que tu entreprends. "
                "Si rien ne le mérite, ne crée rien."
            )
        return {
            "action": "wake_mayor",
            "reason": f"ladder_{rung}",
            "rung": rung,
            "ladder_bead": None,
            "wake_key": f"ladder:{rung}:{bucket}",
            "subject": subject,
            "message": f"{body} Prochain passage de cet échelon au plus tôt dans {hours} h.",
        }

    return {"action": "none", "reason": "ladder_rested", "wake_key": None}
