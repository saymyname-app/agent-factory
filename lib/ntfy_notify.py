#!/usr/bin/env python3
"""Turn a factory-cockpit snapshot into phone pushes Benjamin can act on.

Wave 0-bis (2026-09-17 audit, finding C1) put a push channel in place. On
2026-09-18 Benjamin set the contract for what a push must say:

  - the REAL state, in one plain sentence;
  - what he REALLY has to do, in exactly one of three shapes:
      * nothing -- and what to follow instead;
      * an easy action he can do himself;
      * a delegation -- with a short natural-language sentence he can type
        (or dictate) to the PO session, word for word;
  - never a bead number or anything he would have to transcribe.

This module is the pure, testable half: it reads the JSON that
`bin/factory-cockpit snapshot` already produces and returns alerts with a
stable key (for dedupe/throttle), a title, a body in that shape, and a
priority. It never talks to the network -- see `bin/ntfy-notify`.
"""
from __future__ import annotations

import calendar
import re
import time
from typing import Any

# Bead ids (af-1vr4, smb-v8p, af-u8id.4.1 ...) never reach the phone.
_BEAD_ID = re.compile(r"\b(?:af|smb|smf|hq)-[a-z0-9]{3,}(?:\.[a-z0-9]+)*\b", re.I)
# Escalation windows for "nothing to do, follow it" situations that persist.
MAYOR_SILENCE_SECONDS = 60 * 60
WARNING_PERSIST_SECONDS = 24 * 60 * 60

NOTHING = "nothing"
EASY = "easy"
DELEGATE = "delegate"

# The delegation sentences. Short enough to dictate; the PO session knows
# how to find the exact bead from the live state, Benjamin does not need to.
PROMPTS = {
    "blocked": "L'usine est bloquée : trouve la cause réelle, répare, et demande le correctif de fond.",
    "decision": "Explique-moi la décision en attente et propose ton choix.",
    "mayor_silent": "Le Mayor n'a pas repris l'usine depuis une heure : vérifie pourquoi et débloque.",
    "warnings": "Regarde les avertissements de l'usine et dis-moi s'il faut agir.",
    "result": "Le résultat en cours est bloqué : trouve ce qui manque et débloque-le ou dis-moi quoi faire.",
    "unknown": "Regarde l'état de l'usine et dis-moi ce qu'il faut faire.",
}


def _plain(text: Any) -> str:
    """One line, no bead ids, no double spaces, no trailing period noise."""
    value = _BEAD_ID.sub("", str(text or "")).replace("\n", " ")
    value = re.sub(r"\s{2,}", " ", value).strip(" -:;,.")
    return value


def _todo(kind: str, text: str) -> str:
    if kind == NOTHING:
        return f"À FAIRE : rien. {text}"
    if kind == EASY:
        return f"À FAIRE (facile) : {text}"
    return f"À FAIRE : délègue-moi. Écris-moi : « {text} »"


def _alert(key: str, title: str, state: str, kind: str, todo: str, priority: str) -> dict[str, str]:
    return {
        "key": key,
        "title": title,
        "message": f"ÉTAT : {state}\n{_todo(kind, todo)}",
        "priority": priority,
        "kind": kind,
    }


def providers_exhausted_until(provider_state: Any, now: float) -> str | None:
    """Local HH:MM of the earliest quota return if EVERY pool is exhausted, else None."""
    pools = (provider_state or {}).get("pools") or {}
    if not pools:
        return None
    returns = []
    for pool in pools.values():
        if (pool or {}).get("status") != "exhausted":
            return None
        try:
            until = calendar.timegm(time.strptime(str(pool.get("until"))[:19], "%Y-%m-%dT%H:%M:%S"))
        except (TypeError, ValueError):
            continue
        if until > now:
            returns.append(until)
    if not returns:
        return None
    lt = time.localtime(min(returns))
    return f"{lt.tm_hour:02d}h{lt.tm_min:02d}"


