"""The four indicators of the factory and its daily volumes, computed from
the sources the cockpit reads (D, af-ten1sp; Spec af-fgcw0d, user stories
148, 149 and 150).

    view = analyses(snapshot, requests, now)

One call gives everything the Analyses show, and what the overview reuses
(ticket K): over the seven days that end today (Paris),

- ``indicators``: « Décisions ouvertes », « Résultats fusionnés », « Délai de
  livraison » and « Vérifications CI réussies », each its value, or none and
  the reason it is unavailable, then its method -- population, period,
  sources, when they were read (Paris) and calculation;
- ``volumes``: the daily counts that compare -- results merged, pull
  requests merged, tickets delivered, CI runs that succeeded --, one value
  a day, or none and the reason;
- ``results``, ``portions`` and ``decisions``: what the views list.

A result is counted on the proof of its merge written by the flow
(``gc.flow.promotion``), a ticket on its merge into the integration branch
(``gc.flow.merge``, merged), a CI run on its conclusion as GitHub gives it;
the decisions are the requests the cockpit lists. A source not read gives
no value, never a zero, and a count is never a percentage.

Intent (Benjamin, his words, 2026-10-12): « Il faut présenter ce qu’on peut,
on a des métriques » ; « Bref faut pas que ca soit redondant ».
Mechanism (agent interpretation): the four indicators of the Spec, each
computed once here for every page that shows it.
"""
import json
from datetime import datetime, timedelta, timezone

from cockpit.core.freshness import UNKNOWN
from cockpit.core.readmodel import PARIS

DAYS = 7
DECISIONS, RESULTS, DELAY, CI = "decisions", "results", "delay", "ci"
LABELS = {DECISIONS: "Décisions ouvertes", RESULTS: "Résultats fusionnés", DELAY: "Délai de livraison",
          CI: "Vérifications CI réussies"}
# The portions of the delay the records of the flow date: from the
# publication of the graph to the delivery of the result, to Benjamin's
# acceptance, to the proof of the merge. Each: label, whether it is a wait.
PORTIONS = (("Réalisation et vérifications", False), ("Attente de jugement", True), ("Fusion", False))
# The daily volumes, in the order they are drawn.
VOLUMES = ("Résultats fusionnés", "PR fusionnées", "Tickets livrés", "Exécutions CI réussies")
NO_REPOSITORY = "aucun dépôt GitHub n’est déclaré pour la CI du cockpit (réglage github_repo)"


def analyses(snapshot, requests, now, days=DAYS):
    """What the Analyses show over the ``days`` days that end on the day of
    ``now`` (Paris), from the read model's ``snapshot`` and the ``requests``
    the cockpit lists. See the module."""
    span = _days(now, days)
    period = "%d jours, du %s au %s (Paris)" % (days, span[0].strftime("%d/%m"), span[-1].strftime("%d/%m"))
    within = lambda at: at is not None and span[0] <= _day(at) <= span[-1]
    names = _project_names(snapshot.get("projets"))
    flow_row, github_row, beads_row = snapshot.get("flow"), snapshot.get("github"), snapshot.get("beads")

    flow_reason = _unread(flow_row, "les tickets du flux sont en cours de lecture",
                          "les tickets du flux n’ont pas pu être lus")
    flow = [] if flow_reason else [bead for bead in flow_row["value"] if isinstance(bead, dict)]
    results = sorted((r for r in map(_result, flow) if r and within(r["merged"])), key=lambda r: -r["merged"])
    for result in results:
        result["project"] = names.get(result["project"], result["project"])
    tickets = [at for at in map(_ticket_merged, flow) if within(at)]

    github_reason = NO_REPOSITORY if github_row is None else _unread(github_row, "GitHub est en cours de lecture",
                                                                     "GitHub n’a pas répondu")
    github = {} if github_reason else github_row["value"] or {}
    runs = [run for run in github.get("workflow_runs") or []
            if isinstance(run, dict) and within(_ts(run.get("created_at")))]
    completed = [run for run in runs if run.get("status") == "completed"]
    succeeded = [run for run in completed if run.get("conclusion") == "success"]
    pulls = [at for at in (_ts(pull.get("merged_at")) for pull in github.get("pull_requests") or []
                           if isinstance(pull, dict)) if within(at)]

    def per_day(moments):
        counts = {day: 0 for day in span}
        for at in moments:
            counts[_day(at)] += 1
        return [counts[day] for day in span]

    portions = []
    for (label, wait), (begin, end) in zip(PORTIONS, (("published", "delivered"), ("delivered", "accepted"),
                                                       ("accepted", "merged"))):
        measured = [r[end] - r[begin] for r in results
                    if r[begin] is not None and r[end] is not None and r[end] >= r[begin]]
        portions.append({"label": label, "wait": wait, "median": _median(measured), "count": len(measured)})
    totals = [r["merged"] - r["published"] for r in results if r["published"] is not None]
    repository = github.get("repository") or ""

    beads_known = beads_row is not None and beads_row["value"] is not None and beads_row["freshness"] != UNKNOWN
    flow_sources = "les chantiers du flux de livraison, lus sur le tracker"
    indicators = {
        DECISIONS: _indicator(
            DECISIONS, str(len(requests)) if beads_known else None,
            _unread(beads_row, "les demandes sont en cours de lecture", "les demandes n’ont pas pu être lues"),
            population="les décisions qui t’attendent : propositions, questions et résultats à juger, "
                       "ouvertes maintenant",
            period="%s ; une décision ouverte est comptée tant qu’elle attend, même posée avant" % period,
            sources="les demandes du cockpit, lues sur le tracker", read=_read(beads_row),
            calculation="le nombre de demandes ouvertes, comme sur la Vue d’ensemble ; une demande répondue ne "
                        "compte plus"),
        RESULTS: _indicator(
            RESULTS, None if flow_reason else str(len(results)), flow_reason,
            population="les résultats de chantier dont la fusion est prouvée ; les PR et les tickets ne sont "
                       "pas des résultats",
            period=period, sources="la preuve de fusion (gc.flow.promotion) de %s" % flow_sources,
            read=_read(flow_row),
            calculation="le nombre de résultats fusionnés, un par preuve de fusion, compté le jour de la fusion "
                        "(Paris)"),
        DELAY: _indicator(
            DELAY, None if flow_reason or not totals else delay_text(_median(totals)),
            flow_reason or (None if totals else "aucun résultat fusionné sur la période"),
            population="les %d résultats fusionnés de la période" % len(results),
            period=period, sources="la publication du graphe, la livraison, l’acceptation et la preuve de fusion "
                                   "de %s" % flow_sources, read=_read(flow_row),
            calculation="la médiane des délais de la publication du graphe à la preuve de fusion ; chaque portion "
                        "est la médiane de ses propres délais, mesurée sur les résultats qui la datent : elles ne "
                        "s’additionnent pas"),
        CI: _indicator(
            CI, None if github_reason or not completed else "%d %%" % round(100 * len(succeeded) / len(completed)),
            github_reason or (None if completed else "aucune exécution CI terminée sur la période"),
            population="les exécutions CI terminées de la période ; une exécution en cours n’est pas comptée",
            period=period, sources="la CI GitHub%s, ses %d dernières exécutions" % (
                " du dépôt %s" % repository if repository else "", 100),
            read=_read(github_row),
            calculation="%d réussies sur %d terminées" % (len(succeeded), len(completed)) if not github_reason
            else "les exécutions réussies sur les exécutions terminées"),
    }
    volumes = [
        {"label": VOLUMES[0], "values": None if flow_reason else per_day(r["merged"] for r in results),
         "reason": flow_reason},
        {"label": VOLUMES[1], "values": None if github_reason else per_day(pulls), "reason": github_reason},
        {"label": VOLUMES[2], "values": None if flow_reason else per_day(tickets), "reason": flow_reason},
        {"label": VOLUMES[3], "values": None if github_reason else per_day(_ts(r.get("created_at")) for r in succeeded),
         "reason": github_reason},
    ]
    return {"days": span, "period": period, "indicators": indicators, "volumes": volumes, "results": results,
            "portions": portions, "decisions": list(requests) if beads_known else [], "now": now}


