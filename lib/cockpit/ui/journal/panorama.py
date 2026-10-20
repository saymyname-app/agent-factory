"""The destination Journal of Panorama (F, af-njwz8v: the Prototype Fold of
the Journal reference, prototypes/c01-complete/frozen-panorama-journal at
632deea; Spec af-fgcw0d, user stories 76, 157, 158 and 175).

    view = journal_view(snapshot_row, entries, runs, projects, gc_row, connected)
    render_journal_panorama(view, query, now, anchors, envois_html="")

Three tabs, each an address of its own (``/journal?vue=…``), opened by a
button that sends a form, with no script:

- « Événements utiles » (``vue=utiles``, the default): the bugs, proposals,
  changes, decisions and events that concern the operator, day by day, each
  with its time, its source and its category, its title, its consequence,
  a link that leads where it says and, folded, its detail and its source.
  The categories (``categorie=``) keep their own. They are the requests
  answered or cleared (the traces on the beads), the deliveries merged,
  stopped or launched (the runs) and the events held for the journal. An
  event of a nature the cockpit has no label for keeps its place, said
  « Signal non reconnu venant de … », with its producer's words folded,
  unchanged (user story 76).
- « Logs techniques » (``vue=logs``): the events of the technical sources
  (CI, agents, delivery, connections, maintenance, notifications, and the
  others), each with what it means and its raw event folded, as received
  less its secrets; filtered by source (``source=``) and searched
  (``q=``, in the title, the meaning, the source and the raw event).
- « Sources disponibles » (``vue=sources``): each source of the logs, said
  « raccordée » when the factory declares it connected or the cockpit read
  logs of it -- a connected source that sent nothing yet stays connected --,
  « absente » otherwise, « inconnue » while the journal cannot be read.

Every label is fixed by the type of the event; no model reads or writes
any of it. A journal not read yet says so, one that cannot be read says
the view is unavailable -- never an empty journal --, and one read while
the supervisor no longer answers keeps what it shows under a notice. The
parts carry the anchors of the reference (``data-anchor``), numbered after
the shell's.
"""
import html
from datetime import datetime, timedelta, timezone

from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.core.readmodel import PARIS
from cockpit.ui.journal.render import _render_entry
from cockpit.ui.panorama.shell import open_button

LOADING, ERROR, EMPTY, CONTENT = "loading", "error", "empty", "content"

TABS = (("utiles", "Événements utiles"), ("logs", "Logs techniques"), ("sources", "Sources disponibles"))
# The categories of the useful events: key, label of the filter, label of
# an event of that category.
CATEGORIES = (("tout", "Tout", None), ("bugs", "Bugs", "Bug"), ("propositions", "Propositions", "Proposition"),
              ("changements", "Changements", "Changement"), ("decisions", "Décisions", "Décision"),
              ("evenements", "Événements", "Événement"))
# The nature an event is held for the journal with, its category.
NATURES = {"bug": "bugs", "proposition": "propositions", "changement": "changements", "décision": "decisions",
           "decision": "decisions", "événement": "evenements", "evenement": "evenements"}
# The sources of the technical logs: key, label; the source each one's
# events are held with; « autres », what no source claims.
SOURCES = (("ci", "CI"), ("agents", "Agents"), ("livraison", "Livraison"), ("connexions", "Connexions"),
           ("maintenance", "Maintenance"), ("notifications", "Notifications"))
LOG_FILTERS = (("tous", "Tous"),) + SOURCES + (("autres", "Autres"),)
TECHNICAL = {"ci": "ci", "agents": "agents", "delivery": "livraison", "livraison": "livraison",
             "connections": "connexions", "connexions": "connexions", "maintenance": "maintenance",
             "notifications": "notifications", "notification": "notifications"}
# How each way a request was closed is, in the journal: its category, its label.
VOIES = {"escalation-door": ("decisions", "Décision"), "cockpit": ("decisions", "Décision"),
         "proposal-door": ("propositions", "Proposition"), "clear": ("evenements", "Effacée")}
# The filters of the journal before the tabs (``?filtre=``): the category
# each one is now.
FORMER_FILTERS = {"utiles": "tout", "tout": "tout", "decisions": "decisions", "propositions": "propositions",
                  "livraisons": "changements", "evenements": "evenements", "effacees": "evenements"}
