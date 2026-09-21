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

import provider_failover as pf

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
    "provider_error": "Un fournisseur IA reste en erreur : vérifie la cause (cockpit > Fournisseurs IA) et répare si besoin.",
    "cold_start": "Des sessions n'arrivent pas à démarrer : regarde la cause et débloque.",
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


def providers_exhausted_until(provider_state: Any, provider_policy: Any, now: float) -> str | None:
    """Local HH:MM of the earliest quota return if every provider actually in
    use right now is exhausted, else None.

    af-d1jfc (2026-09-18): this used to loop over provider_state['pools'] and
    conclude "all exhausted" the moment every entry present there was
    exhausted. But 'pools' only ever gets an entry for a pool that has hit a
    RECORDED exhaustion event -- it is not a registry of every configured
    provider. With only openai recorded, the old code decided 100% of the
    (one) pool it knew about was down and told Benjamin's phone "tous les
    fournisseurs" while claude-standard was healthy and the Mayor was
    running. Compare against the providers actually resolved for each target
    right now (provider_state['effective'], target -> provider) mapped to
    their pool via provider_policy['providers'][provider]['pool'] instead: a
    provider with no exhaustion entry for its pool is healthy.
    """
    provider_state = provider_state or {}
    pools = provider_state.get("pools") or {}
    effective = provider_state.get("effective") or {}
    if not effective:
        return None
    provider_defs = (provider_policy or {}).get("providers") or {}
    in_use_pools = set()
    for provider in effective.values():
        pool_name = (provider_defs.get(provider) or {}).get("pool")
        if not pool_name:
            # Unknown provider (stale/missing policy): can't prove it's down.
            return None
        in_use_pools.add(pool_name)
    returns = []
    for pool_name in in_use_pools:
        pool = pools.get(pool_name)
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
    quota_until = providers_exhausted_until(snapshot.get("provider_state"), snapshot.get("provider_policy"), now)
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


# --------------------------------------------------------------------------
# Provider-problem alerts (af-tr2da, 2026-09-21)
# --------------------------------------------------------------------------
#
# Incident (2026-09-20): Claude login expired in WSL. provider-failover
# recorded pool anthropic = error/auth and fell to a broken fallback.
# Nothing started for ~5.5h and Benjamin was told nothing -- the only
# existing provider alert (providers_exhausted_until, above) fires only when
# EVERY provider in use is quota-exhausted, and a single pool in a *error*
# state (not quota) never trips it.
#
# Relevance rules (Benjamin, 2026-09-20):
#   R1 alert on IMPACT (a target with no usable provider, a target on a
#      fallback because of an error, or a pool in error that will not heal
#      alone) -- not on every error line.
#   R2 classify by who must act: category=auth never heals alone, alert
#      immediately; a quota wall with a known reset is normal life, silent;
#      network/server/unknown-duration errors are silent while young and
#      alert only once they persist.
#   R3 one alert per incident (pool + category + affected targets), not per
#      tick; re-alert on worsening (a fresh fingerprint) or a single 6h
#      reminder (max 2), never more often.
#   R4 every alert states what stopped in plain French (policy labels, never
#      raw provider/pool ids), since when, what is affected, whether it
#      self-heals, and the one action to take.
#   R5 an all-clear when it resolves.
#   R6 a symptom backstop independent of the log classifier: many sessions
#      failing to boot alerts even with no recognised error text.
#   R7 a hard cap on provider alerts per 24h; overflow collapses into one
#      "many provider problems" alert instead of paging once per incident.
#
# This module never re-decides failover: provider_failover.resolve() is the
# single source of truth for who is actually affected and why; this only
# reports what it already decided, reusing it rather than re-implementing
# chain resolution (and risking drifting from what bin/provider-failover
# itself acts on).

PERSIST_ALERT_SECONDS = 30 * 60   # network/server/config/unknown-reset quota: alert once this old
STRIKES_ALERT_THRESHOLD = 3       # ...or once this many strikes, whichever comes first
PROVIDER_REMIND_SECONDS = 6 * 60 * 60
PROVIDER_MAX_REMINDERS = 2
PROVIDER_ALERT_CAP = 6
PROVIDER_CAP_WINDOW_SECONDS = 24 * 60 * 60
COLD_START_THRESHOLD = 10
COLD_START_WINDOW_MINUTES = 15

# The one concrete action for a fixed credential, per pool. Falls back to a
# generic instruction for a pool this map does not know about, rather than
# staying silent on the fix (R4).
_REAUTH_HINT = {
    "anthropic": "Reconnecte Claude Code sur cet hôte : ouvre la session, lance `/login`.",
    "openai": "Reconnecte Codex sur cet hôte : `codex login`.",
    "openai-spark": "Reconnecte Codex sur cet hôte : `codex login`.",
}


