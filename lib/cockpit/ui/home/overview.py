"""The destination « Vue d’ensemble » of B/Panorama, with the panels of a
result (T02 Prototype Fold, af-0gonc9; Spec af-2zseit, user stories 111,
124, 147 and 175; Validated Prototype prototype/cockpit-b-zones-20261012 at
632deea, prototypes/c01-complete/frozen-panorama-home).

    view = overview_view(snapshot, requests)
    main_html = render_overview(view, anchors, details_html)

:func:`overview_view` reads, from the read model's snapshot and the
requests already assembled from it, which state the destination is in and
what it shows; :func:`render_overview` draws it, inside the shell of
:mod:`cockpit.ui.panorama.shell`. Neither reads a source.

The states:

- ``loading``: the tracker has not answered yet; ``error``: it was never
  read and its last read failed -- the page says the real state is unknown
  and offers to read again;
- ``empty``: nothing waits, no project, no result, no indicator;
- ``content``: four indicators, the activity, the last runs, what waits
  (« Ce qui t’attend ») beside the result open under it, the projects. A
  reading of the supervisor or the tracker that is no longer current keeps
  the last values under a notice that says so.

The result open is the result of a chantier, as the records of the D01 flow
give it (A1, af-c662qx; :mod:`cockpit.projects.outcome`, read with the
projects): the one to judge first, else the latest of the others; without
one, the first request. A result to judge shows what it is, its dossier --
the rubrics of its dossier page, each a part that unfolds, « Ce qui n'a PAS
été vérifié » as « Ce qui reste à vérifier » with the recette of the cockpit
for the Factory's own project, its reports (« Compte rendu … ») -- above its
bar; a result judged shows its follow-up: what was answered, the proof of
the merge or that there is none, the reason of an abandon. Essai and Avis
are not wired to a door here (A2): they are drawn unavailable under every
result, and the panel says why -- not wired yet on a result to judge, of no
use on a result already judged; nothing on the page shows a command done
that no door recorded.
No record a demonstration dataset writes (``gc.result_dossier``) is read.

Every part carries the anchor of the reference (``data-anchor``), numbered
by the :class:`~cockpit.ui.panorama.shell.Anchors` of the page as the frozen
pages number them: the generic ones too (``div-3``, ``strong-8``,
``circle-7``), in the order the reference draws them.
"""
import html
import json
from datetime import datetime

from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.core.readmodel import PARIS
from cockpit.projects import outcome as outcome_mod
from cockpit.projects.model import Chantier
from cockpit.projects.source import from_value as projects_from_value
from cockpit.requests.model import URGENT
from cockpit.text.validate import speaks_plainly
from cockpit.runs.derive import runs_from_beads
from cockpit.ui.runs.page import duration
from cockpit.ui.home.page import UNKNOWN_TEXT, UNKNOWN_TEXT_NO_TIME
from cockpit.ui.home.pour_moi import CSS as POUR_MOI_CSS, links_of, render_details, render_request
from cockpit.ui.panorama.shell import Anchors, anchor_slug, open_button
from cockpit.ui.projects.page import RESULT_PANEL_ID
from cockpit.ui.projects.project_page import project_page_url

LOADING, ERROR, EMPTY, CONTENT = "loading", "error", "empty", "content"
PROJECT_CARD = "gc.project_card"
RUN_CARD = "gc.run_card"
SAID = "said"

DECISIONS = "Décisions à prendre"
# The indicators the cockpit has no source for yet: what the tracker keeps
# as said of them (one bead under each title: its value, then its period),
# or « non collecté ».
SAID_INDICATORS = ("Résultats fusionnés", "Délai de livraison", "Vérifications CI réussies")
CHART_LABEL = ("Volumes quotidiens comparés sur sept jours : PR fusionnées, tickets livrés, "
               "exécutions CI réussies")
# Each series its colour (a token of the page, 3:1 at least on the surface
# in both themes) and its dashes, so that it is told apart without its
# colour: a plain, a dashed and a dotted line.
CHART_SERIES = (("PR fusionnées", "var(--pn-series-1)", ""), ("Tickets livrés", "var(--pn-series-2)", "8 5"),
                ("CI réussies", "var(--pn-series-3)", "1 5"))
ACTIVITY = "Activité sur 7 jours"
UNWIRED_RESULT = "Essai et Avis ne sont pas encore raccordés à cette vue : rien n’est lancé ni préparé d’ici."
JUDGED_RESULT = "Résultat déjà jugé : Essai et Avis ne servent qu’à un résultat à juger, rien n’est lancé ni préparé d’ici."
UNSURE_RESULT = ("État du résultat incertain : Essai et Avis restent indisponibles tant que ses enregistrements "
                 "ne sont ni lisibles ni cohérents.")
NOT_GIVEN = "Contenu non fourni par la source."
# The parts of a result to judge the cockpit draws whatever its dossier: the
# two that open the page of the dossier, the one that says what is left to
# verify, the one that gives its version and its sources.
OPENING = (("Ce qui a été livré", "Changements et version à essayer"),
           ("Vérifications et preuves", "Parcours, tests et relecture"))
TO_VERIFY = "Ce qui reste à vérifier"
VERSION = "Version et sources"
DOSSIER_UNREAD = "Dossier non lu : sa page est introuvable ou illisible."
FOLLOW_UP = "Suivi du résultat"
HISTORY = "Historique et preuves"
# The project whose results carry the recette of the cockpit (Spec
# af-fgcw0d, Testing Decisions 6): the Factory itself.
FACTORY_PROJECT = "Usine"
# The proofs of the recette, each said with what the cockpit holds of it.
RECETTE_STOP_DONE = "Arrêt et reprise : une reprise vérifiée est enregistrée après un essai réel."
RECETTE_STOP_MISSING = "Arrêt et reprise vérifiés : preuve manquante, aucun essai réel réussi n’est enregistré."
RECETTE_ALERT_MISSING = ("Alerte d’une usine muette : preuve manquante, aucune alerte d’essai n’est enregistrée "
                         "par le cockpit.")