# Where the link an event offers leads, by its label; « Voir le projet »,
# to the page of its project.
LINKS = {"Voir les propositions": "/", "Voir le résultat": "/", "Voir les connexions": "/usine"}
PROJECT_LINK = "Voir le projet"
UNKNOWN_TITLE = "Signal non reconnu venant de %s"
UNKNOWN_SOURCE_TITLE = "Signal non reconnu venant d’une source inconnue"
UNKNOWN_TEXT = "Ce signal ne correspond à aucun type connu du cockpit. Son texte d’origine est dans le détail."
UNKNOWN_LOG = "Événement non reconnu"
UNKNOWN_LOG_TEXT = "Le type reçu ne possède pas encore de libellé. Le contenu brut reste accessible."
LEAD = "Les changements qui comptent, leurs conséquences et la suite."
FIXED_LABELS = "Libellés fixes par type d’événement ; aucun appel de modèle."
STALE_NOTICE = "État actuel inconnu · dernières données conservées. Actions indisponibles."
LIMIT = 200


def _e(value):
    return html.escape(str(value), quote=True)


def _epoch(iso):
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).timestamp()


def _hhmm(at):
    return "%s (Paris)" % datetime.fromtimestamp(at, tz=PARIS).strftime("%H:%M") if at else "Heure inconnue"


# --- what the journal holds ------------------------------------------------------

def journal_items(entries, runs, projects=None):
    """Every item of the journal, newest first (the undated last, in the
    order read): the useful ones (``log`` False) and the technical logs
    (``log`` True). ``projects``: key -> name of the declared projects."""
    projects = projects or {}
    run_ids = {run["id"]: run for run in runs or []}
    items = []
    for entry in entries or []:
        at = _epoch(entry.quand) if entry.quand else None
        if entry.voie in VOIES:
            # The resolution of a request: drawn as the journal always drew
            # it -- what, when, by whom, which way, its details.
            category, label = VOIES[entry.voie]
            run = run_ids.get(entry.bead_id)
            items.append({"at": at, "log": False, "category": category, "label": label, "html": _render_entry(entry),
                          "bead_id": entry.bead_id, "title": entry.demande or entry.quoi, "text": entry.quoi,
                          "link": ("Voir le run", run["href"]) if run else None})
            continue
        items.extend(_event_items(entry, at, projects))
    for run in runs or []:
        for event in run["events"]:
            text = event["text"]
            if text.startswith("Fusionné"):
                title = "%s fusionné" % run["ticket"]
            elif text.startswith("Arrêt"):
                title = "%s arrêté" % run["ticket"]
            elif text == "Ticket lancé":
                title = "%s lancé" % run["ticket"]
            else:
                continue
            items.append({"at": event["at"], "log": False, "category": "changements", "label": "Changement",
                          "title": "%s · %s" % (title, run["title"]), "text": text, "project": None,
                          "link": ("Voir le run", run["href"]), "bead_id": run["id"],
                          "folded": ["Livraison du run %s · %s" % (run["id"], run.get("branch") or "")]})
    return sorted(items, key=lambda item: -(item["at"] or 0))


def _event_items(entry, at, projects):
    """An event held for the journal: a useful event of its category, a log
    of its source, or -- of a nature the cockpit has no label for -- both,
    said by the fallback, its producer's words folded."""
    nature = entry.voie.strip()
    project = projects.get(entry.projet) or entry.projet or None
    href = LINKS.get(entry.lien) or ("/projet/%s" % entry.projet if entry.lien == PROJECT_LINK and entry.projet
                                     else None)
    link = (entry.lien, href) if href else None
    base = {"at": at, "bead_id": entry.bead_id, "project": project, "link": link}
    category = NATURES.get(nature.lower())
    if category:
        label = next(label for key, _, label in CATEGORIES if key == category)
        return [{**base, "log": False, "category": category, "label": label, "title": entry.quoi,
                 "text": " ".join(entry.texte), "folded": entry.plie}]
    source = TECHNICAL.get(nature.lower())
    if source:
        return [{**base, "log": True, "source": source, "title": entry.quoi, "text": " ".join(entry.texte),
                 "raw": entry.plie, "nature": nature}]
    # Unknown: the fallback, and what was received, unchanged, folded.
    received = ["Nature reçue : %s" % nature, "Titre reçu : %s" % entry.quoi] + list(entry.texte) + list(entry.plie)
    return [
        {**base, "log": False, "category": None, "label": None, "unknown": True,
         "title": UNKNOWN_TITLE % project if project else UNKNOWN_SOURCE_TITLE, "text": UNKNOWN_TEXT,
         "folded": received},
        {**base, "log": True, "source": "autres", "title": UNKNOWN_LOG, "text": UNKNOWN_LOG_TEXT,
         "raw": [" ".join(["%s · %s" % (nature, entry.quoi)] + list(entry.texte))] + list(entry.plie),
         "nature": nature},
    ]