def _indicator(key, value, reason, **method):
    return {"key": key, "label": LABELS[key], "value": value, "reason": None if value is not None else reason,
            **method}


def _unread(row, reading, failing):
    """Why ``row`` gives no value -- ``reading`` while its first read has not
    ended, ``failing`` when it failed --, or None when it gives one."""
    if row is not None and row["value"] is not None:
        return None
    if row is not None and row.get("failed_at") is not None:
        return "%s (dernier essai le %s)" % (failing, _when(row["failed_at"]))
    return reading


def _read(row):
    if row is None or not row.get("read_at"):
        return "pas encore lues"
    return "lues le %s" % _when(row["read_at"])


def _when(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%d/%m à %H:%M (Paris)")


def _days(now, count):
    today = datetime.fromtimestamp(now, tz=PARIS).date()
    return [today - timedelta(days=count - 1 - i) for i in range(count)]


def _day(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).date()


def _ts(value):
    """An ISO instant as epoch seconds, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


def _record(metadata, key):
    value = (metadata or {}).get(key)
    if isinstance(value, str) and value[:1] in "{[":
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _result(bead):
    """A result whose merge the flow proved: title, project key, and the
    instants of its publication, delivery, acceptance and merge (None when
    the flow did not write it)."""
    metadata = bead.get("metadata") or {}
    promotion = _record(metadata, "gc.flow.promotion")
    merged = _ts((promotion or {}).get("at"))
    if merged is None:
        return None
    judgement = _record(metadata, "gc.flow.judgement") or {}
    accepted = [_ts(answer.get("at")) for answer in judgement.get("answers") or []
                if isinstance(answer, dict) and answer.get("response") == "accepted" and not answer.get("voided")]
    return {"title": bead.get("title") or "", "project": metadata.get("gc.project_id") or "",
            "published": _ts(bead.get("created_at")),
            "delivered": _ts((_record(metadata, "gc.flow.delivered") or {}).get("at")),
            "accepted": max(filter(None, accepted), default=None), "merged": merged}


def _ticket_merged(bead):
    """When a ticket was merged into the integration branch, or None."""
    merge = _record(bead.get("metadata"), "gc.flow.merge")
    return _ts(merge.get("at")) if merge and merge.get("outcome") == "merged" else None


def _project_names(row):
    value = (row or {}).get("value") or {}
    return {p.get("project_id"): p.get("display_name") or p.get("project_id")
            for p in value.get("projects") or [] if isinstance(p, dict)}


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def delay_text(seconds):
    """« 3 h 05 », « 45 min »: a delay to the minute, as the views write it."""
    minutes = int(round(seconds / 60))
    return "%d h %02d" % divmod(minutes, 60) if minutes >= 60 else "%d min" % minutes