def compute_alerts(snapshot: dict[str, Any], first_seen: dict[str, float] | None = None,
                   now: float | None = None) -> list[dict[str, str]]:
    """Return the alert-worthy findings, each already phrased for the phone.

    `first_seen` maps alert key -> epoch of its first appearance, so a
    "nothing to do, the Mayor is on it" situation that outlives its window
    turns into a delegation instead of staying quiet forever.
    """
    first_seen = first_seen or {}
    now = time.time() if now is None else now
    alerts: list[dict[str, str]] = []
    human = snapshot.get("human_state") or {}
    campaign = human.get("campaign") or {}
    resume = human.get("resume") or {}

    def age(key: str) -> float:
        return now - first_seen.get(key, now)

    # 0. Every provider pool exhausted: nothing can run, whatever the campaign
    # says. On 2026-09-18 the Factory sat idle 05:20-13:00 on quota while the
    # phone said "l'usine avance" (all_paused) -- the state was a lie.
    quota_until = providers_exhausted_until(snapshot.get("provider_state"), now)
    if quota_until:
        alerts.append(_alert("quota_exhausted", "Usine : à l'arrêt, quota épuisé",
                             f"tous les fournisseurs IA sont à court de quota ; rien ne tourne jusqu'à {quota_until}.",
                             NOTHING, "Elle repart seule au retour du quota.", "default"))
        return alerts

    # 1. A blocked campaign is the state that matters most; say why in one line.
    if campaign.get("blocked"):
        kind = str(campaign.get("blocker_kind") or "inconnu")
        key = f"campaign_blocked:{kind}"
        cause = _plain(campaign.get("cause")) or "cause non précisée"
        if kind == "admin":
            action = _plain(campaign.get("action")) or "voir le cockpit"
            alerts.append(_alert(key, "Usine : en pause (action à toi)",
                                 f"l'usine est en pause volontaire — {cause}.",
                                 EASY, action, "default"))
        elif kind == "limit":
            alerts.append(_alert(key, "Usine : en attente de quota",
                                 f"l'usine attend le retour d'un quota — {cause}.",
                                 NOTHING, "Elle repart seule quand le quota revient.", "low"))
        elif kind == "all_paused":
            # The product lane is paused on purpose (factory-first, 2026-09-18);
            # the cockpit calls that "BLOQUÉ" but the factory lane keeps working.
            alerts.append(_alert(key, "Usine : produit en pause, usine au travail",
                                 "les tâches produit sont en pause volontairement ; l'usine avance sur ses propres tâches.",
                                 NOTHING, "Suis l'avancée des tâches usine sur le cockpit.", "low"))
        elif kind == "transient_failure":
            alerts.append(_alert(key, "Usine : nouvelle tentative en cours",
                                 f"une lecture a échoué, l'usine réessaie toute seule — {cause}.",
                                 NOTHING, "Tu seras prévenu si ça dure.", "low"))
        elif kind == "result_blocker":
            alerts.append(_alert(key, "Usine : un résultat est bloqué",
                                 f"le résultat en cours est bloqué — {cause}.",
                                 DELEGATE, PROMPTS["result"], "urgent"))
        elif kind == "decision":
            alerts.append(_alert(key, "Usine : décision attendue",
                                 f"l'usine attend une décision de toi — {cause}.",
                                 DELEGATE, PROMPTS["decision"], "urgent"))
        else:
            alerts.append(_alert(key, "Usine : bloquée",
                                 f"l'usine s'est arrêtée toute seule ({kind}) — {cause}.",
                                 DELEGATE, PROMPTS["blocked"], "urgent"))

    # 2. A pending decision outside the campaign block.
    needs = human.get("needs_benjamin") or snapshot.get("needs_benjamin")
    if needs and not any(a["key"].startswith("campaign_blocked:decision") for a in alerts):
        alerts.append(_alert("needs_benjamin", "Usine : décision attendue",
                             f"une décision t'attend — {_plain(needs)}.",
                             DELEGATE, PROMPTS["decision"], "urgent"))

    # 3. A resume that someone must trigger.
    if resume.get("required") and not campaign.get("blocked"):
        mode = str(resume.get("mode") or "unknown")
        key = f"resume:{mode}"
        owner = str(resume.get("owner") or "")
        if owner.lower() == "benjamin":
            alerts.append(_alert(key, "Usine : action à toi pour reprendre",
                                 f"l'usine attend ton geste — {_plain(resume.get('condition'))}.",
                                 EASY, _plain(resume.get("action")) or "voir le cockpit", "urgent"))
        elif age(key) >= MAYOR_SILENCE_SECONDS:
            alerts.append(_alert(key, "Usine : le Mayor ne reprend pas",
                                 "l'usine attend le Mayor depuis plus d'une heure.",
                                 DELEGATE, PROMPTS["mayor_silent"], "urgent"))
        else:
            alerts.append(_alert(key, "Usine : reprise en cours",
                                 f"l'usine attend une reprise par le Mayor — {_plain(resume.get('condition'))}.",
                                 NOTHING, "Le Mayor est prévenu ; tu seras rappelé s'il ne bouge pas d'ici une heure.",
                                 "default"))

    # 4. Guard warnings: follow, and escalate only if they outlive a day.
    warnings = [w if isinstance(w, str) else str((w or {}).get("message", w)) if isinstance(w, dict) else str(w)
                for w in (snapshot.get("warnings") or [])]
    if warnings:
        key = "warnings"
        n = len(warnings)
        if age(key) >= WARNING_PERSIST_SECONDS:
            alerts.append(_alert(key, "Usine : avertissements qui durent",
                                 f"{n} avertissement(s) tournent depuis plus d'un jour.",
                                 DELEGATE, PROMPTS["warnings"], "default"))
        else:
            # Raw guard text is for the cockpit, not the phone (2026-09-18:
            # "pas de texte d'exception brut").
            alerts.append(_alert(key, "Usine : avertissement",
                                 f"{n} avertissement(s) de surveillance, rien de bloquant.",
                                 NOTHING, "Suis-les dans le cockpit ; je te préviens s'ils durent.", "low"))

    return alerts