def journal_view(row, entries, runs, projects, gc_row, connected=()):
    """What the destination shows: ``state`` (LOADING while the journal was
    never read, ERROR when its read failed, EMPTY, CONTENT), ``stale``
    (what it shows is no longer current: the journal or the supervisor no
    longer answers), ``checked`` (when it was read), ``items`` and
    ``connected`` (the keys of the sources declared connected, from their
    producers' names in ``connected``)."""
    if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
        state = ERROR if row is not None and row.get("failed_at") is not None else LOADING
        return {"state": state, "stale": False, "checked": None, "items": [], "connected": set()}
    items = journal_items(entries, runs, projects)
    stale = row["freshness"] != FRESH or (gc_row or {}).get("freshness", UNKNOWN) != FRESH
    return {"state": CONTENT if items else EMPTY, "stale": stale, "checked": row["read_at"], "items": items,
            "connected": {TECHNICAL.get(str(name).lower(), str(name).lower()) for name in connected}}


# --- the page ----------------------------------------------------------------------

def _choices(anchors, options, chosen, params, field, primary=True):
    """One button per option, each sending ``params`` with ``field`` set to
    its key -- the one ``chosen`` said open (aria-current), drawn as the
    reference's « primary » when ``primary``."""
    out = []
    for key, label in options:
        hidden = "".join('<input type="hidden" name="%s" value="%s">' % (_e(name), _e(value))
                         for name, value in {**params, field: key}.items() if value)
        if key == chosen:
            out.append('<form class="pn-open" method="get" action="/journal">%s<button type="submit" '
                       'class="jn-choice%s" aria-current="true" %s>%s</button></form>'
                       % (hidden, " jn-on" if primary else " jn-on-quiet",
                          anchors("primary" if primary else "button"), _e(label)))
        else:
            out.append('<form class="pn-open" method="get" action="/journal">%s<button type="submit" '
                       'class="jn-choice" %s>%s</button></form>' % (hidden, anchors("button"), _e(label)))
    return "".join(out)


def _query(query):
    """The tab, the category, the source and the words asked for."""
    vue = query.get("vue") if query.get("vue") in dict(TABS) else "utiles"
    categorie = query.get("categorie") or FORMER_FILTERS.get(query.get("filtre") or "", "tout")
    categorie = categorie if categorie in {key for key, _, _ in CATEGORIES} else "tout"
    source = query.get("source") if query.get("source") in dict(LOG_FILTERS) else "tous"
    return vue, categorie, source, (query.get("q") or "").strip()


def render_journal_panorama(view, query, now, anchors, envois_html=""):
    """The ``main`` of /journal for ``view`` and the ``query`` of its
    address (``vue``, ``categorie``, ``source``, ``q``), numbered by
    ``anchors``; ``envois_html``, the notifications sent, folded under the
    useful events."""
    vue, categorie, source, words = _query(query)
    parts = []
    if view["stale"]:
        parts.append('<div class="jn-notice" role="status" %s>%s</div>' % (anchors("notice"), _e(STALE_NOTICE)))
    parts.append('<h1 %s>Journal</h1>' % anchors("h1"))
    if vue != "logs":
        when = ""
        if view["checked"]:
            when = ' <span class="jn-checked">%s à %s.</span>' % (
                "Dernière lecture" if view["stale"] else "Lu", _hhmm(view["checked"]))
        parts.append('<p class="jn-lead" %s>%s%s</p>' % (anchors("page-lead"), _e(LEAD), when))
    parts.append('<div class="jn-row" role="group" aria-label="Onglets du journal" %s>%s</div>'
                 % (anchors("filter-row"), _choices(anchors, TABS, vue, {}, "vue", primary=vue != "logs")))
    if vue == "logs":
        parts.append(_render_logs(view, anchors, source, words))
    elif vue == "sources":
        parts.append(_render_sources(view, anchors))
    else:
        parts.append('<div class="jn-row" role="group" aria-label="Catégories" %s>%s</div>' % (
            anchors("filter-row"),
            _choices(anchors, [(key, label) for key, label, _ in CATEGORIES], categorie, {}, "categorie")))
        parts.append(_render_useful(view, anchors, categorie, now))
        if envois_html:
            parts.append('<details class="pn-panel jn-envois"><summary>Envois de notifications</summary>%s</details>'
                         % envois_html)
    return "".join(parts)