RECETTE_DAYS_MISSING = ("Sept jours consécutifs d’usage réel : preuve manquante, le cockpit ne compte pas encore "
                        "les jours d’usage.")


def recette(stop_trial_passed):
    """The lines of the recette of the cockpit: each proof it needs, said
    present when the cockpit holds it, missing otherwise -- never said
    acquired without a record."""
    return [RECETTE_STOP_DONE if stop_trial_passed else RECETTE_STOP_MISSING, RECETTE_ALERT_MISSING,
            RECETTE_DAYS_MISSING]
LEGACY_SUMMARY = "Détails techniques et actions"


def overview_view(snapshot, requests, stop_trial_passed=False, now=None, undelivered=()):
    """What the destination shows: ``state`` (see the module), ``stale``,
    ``checked`` (HH:MM of the reading shown), ``requests`` (« Pour moi »,
    each opened with its gestures, :mod:`cockpit.ui.home.pour_moi`),
    ``indicators``, ``activity``, ``runs`` (the cards of the last runs),
    ``dossier`` (the result open), ``projects``. ``stop_trial_passed``:
    whether a real stop and restart reached a verified restart (the
    recette). ``requests`` are those the cockpit knows even while the
    tracker is not read: what it raises itself (« Usine muette »); the
    list then says it is not whole (``unknown``). ``undelivered``: the ids
    of the requests whose push could not be delivered yet."""
    beads_row = snapshot.get("beads")
    view = {"state": CONTENT, "stale": False, "checked": None, "requests": [], "indicators": [],
            "activity": {}, "runs": [], "dossier": None, "projects": [], "projects_unread": False, "now": now,
            "unknown": _unknown(beads_row)}
    urls = _project_urls(snapshot.get("projets"))
    view["requests"] = [
        {"id": r.id, "quoi": r.quoi, "projet": r.projet, "pourquoi": r.pourquoi, "request": r,
         # A title its producer wrote outside the contract of the text (too
         # long, on two lines) is said whole after the cockpit's label;
         # one that holds an identifier or an internal term only in the
         # folded details (spec .73, .75).
         "origine": _plain((r.texte_origine or {}).get("quoi")),
         "links": links_of(r, urls.get(r.projet) or urls.get((r.projet or "").lower())),
         "undelivered": r.id in undelivered}
        for r in requests
    ]
    if beads_row is None or beads_row["value"] is None:
        view["state"] = ERROR if (beads_row or {}).get("failed_at") is not None else LOADING
        return view
    beads = [bead for bead in beads_row["value"] if isinstance(bead, dict)]
    rows = [snapshot[name] for name in ("gc", "beads") if snapshot.get(name)]
    view["stale"] = any(row["freshness"] != FRESH for row in rows)
    read_ats = [row["read_at"] for row in rows if row["read_at"] is not None]
    view["checked"] = _hhmm(min(read_ats) if view["stale"] else max(read_ats))
    view["dossier"] = _result_open(snapshot.get("projets"), recette(stop_trial_passed))
    said = {bead.get("title"): _lines(bead) for bead in beads if SAID in (bead.get("labels") or [])}
    view["indicators"] = [(DECISIONS, str(len(requests)), "Maintenant · demandes ouvertes", "#pn-inbox")] + [
        (label, *(said[label] + ["", ""])[:2], "/analyses") if said.get(label)
        else (label, "—", "Non collecté", "/analyses")
        for label in SAID_INDICATORS
    ]
    view["activity"] = _activity(said.get(ACTIVITY) or [])
    view["runs"] = [card for card in (_record(bead, RUN_CARD) for bead in beads) if card]
    runs_row = snapshot.get("runs")
    if not view["runs"] and runs_row and runs_row["value"]:
        view["runs"] = runs_from_beads(runs_row["value"], max(r["read_at"] or 0 for r in rows + [runs_row]))[:3]
    view["projects"] = _projects(snapshot.get("projets"), beads, view["requests"])
    projets = snapshot.get("projets")
    view["projects_unread"] = projets is not None and projets["value"] is None
    if not (view["requests"] or view["dossier"] or view["projects"] or view["activity"] or view["runs"]
            or any(said.get(label) for label in SAID_INDICATORS)):
        view["state"] = EMPTY
    return view


def _unknown(beads_row):
    """What « Ce qui t’attend » says when the tracker is not known (spec
    .16): since when it is unreadable; ``None`` while it reads."""
    if beads_row is not None and beads_row["freshness"] != UNKNOWN:
        return None
    read_at = (beads_row or {}).get("read_at")
    since = _hhmm(read_at) if read_at is not None else None
    return UNKNOWN_TEXT % since if since else UNKNOWN_TEXT_NO_TIME


def _plain(text):
    return text if text and speaks_plainly(text) else None


def _project_urls(row):
    """The page of each declared project, by its name and by its key."""
    if row is None or row["value"] is None:
        return {}
    projects, _ = projects_from_value(row["value"])
    urls = {}
    for project in projects:
        urls[project.display_name] = urls[project.project_id] = project_page_url(project.project_id)
    return urls


def _activity(lines):
    """The daily volumes the tracker keeps as said under « Activité sur 7
    jours », one line a day and a series (« PR fusionnées · Lundi : 1 »):
    series -> its seven volumes, Monday first. A series without its seven
    days is left out: no line is drawn of a day no source gave."""
    days = [day for _, day in CHART_DAYS]
    said = {}
    for line in lines:
        series, _, rest = line.partition(" · ")
        day, _, volume = rest.partition(" : ")
        try:
            said.setdefault(series, {})[day] = float(volume.replace(",", "."))
        except ValueError:
            continue
    return {series: [volumes[day] for day in days] for series, volumes in said.items()
            if series in {label for label, _, _ in CHART_SERIES} and set(days) <= set(volumes)}