def compute_digest(snapshot: dict[str, Any], alerts: list[dict[str, str]]) -> dict[str, str]:
    """The twice-a-day summary: real state + what to do (or follow), no ids."""
    human = snapshot.get("human_state") or {}
    activity = _plain((human.get("activity") or {}).get("label")) or "état inconnu"
    result = human.get("result") or {}
    last = snapshot.get("last_delivery") or {}
    queue = snapshot.get("queue") or []
    factory_open = sum(1 for q in queue if q.get("goal") == "none" and q.get("state") == "eligible")
    product_open = sum(1 for q in queue if q.get("goal") != "none" and q.get("state") == "eligible")
    product_paused = sum(1 for q in queue if q.get("goal") != "none" and q.get("state") == "paused")

    lines = [f"ÉTAT : {activity}."]
    if result.get("id"):
        lines.append(f"En cours : {_plain(result.get('title'))}.")
    if last.get("title"):
        lines.append(f"Dernière livraison : {_plain(last.get('title'))}.")
    lines.append(f"File : {factory_open} tâche(s) usine prête(s), {product_open} produit prête(s), {product_paused} produit en pause.")

    urgent = [a for a in alerts if a["kind"] != NOTHING]
    if urgent:
        lines.append(urgent[0]["message"].split("\n", 1)[1])
    elif alerts:
        lines.append(alerts[0]["message"].split("\n", 1)[1])
    else:
        lines.append("À FAIRE : rien. Suis l'avancée sur le cockpit ; je te préviens si quelque chose change.")
    return {
        "key": "digest",
        "title": "Usine : point du jour",
        "message": "\n".join(lines),
        "priority": "low",
        "kind": NOTHING,
    }


def digest_due(state: dict[str, float], now: float, hours: tuple[int, ...] = (8, 20),
               localtime=time.localtime) -> str | None:
    """Return the digest slot key if this tick is the first one in a slot hour."""
    lt = localtime(now)
    if lt.tm_hour not in hours:
        return None
    slot = f"digest:{lt.tm_year:04d}-{lt.tm_mon:02d}-{lt.tm_mday:02d}:{lt.tm_hour:02d}"
    return None if slot in state else slot


def diff_alerts(
    alerts: list[dict[str, str]],
    state: dict[str, float],
    now: float,
    remind_seconds: int = 3600,
) -> tuple[list[dict[str, str]], list[str]]:
    """Split alerts into (due, resolved_keys) against previously-sent state.

    `state` maps alert key -> epoch seconds of the last notification for that
    key (entries starting with `first:` and `digest:` are bookkeeping, not
    alerts). An alert is due the first time its key appears, or again once
    `remind_seconds` has passed while it is still active -- a stuck situation
    keeps paging instead of going silent. `resolved_keys` are alert keys that
    no longer appear, for a one-time "back to normal" notice.
    """
    active_keys = {a["key"] for a in alerts}
    due = [
        a for a in alerts
        if a["key"] not in state or now - state[a["key"]] >= remind_seconds
    ]
    resolved = [
        key for key in state
        if key not in active_keys and not key.startswith(("first:", "digest:"))
    ]
    return due, resolved