def _since_text(age_seconds: float) -> str:
    minutes = max(1, int(age_seconds // 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, rem = divmod(minutes, 60)
    return f"{hours}h{rem:02d}" if rem else f"{hours}h"


def _resolvable_state(provider_state: Any) -> dict[str, Any]:
    """provider_failover.resolve() indexes state["pools"/"disabled"/...]
    directly (KeyError on a missing key) -- the real .gc/provider-state.json
    always has the full shape (normalize_state gives it one before it is
    ever saved), but defend here anyway rather than trust every caller."""
    state = dict(provider_state or {})
    state.setdefault("pools", {})
    state.setdefault("disabled", {})
    state.setdefault("forced", {})
    state.setdefault("chains", {})
    state.setdefault("effective", {})
    state.setdefault("auto", True)
    return state


def _pool_targets(policy: dict[str, Any], state: dict[str, Any]) -> dict[str, set[str]]:
    """pool -> targets whose chain includes a provider on that pool."""
    out: dict[str, set[str]] = {}
    providers = policy.get("providers") or {}
    for target in policy.get("targets") or {}:
        for provider in pf.chain_for(state, policy, target):
            pool = (providers.get(provider) or {}).get("pool")
            if pool:
                out.setdefault(pool, set()).add(target)
    return out


def _troubled_pools(provider_state: Any, provider_policy: Any, now: float) -> list[dict[str, Any]]:
    """Every pool genuinely in trouble right now, with its fingerprint key,
    independent of whether it is old/frequent enough to alert on yet.

    A pool is "trouble" only when provider_failover recorded it as `error`
    (a provider_error detection: auth/network/server/config) or as
    `exhausted` with no known reset -- an unknown-duration quota wall
    behaves the same way as an unresolved error: nobody knows when it
    clears. A known-reset quota wall is the failover's ordinary, absorbed
    case (R1 "normal life") and a manual mark/disable is a decision
    Benjamin already made himself -- neither counts as trouble here.
    """
    policy = provider_policy or {}
    if not policy.get("providers") or not policy.get("targets") or not policy.get("pools"):
        return []
    state = _resolvable_state(provider_state)
    pools = state["pools"]
    if not pools:
        return []
    resolution = pf.resolve(policy, state, now)
    pool_targets = _pool_targets(policy, state)
    out = []
    for pool_name, entry in pools.items():
        if pool_name not in policy["pools"] or entry.get("source") == "manual":
            continue
        status = entry.get("status")
        until = pf.epoch(entry.get("until"))
        if status not in ("error", "exhausted") or (until is not None and until <= now):
            continue
        if status == "exhausted" and entry.get("reset_known"):
            continue
        category = entry.get("category") if status == "error" else "quota"
        affected = sorted(
            target for target in pool_targets.get(pool_name, ())
            if (resolution.get(target, {}).get("provider") is None
                or (resolution[target]["reason"] == "fallback"
                    and resolution[target]["chain"][0]["pool"] == pool_name
                    and resolution[target]["chain"][0]["state"] in ("error", "exhausted")))
        )
        out.append({
            "key": f"provider:{pool_name}:{category}:{','.join(affected)}",
            "pool": pool_name, "category": category, "affected": affected,
            "strikes": int(entry.get("strikes") or 0),
        })
    return out


def provider_trouble_keys(provider_state: Any, provider_policy: Any, now: float) -> set[str]:
    """Fingerprint keys of every pool currently in trouble, alert-worthy or
    not. The caller stamps `first_seen[key]` the first tick each key
    appears here (mirroring how `compute_alerts`' own bookkeeping tracks
    age) so `provider_problem_alerts` can tell young from persistent, and
    drops a key once it stops appearing so a resolved incident's age does
    not linger and taint a later, unrelated one that happens to reuse the
    same pool/category/targets fingerprint.
    """
    return {t["key"] for t in _troubled_pools(provider_state, provider_policy, now)}


def provider_problem_alerts(provider_state: Any, provider_policy: Any, now: float,
                            first_seen: dict[str, float] | None = None) -> list[dict[str, str]]:
    """R1/R2/R4: one alert per pool in trouble long/serious enough to matter,
    phrased for the phone. `first_seen` must be kept by the caller across
    every key `provider_trouble_keys` returns, not just the ones that end up
    alert-worthy -- see that function's docstring."""
    first_seen = first_seen or {}
    policy = provider_policy or {}
    alerts: list[dict[str, str]] = []
    for trouble in _troubled_pools(provider_state, provider_policy, now):
        key, pool_name, category = trouble["key"], trouble["pool"], trouble["category"]
        age = now - first_seen.get(key, now)
        if category != "auth" and age < PERSIST_ALERT_SECONDS and trouble["strikes"] < STRIKES_ALERT_THRESHOLD:
            continue  # young and possibly self-healing (R1/R2) -- stay silent
        pool_label = policy["pools"].get(pool_name, {}).get("label", pool_name)
        target_labels = [policy["targets"].get(t, {}).get("label", t) for t in trouble["affected"]]
        touched = f" ({', '.join(target_labels)})" if target_labels else ""
        since = _since_text(age)
        if category == "auth":
            state_text = f"{pool_label} est en erreur d'authentification depuis {since}{touched}."
            alerts.append(_alert(key, f"Fournisseur en panne : {pool_label}", state_text, EASY,
                                 _REAUTH_HINT.get(pool_name, "Reconnecte le compte du fournisseur concerné."),
                                 "urgent"))
        elif category == "quota":
            state_text = f"{pool_label} est à court de quota depuis {since}, date de retour inconnue{touched}."
            alerts.append(_alert(key, f"Fournisseur en quota : {pool_label}", state_text, NOTHING,
                                 "Elle repart seule au retour du quota ; je te préviens si ça dure vraiment longtemps.",
                                 "default"))
        else:
            state_text = f"{pool_label} reste en erreur ({category}) depuis {since}{touched}."
            alerts.append(_alert(key, f"Fournisseur en erreur : {pool_label}", state_text, DELEGATE,
                                 PROMPTS["provider_error"], "default"))
    return alerts


def cold_start_alert(count: int | None, threshold: int = COLD_START_THRESHOLD,
                     window_minutes: int = COLD_START_WINDOW_MINUTES) -> dict[str, str] | None:
    """R6: a symptom backstop independent of `provider_failover.detect()`'s
    text classifier -- sessions repeatedly failing to boot alert even when
    no error text was recognised (the 2026-09-20 incident would have tripped
    this even if the auth regex had not matched)."""
    if count is None or count < threshold:
        return None
    return _alert("provider:cold_start_backstop", "Usine : démarrages en échec",
                  f"{count} session(s) n'ont pas réussi à démarrer en {window_minutes} min, sans cause reconnue.",
                  DELEGATE, PROMPTS["cold_start"], "urgent")


def diff_provider_alerts(
    alerts: list[dict[str, str]],
    sent: dict[str, dict[str, Any]],
    now: float,
    remind_seconds: int = PROVIDER_REMIND_SECONDS,
    max_reminders: int = PROVIDER_MAX_REMINDERS,
) -> tuple[list[dict[str, str]], list[str]]:
    """R3: one push per incident, then at most `max_reminders` more every
    `remind_seconds` while it stays active, then silence -- without ever
    going fully quiet forever the way a single stuck situation could under
    R3's "never more often" if reminders had no cap. `sent` maps alert key
    -> {"at": epoch of the last push, "reminders": reminders sent so far}
    (separate from the general `diff_alerts` state so the two throttles,
    1h-forever for ordinary alerts and 6h/max-2 here, never collide on the
    same keys). A fingerprint change (pool/category/affected-targets, baked
    into the key by `provider_problem_alerts`) is a new key, so a worsening
    incident is due immediately regardless of any cap on the old one.
    """
    active_keys = {a["key"] for a in alerts}
    due = []
    for alert in alerts:
        record = sent.get(alert["key"])
        if record is None:
            due.append(alert)
            continue
        if record.get("reminders", 0) >= max_reminders:
            continue
        if now - record.get("at", 0) >= remind_seconds:
            due.append(alert)
    resolved = [key for key in sent if key not in active_keys]
    return due, resolved


def apply_provider_budget(
    due: list[dict[str, str]],
    history: list[float],
    now: float,
    cap: int = PROVIDER_ALERT_CAP,
    window_seconds: int = PROVIDER_CAP_WINDOW_SECONDS,
) -> tuple[list[dict[str, str]], list[float], dict[str, str] | None]:
    """R7: cap provider pushes to `cap` per `window_seconds`; anything this
    tick would push past the cap collapses into one "many provider
    problems" alert instead of paging once per incident. Returns
    (alerts to actually push this tick, the trimmed history to keep,
    a collapse alert or None). The collapse alert is not itself counted
    against the cap -- it replaces the pushes it collapsed, it does not add
    to them -- and goes through the same `diff_provider_alerts` throttle as
    any other provider alert (key "provider:cap"), so it reminds at most
    twice every 6h rather than every tick while the flood continues.
    """
    recent = [t for t in history if now - t < window_seconds]
    room = max(0, cap - len(recent))
    allowed, overflow = due[:room], due[room:]
    cap_alert = None
    if overflow:
        cap_alert = _alert(
            "provider:cap", "Fournisseurs : nombreux problèmes",
            f"{len(overflow)} problème(s) fournisseur de plus que la limite de {cap} alertes / 24h.",
            NOTHING, "Regarde `./bin/provider-failover status` pour le détail complet.", "default",
        )
    return allowed, recent, cap_alert