def _hhmm(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _lines(bead):
    return [line.strip() for line in (bead.get("description") or "").split("\n") if line.strip()]


def _record(bead, key):
    """The record ``key`` of ``bead``'s metadata, or None."""
    raw = (bead.get("metadata") or {}).get(key)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def _historique(value, project_id):
    """The chantiers of the historique of a project, the last one first."""
    rows = ((value or {}).get("historique") or {}).get(project_id) or []
    return [Chantier(**raw) for raw in reversed(rows)]


def _result_open(row, lines_of_recette):
    """The result the destination opens: of the chantiers whose D01
    records give a result, the first to judge, else the first active one,
    else the last one ended; as the panel draws it, or None."""
    if row is None or row["value"] is None:
        return None
    projects, _ = projects_from_value(row["value"])
    found = [(project, chantier) for project in projects
             for chantier in project.chantiers + _historique(row["value"], project.project_id) if chantier.outcome]
    ranked = sorted(found, key=lambda pair: (pair[1].outcome["issue"] not in outcome_mod.JUDGED_NOW,
                                             pair[1].termine))
    if not ranked:
        return None
    project, chantier = ranked[0]
    return _result_view(project, chantier,
                        lines_of_recette if project.display_name == FACTORY_PROJECT else [])


def _result_view(project, chantier, lines_of_recette):
    """What the panel of the result says: what it is about, its issue, its
    title and summary, its dossier (its parts above the bar) or its
    follow-up."""
    outcome = chantier.outcome
    issue = outcome["issue"]
    view = {"about": "%s · %s" % (project.display_name, chantier.titre), "issue": issue, "chantier": chantier.id,
            "project_url": project_page_url(project.project_id),
            "label": outcome["label"], "sentence": outcome["sentence"], "history": outcome["history"],
            "judged_now": issue in outcome_mod.JUDGED_NOW}
    if not view["judged_now"]:
        view.update(title=FOLLOW_UP, summary=outcome["sentence"], resources=[], reports=[])
        return view
    view["title"] = outcome["title"] or "Le résultat attend ton avis"
    view["summary"] = outcome["summary"] or ""
    to_verify = outcome["unverified"] if outcome["pack_read"] else [DOSSIER_UNREAD]
    resources = [{"label": label, "detail": detail, "opens": True} for label, detail in OPENING]
    resources.append({"label": TO_VERIFY, "opens": False, "said": to_verify, "recette": list(lines_of_recette)})
    # « Version et sources » the dossier leaves empty, or does not have, is
    # given by the records: the version delivered and its dossier.
    rubrics = [part for part in outcome.get("rubrics") or [] if part["label"] != VERSION or part["said"]]
    resources += [{"label": part["label"], "opens": False, "said": part["said"]} for part in rubrics]
    if not any(part["label"] == VERSION for part in rubrics):
        resources.append({"label": VERSION, "opens": False, "said": _version(outcome)})
    view["resources"] = resources
    view["reports"] = [{"label": part["label"], "opens": False, "said": part["said"]} for part in outcome["reports"]]
    return view


def _version(outcome):
    """« Version et sources » of a result its dossier does not give: the
    version delivered, the fingerprint of its dossier, its Spec."""
    lines = []
    if outcome["commit"]:
        lines.append("Version livrée : commit %s." % str(outcome["commit"])[:7])
    if outcome["pack"]:
        lines.append("Empreinte du dossier : %s." % outcome["pack"])
    if outcome["spec"]:
        lines.append("Spec : %s." % outcome["spec"])
    return lines


def _projects(row, beads, requests):
    """One card per declared project, those something waits for first, in
    the order of what waits: its name, its current chantier and its stage
    -- the issue of its result when the D01 records give one --, its
    figures and the line of its release when the tracker holds them. A
    project with no active chantier shows its last one ended."""
    if row is None or row["value"] is None:
        return []
    projects, _ = projects_from_value(row["value"])
    cards = {bead.get("id"): _record(bead, PROJECT_CARD) for bead in beads}
    waiting = [request["projet"] for request in requests]
    order = {name: waiting.index(name) if name in waiting else len(waiting) for name in waiting}
    out = []
    for project in sorted(projects, key=lambda p: order.get(p.display_name, len(waiting))):
        current = next((c for c in project.chantiers if not c.termine), None) or next(
            iter(_historique(row["value"], project.project_id)), None)
        card = (cards.get(current.id) if current else None) or {}
        out.append({
            "id": project.project_id,
            "name": project.display_name,
            "chantier": "%s · %s" % (current.titre, current.issue or card.get("stage") or current.stage) if current
            else "Aucun chantier en cours",
            "figures": [str(figure) for figure in card.get("figures") or []],
            "release": card.get("release"),
        })
    return out


# --- rendering -----------------------------------------------------------------

def _e(text):
    return html.escape(str(text))


def render_overview(view, anchors, details_html=""):
    """The ``main`` of the destination for ``view``, numbered by ``anchors``
    as the reference numbers its parts; ``details_html``, the zones of the
    cockpit not folded into Panorama yet, folded under it."""
    state = view["state"]
    if state == LOADING:
        checked = "Lecture des sources en cours"
    elif state == ERROR:
        checked = "Aucune source lue"
    elif view["stale"]:
        checked = "Dernière observation · %s (Paris)" % view["checked"]
    else:
        checked = "Vérifié à %s (Paris)" % view["checked"]
    parts = ['<div class="pn-overview-head" %s><div %s><h1 %s>Vue d’ensemble</h1><small %s>%s</small></div></div>'
             % (anchors("overview-head"), anchors("div"), anchors("h1"), anchors("small"), _e(checked))]
    if state == LOADING:
        parts.append(
            '<section class="pn-panel" role="status" %s><h2 %s>Lecture en cours…</h2>%s</section>'
            % (anchors("panel"), anchors("h2"), "".join('<div class="pn-skeleton" %s></div>' % anchors("skeleton")
                                                         for _ in range(3))))
        parts.append(_render_alone(view))
    elif state == ERROR:
        parts.append(
            '<section class="pn-error" role="alert" %s><h2 %s>Cette vue est indisponible</h2>'
            "<p %s>L’état réel est inconnu. Les sources de l’usine n’ont pas répondu.</p>"
            '<form method="post" action="/api/health/recheck"><button type="submit" %s>Réessayer</button></form>'
            "</section>" % (anchors("error"), anchors("h2"), anchors("p"), anchors("button")))
        parts.append(_render_alone(view))
    elif state == EMPTY:
        parts.append('<section class="pn-panel pn-empty" %s><h2 %s>Rien à afficher ici</h2>'
                     "<p %s>Aucun élément dans cette vue.</p></section>"
                     % (anchors("panel"), anchors("h2"), anchors("p")))
    else:
        parts.append(_render_content(view, anchors))
    legacy = ""
    if details_html:
        legacy = ('<details class="pn-legacy" id="pn-legacy"><summary>%s</summary>'
                  '<div class="pn-legacy-body">%s</div></details>' % (LEGACY_SUMMARY, details_html))
    return '<div class="pn-overview">%s</div>%s%s' % ("".join(parts), legacy, SCRIPT)


def _render_content(view, anchors):
    parts = []
    if view["stale"]:
        parts.append('<div class="pn-notice" role="status" %s>Lecture périmée · état actuel inconnu. '
                     "Dernières valeurs conservées ; actions indisponibles.</div>" % anchors("notice"))
    metrics = []
    grid = anchors("metric-grid")
    for number, (label, value, caption, href) in enumerate(view["indicators"]):
        metrics.append(
            '<div class="pn-metric%s" %s><a href="%s">'
            '<span class="pn-metric-label" %s>%s</span><strong %s>%s</strong><small %s>%s</small></a></div>'
            % (" pn-emphasis" if number == 0 else "", anchors("metric"), _e(href), anchors("metric-label"),
               _e(label), anchors("strong"), _e(value), anchors("small"), _e(caption)))
    parts.append('<div class="pn-metric-grid" %s>%s</div>' % (grid, "".join(metrics)))
    parts.append(_render_activity(view["activity"], anchors))
    panel, heading = anchors("panel"), anchors("section-heading")
    parts.append(
        '<section class="pn-panel" %s><div class="pn-section-heading" %s><h2 %s>Derniers runs</h2>%s</div>'
        '<iframe class="pn-runs" title="Cartes des derniers runs" srcdoc="%s" %s></iframe></section>'
        % (panel, heading, anchors("h2"), open_button("/runs", "Tout voir", anchors("link"), "pn-link"),
           _e(_runs_document(view["runs"])), anchors("overview-runs")))
    inbox, requests_panel = anchors("inbox"), anchors("panel")
    title = '<h2 %s>Ce qui t’attend</h2>' % anchors("h2")
    result = view["dossier"]
    opened = result["chantier"] if result else (view["requests"][0]["id"] if view["requests"] else None)
    lines = _render_lines(view["requests"], opened, anchors)
    opened_html = _render_result(view, anchors)
    parts.append('<div class="pn-inbox" id="pn-inbox" %s><div class="pn-panel pn-requests" %s>%s%s%s</div>%s</div>'
                 % (inbox, requests_panel, title, _unknown_notice(view), lines, opened_html))
    parts.append(_render_projects(view["projects"], anchors, view["projects_unread"]))
    return "".join(parts)


# The frame of the chart of the reference: the days along x, 105 px apart
# from x 55; the volumes along y, from y 195 (none) up to 162 px higher, with
# four lines of the grid at a quarter, a half and three quarters of the top.
CHART_DAYS = (("Lun", "Lundi"), ("Mar", "Mardi"), ("Mer", "Mercredi"), ("Jeu", "Jeudi"), ("Ven", "Vendredi"),
              ("Sam", "Samedi"), ("Dim", "Dimanche"))
CHART_ZERO, CHART_HEIGHT, CHART_STEP = 195, 162, 105


def _render_activity(activity, anchors):
    """« Activité sur 7 jours », folded: the key of the three series, then
    their chart, the volumes a source said of each day (``activity``:
    series -> seven volumes, Monday first), or, without one, that they are
    not collected -- no line is drawn of a volume no source gave."""
    bilan, summary, chart_key = anchors("bilan"), anchors("summary"), anchors("chart-key")
    key = "".join('<span style="--series:%s;--dash:%s" %s>%s</span>'
                  % (colour, "dashed" if dashes.startswith("8") else "dotted" if dashes else "solid",
                     anchors("span"), _e(label))
                  for label, colour, dashes in CHART_SERIES)
    if activity:
        top = max(3, -(-max(max(volumes) for volumes in activity.values()) // 3) * 3)
        scale = CHART_HEIGHT / top
        lines = "".join('<line x1="40" y1="%s" x2="695" y2="%s" %s></line>'
                        % (_n(CHART_ZERO - tick * scale), _n(CHART_ZERO - tick * scale), anchors("line"))
                        for tick in (0, top / 3, 2 * top / 3, top))
        grid = '<g stroke="var(--line)" %s>%s</g>' % (anchors("g"), lines)
        g = anchors("g")
        labels = "".join('<text x="20" y="%s" %s>%s</text>' % (_n(CHART_ZERO + 4 - tick * scale), anchors("text"),
                                                               _n(tick))
                         for tick in (0, top / 3, 2 * top / 3, top))
        labels += "".join('<text x="%d" y="222" %s>%s</text>' % (45 + CHART_STEP * day, anchors("text"), short)
                          for day, (short, _) in enumerate(CHART_DAYS))
        series = []
        for label, colour, dashes in CHART_SERIES:
            volumes = activity.get(label)
            if not volumes:
                continue
            points = [(55 + CHART_STEP * day, _n(CHART_ZERO - volume * scale)) for day, volume in enumerate(volumes)]
            series.append('<polyline fill="none" stroke="%s" stroke-width="2.5" stroke-linejoin="round" '
                          'stroke-linecap="round"%s points="%s" %s></polyline>'
                          % (colour, ' stroke-dasharray="%s"' % dashes if dashes else "",
                             " ".join("%d,%s" % point for point in points), anchors("polyline")))
            for (x, y), volume, (_, day) in zip(points, volumes, CHART_DAYS):
                series.append('<circle cx="%d" cy="%s" r="4" fill="%s" %s><title %s>%s · %s : %s</title></circle>'
                              % (x, y, colour, anchors("circle"), anchors("title"), _e(label), day, _n(volume)))
        chart = grid + '<g fill="var(--muted)" font-size="11" %s>%s</g>%s' % (g, labels, "".join(series))
        note = _activity_table(activity)
    else:
        chart = '<g stroke="var(--line)">%s</g>' % "".join(
            '<line x1="40" y1="%d" x2="695" y2="%d"></line>' % (y, y) for y in (195, 141, 87, 33))
        note = "<p>Volumes quotidiens non collectés : aucune source ne les fournit encore au cockpit.</p>"
    return (
        '<details class="pn-panel pn-activity" %s><summary %s>Activité sur 7 jours</summary>'
        '<div class="pn-chart-key" %s>%s</div>'
        '<svg class="pn-chart" viewBox="0 0 720 235" role="img" aria-label="%s" data-anchor="%s-1">%s</svg>'
        "%s%s</details>"
    ) % (bilan, summary, chart_key, key, _e(CHART_LABEL), anchor_slug(CHART_LABEL), chart, note,
         open_button("/analyses", "Explorer les métriques", anchors("link"), "pn-link"))


def _activity_table(activity):
    """The volumes of the chart as a table, for a reader that does not see
    it: one row a series, one column a day."""
    head = "".join('<th scope="col">%s</th>' % day for _, day in CHART_DAYS)
    rows = "".join('<tr><th scope="row">%s</th>%s</tr>'
                   % (_e(label), "".join("<td>%s</td>" % _n(volume) for volume in activity[label]))
                   for label, _, _ in CHART_SERIES if activity.get(label))
    return ('<table class="pn-sr-only"><caption>%s</caption><tr><th scope="col">Série</th>%s</tr>%s</table>'
            % (_e(CHART_LABEL), head, rows))


def _n(number):
    """A number of the chart as the reference writes it: no ``.0``."""
    return ("%.2f" % number).rstrip("0").rstrip(".")


def _render_lines(requests, opened, anchors=None):
    """The lines of « Ce qui t’attend »: each request said in the words of
    the cockpit, the one open marked; each line opens its request."""
    def anchor(name):
        return anchors(name) if anchors else ""

    return "".join(
        '<button type="button" class="pn-request" aria-current="%s" data-request="%s" %s><strong %s>%s</strong>'
        "%s<small %s>%s</small></button>"
        % ("true" if request["id"] == opened else "false", _e(request["id"]), anchor("request"), anchor("strong"),
           _e(request["quoi"]),
           '<span class="pn-origin">Texte écrit : « %s »</span>' % _e(request["origine"]) if request["origine"] else "",
           anchor("small"),
           _e(" · ".join(filter(None, (request["request"].niveau if request["request"].niveau == URGENT else "",
                                        request["projet"], request["pourquoi"])))))
        for request in requests
    ) or "<p>Rien ne t’attend.</p>"


def _render_requests(view, opened, anchors=None):
    """Every request of « Pour moi » opened in its article, beside the
    lines; the one ``opened`` shown, the first carrying the anchor of the
    panel of the reference when no result holds it. The request of the
    result is the result's panel."""
    result = view["dossier"]
    out = []
    for request in view["requests"]:
        if result and request["id"] == result["chantier"]:
            continue
        shown = request["id"] == opened
        out.append(render_request(request["request"], view["now"], request["links"], stale=view["stale"],
                                  shown=shown, anchor=anchors("panel") if shown and anchors else "",
                                  undelivered=request["undelivered"]))
    return "".join(out)


def _render_alone(view):
    """« Ce qui t’attend » while the tracker is not read: what the cockpit
    raised itself, outside the parts the reference numbers."""
    if not view["requests"]:
        return ""
    opened = view["requests"][0]["id"]
    return ('<div class="pn-inbox" id="pn-inbox"><div class="pn-panel pn-requests"><h2>Ce qui t’attend</h2>%s%s</div>'
            "%s</div>" % (_unknown_notice(view), _render_lines(view["requests"], opened), _render_requests(view, opened)))


def _unknown_notice(view):
    """The list is not whole: what comes from the tracker is unknown."""
    return '<p class="pn-unknown" role="status">%s</p>' % _e(view["unknown"]) if view["unknown"] else ""


def _render_result(view, anchors):
    """The panel of the result open under « Ce qui t’attend »: a result to
    judge, with its dossier above its bar; a result judged, with its
    follow-up; without one, the first request open with its gestures. The
    other requests are opened beside, hidden until their line is chosen."""
    result = view["dossier"]
    if result is None:
        if not view["requests"]:
            return ('<article class="pn-panel pn-result" %s><h2>Rien ne t’attend</h2>'
                    "<p>Aucune demande ouverte.</p></article>" % anchors("panel"))
        return _render_requests(view, view["requests"][0]["id"], anchors)
    panel = anchors("panel")
    parts = ['<small %s>%s</small><h2 %s>%s</h2>'
             % (anchors("small"), _e(result["about"]), anchors("h2"), _e(result["title"]))]
    if result["summary"]:
        parts.append("<p %s>%s</p>" % (anchors("p"), _e(result["summary"])))
    if not result["judged_now"]:
        # Judged: its follow-up, then the bar, Essai and Avis unavailable.
        parts.append(_render_folded({"label": HISTORY, "said": result["history"]}, anchors))
        reason = UNSURE_RESULT if result["issue"] in (outcome_mod.UNKNOWN, outcome_mod.INCONSISTENT) else JUDGED_RESULT
    else:
        if result["issue"] != outcome_mod.TO_JUDGE:
            # Outdated, or its trial down: said before anything of the dossier.
            parts.append('<p class="pn-result-issue" role="status">%s</p>' % _e(result["sentence"]))
        resource_list = anchors("resource-list")
        parts.append('<div class="pn-resources" %s>%s</div>'
                     % (resource_list, "".join(_render_resource(r, anchors) for r in result["resources"])))
        parts.append("".join(_render_folded(report, anchors) for report in result["reports"]))
        reason = UNWIRED_RESULT
    request = next((r["request"] for r in view["requests"] if r["id"] == result["chantier"]), None)
    if request is not None:
        # The request of the result: its identifiers and links, folded.
        parts.append(render_details(request, links_of(request, result["project_url"])))
    dock = anchors("actions-possibles")
    parts.append(
        '<div class="pn-dock" role="group" aria-label="Actions possibles" %s>'
        '<a class="pn-button" role="link" aria-disabled="true" tabindex="-1" %s>Essai ↗</a><button type="button" disabled %s>Avis</button>'
        '<p class="pn-unwired">%s</p></div>' % (dock, anchors("button"), anchors("button"), reason))
    return '<article class="pn-panel pn-result" id="%s" data-open="%s" data-issue="%s" %s>%s</article>%s' % (
        RESULT_PANEL_ID, _e(result["chantier"]), _e(result["issue"]), panel, "".join(parts),
        _render_requests(view, result["chantier"]))


def _render_resource(resource, anchors):
    """A resource of the dossier: one that opens -- not from this view yet,
    so drawn unavailable --, or one that unfolds."""
    if not resource.get("opens"):
        return _render_folded(resource, anchors)
    button, label = anchors("button"), anchors("span")
    return ('<button type="button" class="pn-resource" disabled %s><span %s><strong %s>%s</strong><small %s>%s</small>'
            '</span><span aria-hidden="true" %s>↗</span></button>'
            % (button, label, anchors("strong"), _e(resource.get("label")), anchors("small"),
               _e(resource.get("detail") or ""), anchors("span")))


def _render_folded(part, anchors):
    """A part of the dossier that unfolds: open, the lines its record gives
    it, or that the source gave none; then, for « Ce qui reste à
    vérifier », the recette of the cockpit -- a list of its own, outside
    the numbering of the parts the reference draws."""
    said = [line for line in part.get("said") or [] if isinstance(line, str)] or [NOT_GIVEN]
    details, summary = anchors("details"), anchors("summary")
    lines = "".join("<p %s>%s</p>" % (anchors("p"), _e(line)) for line in said)
    if part.get("recette"):
        lines += ('<ul class="pn-recette" aria-label="Recette du cockpit">%s</ul>'
                  % "".join("<li>%s</li>" % _e(line) for line in part["recette"]))
    return "<details %s><summary %s>%s</summary>%s</details>" % (details, summary, _e(part.get("label")), lines)


def _render_projects(projects, anchors, unread=False):
    panel, title, rows_anchor = anchors("panel"), '<h2 %s>Projets</h2>' % anchors("h2"), anchors("rows")
    rows = []
    for project in projects:
        row, holder, name, chantier, stats = (anchors("row"), anchors("div"), anchors("strong"), anchors("small"),
                                              anchors("small-stats"))
        figures = "".join("<span %s>%s</span>" % (anchors("span"), _e(figure)) for figure in project["figures"]) or \
            "<span %s>Volumes non collectés</span>" % anchors("span")
        rows.append(
            '<div class="pn-row pn-project" %s><a href="%s">'
            '<div %s><strong %s>%s</strong><small %s>%s</small><div class="pn-stats" %s>%s</div>'
            '<div class="pn-release" %s>%s</div></div><span aria-hidden="true" %s>→</span></a></div>'
            % (row, _e(project_page_url(project["id"])), holder, name, _e(project["name"]), chantier,
               _e(project["chantier"]), stats, figures, anchors("release-info"),
               _e(project["release"] or "Release non cadrée"), anchors("span")))
    body = "".join(rows) or ("<p>Lecture des projets en cours : leur état réel n’est pas encore connu.</p>" if unread
                             else "<p>Aucun projet déclaré.</p>")
    return '<section class="pn-panel pn-projects" %s>%s<div class="pn-rows" %s>%s</div></section>' % (
        panel, title, rows_anchor, body)


# The cards of the last runs, inside their frame, as the reference draws
# them: three a row, one under the other in a frame under 850 px. A card
# opens the destination Runs; opening the run itself is T44's. The status of
# a run waiting for a decision is written darker in the light theme, where
# the reference's is under 4.5:1 on the surface.
RUNS_CSS = (
    ":root{color-scheme:light;--surface:#fff;--line:#dbe0e8;--ink:#17202e;--muted:#657185;--accent:#415fce;"
    "--ok:#1c7954;--human:#e4bc6d;--code:#55b5ae;--agent:#a897eb;--wait:#85590f}"
    "@media (prefers-color-scheme: dark){:root{color-scheme:dark;--surface:#161b23;--line:#2a3240;--ink:#ecedf3;"
    "--muted:#9aa6b9;--accent:#99aaff;--ok:#55c89d;--wait:#e4bc6d}}"
    "*{box-sizing:border-box}html,body{margin:0;background:var(--surface);color:var(--ink);font:15px system-ui,sans-serif}"
    ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}"
    ".card{display:block;height:100%;background:var(--surface);border:1px solid var(--line);border-radius:10px;"
    "padding:18px;color:inherit;text-decoration:none}"
    ".card:hover{border-color:var(--accent)}.card:focus-visible{outline:2px solid var(--accent);outline-offset:-4px}"
    ".card h2{margin:12px 0 7px;font-size:18px;overflow-wrap:anywhere}"
    ".card p{margin:0 0 14px;font-size:14px;line-height:1.5;color:var(--muted);overflow-wrap:anywhere}"
    ".card-top{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted)}"
    ".badge{color:var(--ok)}.badge.live{color:var(--accent)}.badge.wait{color:var(--wait)}"
    ".live-dot{display:inline-block;width:7px;height:7px;border-radius:100%;background:var(--accent);margin-right:6px}"
    ".card-foot{display:flex;justify-content:space-between;gap:10px;margin-top:15px;font-size:13px;color:var(--muted)}"
    ".mono{font:13px ui-monospace,monospace}"
    ".mini{display:grid;gap:6px;font-size:11px}"
    ".mini-row{display:grid;grid-template-columns:70px 1fr;gap:8px;align-items:center}"
    ".mini-track{height:8px;position:relative;border-bottom:1px solid var(--line);"
    "background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),var(--line) 25%)}"
    ".mini-bar{position:absolute;height:5px;border-radius:4px;top:1px;background:var(--agent);min-width:2px}"
    ".mini-bar.code{background:var(--code)}.mini-bar.human{background:var(--human)}"
    ".mini-axis{margin:8px 0 0 78px;display:flex;justify-content:space-between;color:var(--muted);font-size:10px}"
    ".none{margin:12px 0;font-size:14px;line-height:1.5;color:var(--muted)}"
    "@media(max-width:850px){.grid{grid-template-columns:1fr}}"
)


def _runs_document(runs):
    """The document of the frame « Derniers runs »: a card for each run of
    ``runs``, or that the cockpit reads none."""
    anchors = Anchors()
    cards = "".join(_run_card(run, anchors) for run in runs)
    body = ('<div class="grid" %s>%s</div>' % (anchors("grid"), cards) if cards
            else '<p class="none">Aucun run récent n’est lu par le cockpit.</p>')
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><base target="_top">'
            "<style>%s</style></head><body>%s</body></html>" % (RUNS_CSS, body))


def _run_card(run, anchors):
    """One card: the workflow and the status of the run, its title and its
    step, a lane per participant with a bar per job, placed within the run,
    its axis, its start and its duration."""
    elapsed = run["elapsed"]
    card, top = anchors("card"), anchors("card-top")
    tone = run.get("tone")
    dot = '<span class="live-dot" %s></span>' % anchors("live-dot") if tone in ("wait", "live") else ""
    head = ('<div class="card-top" %s><span %s>%s</span><span class="badge %s" %s>%s%s</span></div>'
            % (top, anchors("span"), _e(run["type"]), tone if tone in ("wait", "live") else "", anchors("badge"),
               dot, _e(run["status"])))
    title = "<h2 %s>%s</h2><p %s>%s</p>" % (anchors("h2"), _e(run["title"]), anchors("p"), _e(run["step"]))
    mini = anchors("mini")
    rows = []
    for lane in run["lanes"]:
        row, name, track = anchors("mini-row"), anchors("span"), anchors("mini-track")
        bars = "".join('<span class="mini-bar %s" style="left:%s%%;width:%s%%" %s></span>'
                       % (_e(lane["kind"]), _n(100 * start / elapsed), _n(100 * (end - start) / elapsed),
                          anchors("mini-bar"))
                       for start, end in lane["jobs"])
        rows.append('<div class="mini-row" %s><span %s>%s</span><div class="mini-track" %s>%s</div></div>'
                    % (row, name, _e(lane["name"]), track, bars))
    axis = anchors("mini-axis")
    ticks = "".join("<span %s>%s</span>" % (anchors("span"), _tick(seconds)) for seconds in (0, elapsed / 2, elapsed))
    foot = anchors("card-foot")
    return (
        '<a class="card" href="%s" %s>%s%s<div class="mini" %s>%s</div><div class="mini-axis" %s>%s</div>'
        '<div class="card-foot" %s><span %s>Début %s (Paris)</span><span class="mono" %s>%s</span></div></a>'
    ) % (_e(run.get("href") or "/runs"), card, head, title, mini, "".join(rows), axis, ticks, foot, anchors("span"), _e(run["started"]),
         anchors("mono"), duration(elapsed))


def _tick(seconds):
    """A mark of the axis of a card: « 0s », « 45s », « 6m », « 4m06s »."""
    seconds = int(round(seconds))
    minutes, rest = divmod(seconds, 60)
    if not minutes:
        return "%ds" % rest
    return "%dm%02ds" % (minutes, rest) if rest else "%dm" % minutes

CSS = """
:root{--pn-series-1:#415fce;--pn-series-2:#1c7954;--pn-series-3:#97691e}
@media (prefers-color-scheme: dark){:root{--pn-series-1:#91a7ff;--pn-series-2:#52c9b1;--pn-series-3:#e6ba70}}
.pn-overview-head small{display:block;margin-bottom:20px;color:var(--pn-muted-text);font-size:12px}
.pn-overview-head h1{font-size:27px;margin:0 0 6px}
.pn-overview small{color:var(--pn-muted-text);font-size:12px}
.pn-overview button{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:10px 14px;cursor:pointer}
.pn-overview button:hover{border-color:var(--accent)}
.pn-overview button:disabled{opacity:.5;cursor:not-allowed}
.pn-overview button.pn-link{padding:0;border:0;border-radius:4px;background:none;color:var(--accent)}
.pn-overview button.pn-link:hover{text-decoration:underline}
.pn-notice{padding:12px;border:1px solid var(--line);border-radius:6px;color:var(--pn-warn-text);margin-bottom:18px;
  overflow-wrap:anywhere}
.pn-metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
.pn-metric{border:1px solid var(--line);border-radius:10px;background:var(--surface);min-width:0}
.pn-metric>a{display:block;padding:18px;border-radius:10px;color:inherit;text-decoration:none}
.pn-metric:hover{border-color:var(--accent)}
.pn-metric.pn-emphasis{border-color:var(--accent)}
.pn-metric strong{display:block;font-size:28px;margin:7px 0}
.pn-metric small{display:block}
.pn-metric-label{font-size:13px;color:var(--pn-muted-text)}
.pn-activity summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-chart-key{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;margin:12px 0}
.pn-chart-key span:before{content:'';display:inline-block;width:20px;height:0;border-top:3px var(--dash) var(--series);
  vertical-align:middle;margin-right:8px}
.pn-sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);
  white-space:nowrap;border:0}
.pn-chart{width:100%;height:auto;max-height:290px;display:block}
.pn-activity p{margin:8px 0;color:var(--pn-muted-text);font-size:14px}
.pn-section-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:6px}
.pn-section-heading h2{margin:0}
.pn-runs{display:block;width:100%;height:330px;margin-top:12px;border:0;background:var(--surface)}
@media (max-width:850px){.pn-runs{height:890px}}
.pn-inbox{display:grid;grid-template-columns:330px minmax(0,1fr);gap:20px;align-items:start}
.pn-inbox>*{min-width:0}
.pn-requests{padding:0}
.pn-requests h2{padding:20px 20px 0}
.pn-requests>p{padding:0 20px 20px}
.pn-overview .pn-request{display:block;width:100%;text-align:left;border:0;border-top:1px solid var(--line);
  border-radius:0;padding:20px;background:transparent}
.pn-overview .pn-request[aria-current=true]{background:var(--pn-surface-2);box-shadow:inset 4px 0 0 var(--accent)}
.pn-request strong{display:block;margin-bottom:8px;overflow-wrap:anywhere}
.pn-request small{display:block;overflow-wrap:anywhere}
.pn-origin{display:block;margin-bottom:8px;font-size:14px;overflow-wrap:anywhere}
.pn-result h2{margin-top:12px;overflow-wrap:anywhere}
.pn-result>p{margin:0 0 8px}
.pn-result-issue{padding:10px 12px;border:1px solid var(--line);border-left:3px solid var(--pn-warn-text);
  border-radius:6px;color:var(--ink);overflow-wrap:anywhere}
.pn-resources{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:22px}
.pn-overview .pn-resource{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;width:100%;
  min-height:95px;padding:15px;text-align:left;border-color:var(--line)}
.pn-overview .pn-resource:disabled{opacity:1;cursor:default}
.pn-resource>span:first-child{display:flex;flex-direction:column;gap:4px;min-width:0;overflow-wrap:anywhere}
.pn-resources details{grid-column:1/-1}
.pn-result details{border-top:1px solid var(--line);padding:14px 0}
.pn-result>details{margin-top:8px}
.pn-result summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-result details p{font-size:14px;margin:10px 0 0;overflow-wrap:anywhere}
.pn-recette{margin:10px 0 0;padding-left:20px;font-size:14px}
.pn-recette li{margin-top:6px;overflow-wrap:anywhere}
.pn-dock{display:flex;flex-wrap:wrap;gap:12px;align-items:center;border-top:1px solid var(--line);
  padding-top:18px;margin-top:22px}
.pn-dock>:is(button,.pn-button){flex:1;min-height:54px;font-size:16px;font-weight:650}
.pn-button{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;color:var(--ink);
  background:var(--surface);border:1px solid var(--pn-control-line);border-radius:8px;text-decoration:none}
.pn-button[aria-disabled=true]{opacity:.5;cursor:not-allowed}
.pn-unwired{flex-basis:100%;margin:0;font-size:13px;color:var(--pn-muted-text)}
.pn-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  border-bottom:1px solid var(--line)}
.pn-row:last-child{border-bottom:0}
.pn-row>*{min-width:0}
.pn-row strong{display:block;margin-bottom:5px;overflow-wrap:anywhere}
.pn-row small{display:block;overflow-wrap:anywhere}
.pn-project{display:block;padding:0}
.pn-project>a{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  color:inherit;text-decoration:none}
.pn-project>a>*{min-width:0}
.pn-project:hover strong{color:var(--accent)}
.pn-rows{display:grid}
.pn-stats{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:12px;font-size:12px;color:var(--pn-muted-text)}
.pn-release{margin-top:8px;font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.pn-skeleton{height:16px;background:var(--line);border-radius:5px;margin:14px 0;width:65%}
.pn-skeleton:nth-of-type(2){width:85%}
.pn-error{border-left:3px solid var(--pn-warn-text);padding:20px;background:var(--surface);margin-bottom:20px}
.pn-error h2{font-size:19px;margin:0 0 10px}
.pn-error p{margin:0 0 14px}
.pn-empty{text-align:center;padding:55px 20px}
.pn-empty p{color:var(--pn-muted-text)}
.pn-legacy{margin-top:28px;border-top:1px solid var(--line);padding-top:16px}
.pn-legacy>summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-legacy:not([open])>.pn-legacy-body{display:none}
.pn-inbox>[hidden]{display:none}
.pn-unknown{margin:0 20px 14px;padding:10px 12px;border:1px solid var(--line);border-radius:6px;
  color:var(--pn-warn-text);overflow-wrap:anywhere}
@media (max-width:1100px){.pn-inbox{grid-template-columns:minmax(0,1fr)}}
@media (max-width:800px){
  .pn-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pn-metric>a{padding:13px}
  .pn-metric strong{font-size:24px}
  .pn-overview-head h1{font-size:24px}
  .pn-resources{grid-template-columns:minmax(0,1fr)}
  .pn-row,.pn-project>a{align-items:flex-start}
}
""" + POUR_MOI_CSS

# A line of « Ce qui t’attend » opens its request beside the list, in place
# of the one open: the result, or another request with its gestures.
SCRIPT = """
<script>
(function () {
  function openRequest(id) {
    var panels = document.querySelectorAll('#pn-inbox [data-open]');
    var target = null;
    panels.forEach(function (panel) { if (panel.getAttribute('data-open') === id) { target = panel; } });
    if (!target) { return; }
    panels.forEach(function (panel) { panel.hidden = panel !== target; });
    document.querySelectorAll('#pn-inbox .pn-request[data-request]').forEach(function (line) {
      line.setAttribute('aria-current', line.getAttribute('data-request') === id ? 'true' : 'false');
    });
    // On a narrow screen the request opens under the list: the page goes
    // to it.
    if (window.matchMedia('(max-width: 1100px)').matches) { target.scrollIntoView({block: 'start'}); }
  }
  // The frame of the last runs is as tall as its cards: none is cut, none
  // is scrolled to inside the page.
  function fit(frame) {
    var doc = frame.contentDocument;
    if (doc && doc.body) { frame.style.height = Math.ceil(doc.body.getBoundingClientRect().height) + 'px'; }
  }
  document.querySelectorAll('iframe.pn-runs').forEach(function (frame) {
    frame.addEventListener('load', function () { fit(frame); });
    if (frame.contentDocument && frame.contentDocument.readyState === 'complete') { fit(frame); }
  });
  window.addEventListener('resize', function () { document.querySelectorAll('iframe.pn-runs').forEach(fit); });
  document.addEventListener('click', function (event) {
    var request = event.target.closest('.pn-request[data-request]');
    if (request) { openRequest(request.getAttribute('data-request')); }
  });
})();
</script>
"""
