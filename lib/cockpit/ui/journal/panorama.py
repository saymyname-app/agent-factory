"""The destination Journal of Panorama: what changed, day by day -- the
requests answered or cleared (the journal the cockpit already reads from
the traces on the beads) and the deliveries merged or stopped (the runs).

It follows the Journal reference (prototypes/c01-complete/frozen-panorama-
journal at 632deea): a timeline grouped by day, filters by kind, a detail
and its source under each entry. The technical logs of the reference have
no source yet and are left out.

Intent (Benjamin, his words, 2026-10-19 19:42 Paris): « enchaîne sur la
page suivante. »
Mechanism (agent interpretation): Journal, next in the navigation after
Projets; built directly, outside the paused convoy af-pqfxmd.
"""
import html
from datetime import datetime, timedelta, timezone

from cockpit.core.readmodel import PARIS
from cockpit.ui.journal.render import _render_entry

FILTERS = (("utiles", "Utiles"), ("decisions", "Décisions"), ("propositions", "Propositions"),
           ("livraisons", "Livraisons"), ("evenements", "Événements"), ("effacees", "Effacées"), ("tout", "Tout"))
# What each way a request was closed is, in the journal.
VOIES = {"escalation-door": ("decisions", "Décision"), "cockpit": ("decisions", "Décision"),
         "proposal-door": ("propositions", "Proposition"), "clear": ("effacees", "Effacée")}
LIMIT = 200


def _e(value):
    return html.escape(str(value), quote=True)


def _epoch(iso):
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).timestamp()


def journal_items(entries, runs):
    """Every entry of the journal, newest first: ``at``, ``kind`` (a filter
    key), ``label``, ``title``, ``text``, ``href``, ``source``."""
    run_ids = {run["id"]: run for run in runs or []}
    items = []
    for entry in entries or []:
        # A JournalEntry (cockpit.requests.journal): drawn as the journal
        # always drew it -- what, when, by whom, which way, its details.
        kind, label = VOIES.get(entry.voie, ("evenements", "Événement"))
        run = run_ids.get(entry.bead_id)
        items.append({"at": _epoch(entry.quand) if entry.quand else None, "kind": kind, "label": label,
                      "html": _render_entry(entry),
                      "href": run["href"] if run else None, "link": "Voir le run" if run else None})
    for run in runs or []:
        for event in run["events"]:
            text = event["text"]
            if text.startswith("Fusionné"):
                title, tone = "%s fusionné" % run["ticket"], "Livraison"
            elif text.startswith("Arrêt"):
                title, tone = "%s arrêté" % run["ticket"], "Livraison"
            elif text == "Ticket lancé":
                title, tone = "%s lancé" % run["ticket"], "Livraison"
            else:
                continue
            items.append({"at": event["at"], "kind": "livraisons", "label": tone, "title": "%s · %s" % (title, run["title"]),
                          "text": text, "href": run["href"], "link": "Voir le run",
                          "source": "run %s · %s" % (run["id"], run.get("branch") or "")})
    # Undated traces last, in the order they were read.
    return sorted(items, key=lambda item: -(item["at"] or 0))


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


def _selected(items, filtre):
    if filtre == "tout":
        return items
    if filtre == "utiles":
        return [item for item in items if item["kind"] != "effacees"]
    return [item for item in items if item["kind"] == filtre]


def render_journal_panorama(items, filtre, now, checked=None, envois_html="", unknown_html=""):
    """Main part of /journal; ``unknown_html`` says the journal could not be
    read (its deliveries are still shown)."""
    filtre = filtre if filtre in dict(FILTERS) else "utiles"
    buttons = "".join('<a class="jn-filter%s" href="/journal?filtre=%s"%s>%s</a>'
                      % (" on" if key == filtre else "", key, ' aria-current="page"' if key == filtre else "", label)
                      for key, label in FILTERS)
    if True:
        shown = _selected(items, filtre)[:LIMIT]
        groups, current = [], None
        for item in shown:
            day = _day(item["at"], now)
            if day != current:
                if current is not None:
                    groups.append("</ol>")
                groups.append('<h2 class="jn-day">%s</h2><ol class="jn-line">' % _e(day))
                current = day
            link = '<a href="%s">%s</a>' % (_e(item["href"]), _e(item["link"])) if item.get("href") else ""
            if item.get("html"):
                groups.append('<li class="jn-item %s"><small>%s · %s</small>%s%s</li>' % (
                    item["kind"], "%s (Paris)" % datetime.fromtimestamp(item["at"], tz=PARIS).strftime("%H:%M")
                    if item["at"] else "date inconnue", _e(item["label"]), item["html"], link))
                continue
            groups.append(
                '<li class="jn-item %s"><small>%s (Paris) · %s</small><strong>%s</strong><p>%s</p>%s'
                '<details><summary>Détail et source</summary><p class="jn-src">%s</p></details></li>'
                % (item["kind"], datetime.fromtimestamp(item["at"], tz=PARIS).strftime("%H:%M"), _e(item["label"]),
                   _e(item["title"]), _e(item["text"]), link, _e(item["source"])))
        if current is not None:
            groups.append("</ol>")
        body = "".join(groups) or '<section class="pn-panel"><p>Rien dans ce filtre.</p></section>'
    when = " · vérifié à %s (Paris)" % _e(checked) if checked else ""
    envois = ('<details class="pn-panel jn-envois"><summary>Envois de notifications</summary>%s</details>' % envois_html
              if envois_html else "")
    return ('<div class="pn-head"><h1>Journal</h1><p class="jn-sub">Les changements qui comptent, leurs conséquences '
            'et la suite%s.</p></div><nav class="jn-filters" aria-label="Filtrer le journal">%s</nav>%s%s'
            % (when, buttons, unknown_html + body, envois))


CSS = """
.jn-sub{margin:0 0 18px;color:var(--pn-muted-text)}
.jn-filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}
.jn-filter{padding:8px 13px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);text-decoration:none;font-size:13px}
.jn-filter.on{background:var(--pn-surface-2);border-color:var(--accent)}
.jn-day{font-size:18px;margin:22px 0 12px}
.jn-line{list-style:none;margin:0;padding:0 0 0 22px;border-left:1px solid var(--line)}
.jn-item{position:relative;padding:0 0 22px}
.jn-item::before{content:"";position:absolute;left:-27px;top:4px;width:9px;height:9px;border-radius:100%;background:var(--accent)}
.jn-item.livraisons::before{background:var(--ok)}.jn-item.effacees::before{background:var(--line)}
.jn-item.propositions::before{background:var(--warn)}
.jn-item small{display:block;font-size:12px;color:var(--pn-muted-text);margin-bottom:6px}
.jn-item strong{display:block;font-size:15px;margin-bottom:5px;overflow-wrap:anywhere}
.jn-item p{margin:0 0 6px;font-size:14px;line-height:1.5;color:var(--pn-muted-text);overflow-wrap:anywhere}
.jn-item a{color:var(--accent);font-size:14px}
.jn-item details{margin-top:6px;font-size:13px}.jn-item summary{cursor:pointer;color:var(--pn-muted-text)}
.jn-src{font:12px ui-monospace,monospace!important;margin-top:6px!important}
.jn-envois summary{cursor:pointer;font-weight:600}
.jn-item .cockpit-journal-entry{padding:0;border:0;display:grid;gap:4px}
.jn-item .cockpit-journal-demande{font-size:15px}
"""