def _render_unread(view, anchors):
    """The journal not read yet, or that cannot be read; None when read."""
    if view["state"] == LOADING:
        return ('<section class="pn-panel" role="status" %s><h2 %s>Lecture en cours…</h2>%s</section>'
                % (anchors("panel"), anchors("h2"),
                   "".join('<div class="jn-skeleton" %s></div>' % anchors("skeleton") for _ in range(3))))
    if view["state"] == ERROR:
        return ('<section class="jn-error" role="alert" %s><h2 %s>Cette vue est indisponible</h2>'
                "<p %s>L’état réel est inconnu. Le journal n’a pas pu être lu.</p>"
                '<form method="post" action="/api/health/recheck"><button type="submit" class="jn-choice" %s>'
                "Réessayer</button></form></section>" % (anchors("error"), anchors("h2"), anchors("p"), anchors("button")))
    return None


def _empty(anchors, extra=""):
    return ('<section class="pn-panel jn-empty" %s><h2 %s>Rien à afficher ici</h2><p %s>Aucun élément dans cette vue.</p>'
            "%s</section>" % (anchors("panel"), anchors("h2"), anchors("p"), extra))


def _day(at, now):
    if at is None:
        return "Date inconnue"
    day = datetime.fromtimestamp(at, tz=PARIS).date()
    today = datetime.fromtimestamp(now, tz=PARIS).date()
    if day == today:
        return "Aujourd’hui"
    if day == today - timedelta(days=1):
        return "Hier"
    return day.strftime("%d/%m/%Y")


def _render_useful(view, anchors, categorie, now):
    unread = _render_unread(view, anchors)
    if unread:
        return unread
    shown = [item for item in view["items"] if not item["log"]
             and (categorie == "tout" or item["category"] == categorie)][:LIMIT]
    if not shown:
        return _empty(anchors)
    out, current = [], None
    for item in shown:
        day = _day(item["at"], now)
        if day != current:
            if current is not None:
                out.append("</div>")
            out.append('<h2 class="jn-day" %s>%s</h2><div class="jn-line" %s>'
                       % (anchors("timeline-date"), _e(day), anchors("timeline")))
            current = day
        out.append(_render_event(item, anchors))
    out.append("</div>")
    return "".join(out)


def _render_event(item, anchors):
    """One useful event: its line of time, source and category, its title,
    its consequence, its link, and folded, its detail and its source."""
    line = " · ".join(filter(None, (_hhmm(item["at"]), item.get("project"), item.get("label"))))
    article = anchors("timeline-item")
    small = anchors("small")
    head = '<small %s>%s</small>' % (small, _e(line))
    if item.get("html"):
        # A request answered: its own block, as the journal drew it.
        return '<article class="jn-item %s" data-bead-id="%s" %s>%s%s</article>' % (
            item["category"], _e(item["bead_id"]), article, head, item["html"])
    title = '<h3 %s>%s</h3>' % (anchors("h3"), _e(item["title"]))
    text = '<p %s>%s</p>' % (anchors("p"), _e(item["text"])) if item.get("text") else ""
    link = open_button(item["link"][1], item["link"][0], anchors("link"), "jn-link") if item.get("link") else ""
    folded = list(item.get("folded") or [])
    source = folded.pop() if len(folded) > 1 else None
    details = '<details %s><summary %s>Détail et source</summary>%s%s<small class="jn-id">%s</small></details>' % (
        anchors("details"), anchors("summary"),
        "".join('<p %s>%s</p>' % (anchors("p"), _e(line)) for line in folded),
        '<small %s>%s</small>' % (anchors("small"), _e(source)) if source else "",
        _e("Identifiant : %s" % item["bead_id"]))
    return '<article class="jn-item %s" data-bead-id="%s" %s>%s%s%s%s%s</article>' % (
        item.get("category") or "inconnu", _e(item["bead_id"]), article, head, title, text, link, details)


