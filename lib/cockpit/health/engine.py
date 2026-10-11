"""Health zone engine (spec af-oohx2x .66-.69, T16 — "Zone santé de l'usine").

Pure functions turning already-collected signals into fixed French health
lines. Nothing here does I/O or reads a source directly — see
:mod:`cockpit.health.collectors` and :mod:`cockpit.health.git_source` for
turning gc/beads/git reads into the plain inputs these take. Each per-signal
function returns ``None`` (nothing to show) or a health line
``{"kind": "ok"|"warn"|"bad", "text": ...}``. Text is a fixed phrase per
GLOSSARY.md's Cockpit Lexicon: no bead id, no PR number, the Mayor is never
named (AGENTS.md: "l'usine essaie de corriger seule depuis ...").
"""
from datetime import datetime
from zoneinfo import ZoneInfo

OK = "ok"
WARN = "warn"
BAD = "bad"

PARIS = ZoneInfo("Europe/Paris")

# Spec .68: "usine à l'arrêt ?" after 60 min without progress while delivery
# work is ready; alert if gc is unreachable for more than 5 min.
SUPERVISOR_UNREACHABLE_AFTER_SECONDS = 5 * 60
FACTORY_STALLED_AFTER_SECONDS = 60 * 60

def _hhmm(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _duration_fr(seconds):
    total_minutes = int(max(0, seconds) // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return "%d h %02d" % (hours, minutes)
    return "%d min" % minutes


def version_behind(commits_behind):
    """Spec .66: the live root is behind its promotion branch."""
    if not commits_behind:
        return None
    plural = "s" if commits_behind != 1 else ""
    return {
        "kind": WARN,
        "text": "L'usine tourne une version en retard de %d commit%s." % (commits_behind, plural),
    }


def supervisor_unreachable(unreachable_since, now, after_seconds=SUPERVISOR_UNREACHABLE_AFTER_SECONDS):
    """Spec .68: alert once gc's last complete read is older than 5 min."""
    if unreachable_since is None:
        return None
    age = now - unreachable_since
    if age < after_seconds:
        return None
    return {
        "kind": BAD,
        "text": "Superviseur injoignable depuis %s (%s)." % (_hhmm(unreachable_since), _duration_fr(age)),
    }


def supervisor_partial(partial_errors):
    """Spec .14: gc answered, but reported part of its own state unreadable
    (``partial: true``). The values it did deliver are shown; this line
    says the read was not whole."""
    if not partial_errors:
        return None
    return {"kind": WARN, "text": "L'usine répond, mais une partie de son état est illisible."}


def factory_stalled(last_progress_at, now, delivery_ready, after_seconds=FACTORY_STALLED_AFTER_SECONDS):
    """Spec .68: "usine à l'arrêt ?" after 60 min without progress while
    delivery work is ready — the silence-only case is never a blocker for a
    chantier (Implementation Decisions, Étapes d'un chantier), but is
    exactly this health signal."""
    if not delivery_ready or last_progress_at is None:
        return None
    age = now - last_progress_at
    if age < after_seconds:
        return None
    return {
        "kind": WARN,
        "text": "Usine à l'arrêt ? Aucune progression depuis %s alors que du travail est prêt." % _duration_fr(age),
    }


def mayor_first_lines(since_list, now):
    """Spec Further Notes / T16: "l'usine essaie de corriger seule depuis
    1 h 40" for each Mayor-first escalation not yet promoted to Benjamin —
    the Mayor is never named on screen."""
    return [
        {"kind": WARN, "text": "L'usine essaie de corriger seule depuis %s." % _duration_fr(now - since)}
        for since in sorted(since_list or ())
    ]


def loop_lines(loops, now):
    out = []
    for item in loops or ():
        since = item.get("since")
        suffix = " depuis %s" % _duration_fr(now - since) if since is not None else ""
        out.append({"kind": WARN, "text": "Une session de l'usine boucle%s." % suffix})
    return out


def order_failure_lines(order_failures, now):
    out = []
    for item in order_failures or ():
        since = item.get("since")
        suffix = " depuis %s" % _duration_fr(now - since) if since is not None else ""
        out.append({"kind": BAD, "text": "Une tâche planifiée a échoué%s." % suffix})
    return out


def red_ci_lines(red_ci, now):
    out = []
    for item in red_ci or ():
        since = item.get("since")
        suffix = " depuis %s" % _duration_fr(now - since) if since is not None else ""
        out.append({"kind": BAD, "text": "Les tests automatiques (CI) sont rouges%s." % suffix})
    return out


def maintenance_proposal_lines(maintenance, now):
    """ADR-0029 point 2: a maintenance proposal « reste visible dans la
    zone santé ». One informative line (kind ``ok``: nothing is wrong,
    the factory is correcting a defect it found itself) for all of them,
    dated from the oldest -- never a bead id, never the Mayor's name."""
    items = list(maintenance or ())
    if not items:
        return []
    count = len(items)
    sinces = [item.get("since") for item in items if item.get("since") is not None]
    suffix = " depuis %s" % _duration_fr(now - min(sinces)) if sinces else ""
    plural = "s" if count > 1 else ""
    return [
        {
            "kind": OK,
            "text": "L'usine corrige seule %d défaut%s qu'elle a constaté%s%s." % (count, plural, plural, suffix),
        }
    ]


def proposal_sans_champs_lines(sans_champs):
    """ADR-0029 point 4: a proposal no door wrote is an anomaly here, not
    a request -- « à reformuler par la porte ou à fermer »."""
    count = len(list(sans_champs or ()))
    if not count:
        return []
    plural = "s" if count > 1 else ""
    return [
        {
            "kind": WARN,
            "text": "%d proposition%s sans champs lisibles : à reformuler par la porte des propositions, ou à fermer."
            % (count, plural),
        }
    ]


def compute_health(
    now,
    commits_behind=None,
    supervisor_unreachable_since=None,
    supervisor_partial_errors=(),
    last_progress_at=None,
    delivery_ready=False,
    mayor_first_since=(),
    loops=(),
    order_failures=(),
    red_ci=(),
    maintenance_proposals=(),
    proposals_sans_champs=(),
    extra_lines=(),
    supervisor_unreachable_after_seconds=SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
    factory_stalled_after_seconds=FACTORY_STALLED_AFTER_SECONDS,
):
    """Assemble every health line from already-collected signals.

    Returns ``{"ok": bool, "lines": [...]}``. ``ok`` is true only when
    nothing is wrong — never a bare true/false without this list, so the
    page never shows "tout va bien" without the lines that justify it. A
    line of kind ``ok`` (the factory correcting a defect it found itself,
    ADR-0029) is information, not a problem: it does not make ``ok`` false.
    """
    lines = []
    for line in (
        version_behind(commits_behind),
        supervisor_unreachable(supervisor_unreachable_since, now, supervisor_unreachable_after_seconds),
        supervisor_partial(supervisor_partial_errors),
        factory_stalled(last_progress_at, now, delivery_ready, factory_stalled_after_seconds),
    ):
        if line is not None:
            lines.append(line)
    lines.extend(mayor_first_lines(mayor_first_since, now))
    lines.extend(loop_lines(loops, now))
    lines.extend(order_failure_lines(order_failures, now))
    lines.extend(red_ci_lines(red_ci, now))
    lines.extend(proposal_sans_champs_lines(proposals_sans_champs))
    lines.extend(maintenance_proposal_lines(maintenance_proposals, now))
    # What the cockpit's own parts say about themselves (notifications,
    # heartbeat: spec .59, .98), already as health lines.
    lines.extend(extra_lines)
    return {"ok": not any(line.get("kind") != OK for line in lines), "lines": lines}