def _matches(item, words):
    if not words:
        return True
    haystack = " ".join([item["title"], item["text"], dict(LOG_FILTERS)[item["source"]], item.get("nature") or ""]
                        + list(item.get("raw") or []))
    return words.casefold() in haystack.casefold()


def _render_logs(view, anchors, source, words):
    parts = ['<div class="jn-row" role="group" aria-label="Sources des logs" %s>%s</div>' % (
        anchors("filter-row"), _choices(anchors, LOG_FILTERS, source, {"vue": "logs", "q": words}, "source"))]
    parts.append(
        '<form class="jn-search" method="get" action="/journal" role="search">'
        '<input type="hidden" name="vue" value="logs">%s'
        '<input class="jn-search-field" type="search" name="q" value="%s" aria-label="Rechercher dans les logs" '
        'placeholder="Rechercher un événement" %s><button type="submit" class="jn-choice">Rechercher</button></form>'
        % ('<input type="hidden" name="source" value="%s">' % _e(source) if source != "tous" else "", _e(words),
           anchors("log-search")))
    unread = _render_unread(view, anchors)
    if unread:
        parts.append(unread)
        return "".join(parts)
    logs = [item for item in view["items"] if item["log"] and (source == "tous" or item["source"] == source)
            and _matches(item, words)][:LIMIT]
    if not logs:
        clear = ""
        if words:
            clear = ('<p>Aucun log ne contient « %s ».</p><form class="pn-open" method="get" action="/journal">'
                     '<input type="hidden" name="vue" value="logs"><button type="submit" class="jn-link">'
                     "Effacer la recherche</button></form>" % _e(words))
        parts.append(_empty(anchors, clear))
    for item in logs:
        parts.append(
            '<section class="pn-panel jn-log" data-bead-id="%s" %s><small %s>%s</small><h3 %s>%s</h3><p %s>%s</p>'
            '<details %s><summary %s>Événement brut</summary><pre class="jn-raw" %s>%s</pre></details></section>'
            % (_e(item["bead_id"]), anchors("panel"), anchors("small"),
               _e("%s · %s" % (_hhmm(item["at"]), dict(LOG_FILTERS)[item["source"]])), anchors("h3"), _e(item["title"]),
               anchors("p"), _e(item["text"]), anchors("details"), anchors("summary"), anchors("raw-event"),
               _e("\n".join(item.get("raw") or ["Aucun contenu brut fourni par la source."]))))
    parts.append('<p class="jn-note" %s>%s</p>' % (anchors("readonly-note"), _e(FIXED_LABELS)))
    return "".join(parts)


def _render_sources(view, anchors):
    """Each source of the logs and what the cockpit knows of it."""
    counts = {}
    for item in view["items"]:
        if item["log"]:
            counts[item["source"]] = counts.get(item["source"], 0) + 1
    rows = []
    for key, label in SOURCES:
        if view["state"] == LOADING:
            state = "inconnue — lecture en cours"
        elif view["state"] == ERROR:
            state = "inconnue — la source ne répond pas"
        elif counts.get(key):
            state = "raccordée — %d log%s lu%s" % (counts[key], "s" if counts[key] > 1 else "",
                                                     "s" if counts[key] > 1 else "")
        elif key in view.get("connected", ()):
            state = "raccordée — aucun log reçu"
        else:
            state = "absente — aucun log reçu de cette source"
        rows.append('<li class="jn-source"><strong>%s</strong> · %s</li>' % (_e(label), _e(state)))
    others = counts.get("autres")
    note = ("<p>%d log%s d’une source que le cockpit ne reconnaît pas, sous « Autres ».</p>"
            % (others, "s" if others > 1 else "")) if others else ""
    return ('<section class="pn-panel" %s><h2 %s>Couverture des sources</h2>'
            "<p>Pour chaque source des logs techniques, ce que le cockpit en a lu.</p>"
            '<ul class="jn-sources">%s</ul>%s</section>' % (anchors("panel"), anchors("h2"), "".join(rows), note))


CSS = """
.jn-notice{padding:12px;border:1px solid var(--line);border-radius:6px;color:var(--pn-warn-text);margin-bottom:18px}
.pn-main h1{font-size:27px;margin:0 0 20px}
.pn-main .jn-lead{color:var(--pn-muted-text);margin:-10px 0 24px;line-height:1.6;overflow-wrap:anywhere}
.jn-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}
.jn-choice{font:inherit;font-size:13px;color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:8px 13px;cursor:pointer}
.jn-choice:hover{border-color:var(--accent)}
.jn-choice.jn-on{background:var(--accent);border-color:var(--accent);color:var(--pn-accent-ink)}
.jn-choice.jn-on-quiet{background:var(--pn-surface-2);border-color:var(--accent)}
.jn-day{font-size:19px;margin:30px 0 20px}
.jn-line{position:relative;margin-left:9px;border-left:1px solid var(--line);padding-left:28px}
.jn-item{position:relative;padding:0 0 25px;min-width:0}
.jn-item::before{content:"";position:absolute;left:-34px;top:5px;width:10px;height:10px;border:2px solid var(--bg);
  border-radius:50%;background:var(--accent)}
.jn-item.bugs::before{background:var(--warn)}.jn-item.changements::before{background:var(--ok)}
.jn-item.inconnu::before{background:var(--line)}
.jn-item small{display:block;font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.jn-item h3{margin:7px 0;font-size:17px;overflow-wrap:anywhere}
.pn-main .jn-item p{margin:7px 0;color:var(--pn-muted-text);font-size:14px;overflow-wrap:anywhere}
.jn-link{font:inherit;padding:0;border:0;color:var(--accent);background:none;cursor:pointer;text-decoration:underline;
  text-underline-offset:3px}
.jn-item details{padding:10px 0}
.jn-item summary,.jn-log summary{cursor:pointer;color:var(--pn-muted-text)}
.jn-id{margin-top:6px}
.jn-item .cockpit-journal-entry{padding:6px 0 0;border:0;display:grid;gap:4px}
.jn-item .cockpit-journal-demande{font-size:15px;overflow-wrap:anywhere}
.jn-item .cockpit-journal-quoi,.jn-item .cockpit-journal-meta{color:var(--pn-muted-text);overflow-wrap:anywhere}
.jn-search{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;max-width:500px}
.jn-search-field{font:inherit;flex:1 1 220px;min-width:0;max-width:100%;color:var(--ink);background:var(--bg);
  border:1px solid var(--pn-control-line);border-radius:6px;padding:10px}
.jn-search-field:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.jn-log small{display:block;font-size:12px;color:var(--pn-muted-text)}
.jn-log h3{font-size:16px;margin:8px 0;overflow-wrap:anywhere}
.jn-log details{border-top:1px solid var(--line);padding:16px 0 0;margin-top:12px}
.jn-raw{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace;background:var(--bg);color:var(--ink);
  padding:14px;border-radius:6px;margin:12px 0 0}
.pn-main .jn-note{font-size:12px;color:var(--pn-muted-text)}
.jn-error{border-left:3px solid var(--warn);padding:20px;background:var(--surface);margin-bottom:20px}
.jn-error h2{font-size:19px;margin:0 0 16px}
.jn-error p{margin:0 0 16px}
.jn-empty h2{font-size:19px;margin:0 0 12px}
.jn-empty p + p{margin-top:8px}
.jn-skeleton{height:16px;background:var(--line);border-radius:5px;margin:14px 0;width:65%}
.jn-skeleton:nth-child(3){width:85%}
.jn-sources{list-style:none;margin:16px 0 0;padding:0;display:grid;gap:10px}
.jn-source{overflow-wrap:anywhere}
.jn-envois summary{cursor:pointer;font-weight:600}
@media (max-width:800px){.pn-main h1{font-size:24px}.jn-line{padding-left:20px}.jn-item::before{left:-26px}}
"""
