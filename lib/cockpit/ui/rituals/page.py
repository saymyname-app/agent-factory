"""The destination « Rituels et préparation release » of B/Panorama (T41
Prototype Fold, af-r4hrt7; Spec af-2zseit, user stories 167 to 175;
Validated Prototype prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-rituals).

    view = rituals_view(snapshot, query)
    main_html = render_rituals(view, anchors)

:func:`rituals_view` reads, from the read model's snapshot and the query of
the address, what the destination shows; :func:`render_rituals` draws it,
inside the shell of :mod:`cockpit.ui.panorama.shell`. Neither reads a
source.

What it shows:

- the catalogue: the framing of the next release and the four reviews, each
  what it is for, how it is launched and when it last ran -- the record
  ``gc.ritual`` of the bead under its title, when the tracker holds one;
- a ritual under way: the record ``gc.ritual_operation`` of a bead -- the
  ritual, its project, the step it is at, and at the step of a report, of
  the work prepared or of a framing proposed, that content -- drawn at its
  step, with the path of its four steps;
- the launch of a ritual chosen from the catalogue (``?rituel=<key>``, and
  ``&projet=<key>``): its scope or its project to choose, before anything is
  launched. ``?vue=catalogue`` shows the catalogue while a ritual is under
  way.

The commands that would launch an agent or write in the factory -- launch a
review, have a selection prepared, launch the corrections, launch the
preparation of a release, keep a framing -- are not wired to a door here:
each is drawn unavailable, and its bar says so. Nothing on the page shows a
command done that no door recorded.

Every part carries the anchor of the reference (``data-anchor``), numbered
by the :class:`~cockpit.ui.panorama.shell.Anchors` of the page as the frozen
pages number them, in the order the reference draws them.
"""
import html
import json
import urllib.parse

from cockpit.projects.source import from_value as projects_from_value
from cockpit.ui.panorama.shell import anchor_slug
from cockpit.ui.projects.project_page import project_page_url

PATH = "/rituels"
RITUAL = "gc.ritual"
RITUAL_OPERATION = "gc.ritual_operation"
RELEASE = "release"

# The catalogue of the Spec: key, title, what it is for, how it is launched,
# how its last run is named (and the gender of « non renseigné »).
CATALOGUE = (
    (RELEASE, "Préparer la prochaine release",
     "Relier les acquis à une cible révisable, éclaircir les inconnues et proposer le prochain jalon.",
     "CADRAGE DU PROJET", "Dernier cadrage", ""),
    ("incidents", "Revue d’incidents",
     "Comprendre les causes récurrentes et proposer les corrections qui évitent leur retour.",
     "LANCEMENT MANUEL", "Dernière revue", "e"),
    ("architecture", "Revue d’architecture",
     "Repérer les parties difficiles à modifier et proposer des améliorations ciblées.",
     "LANCEMENT MANUEL", "Dernière revue", "e"),
    ("qualite", "Qualité / AI Slop", "Trouver code inutile, duplications et complexité évitable.",
     "LANCEMENT MANUEL", "Dernière revue", "e"),
    ("diagnostic", "Diagnostic Factory", "Comprendre un blocage ou un comportement incohérent de la Factory.",
     "À LA DEMANDE", "Dernière revue", "e"),
)

# The four steps of each path, and the one each step of a ritual is at
# (None: before the first, or past the last).
REVIEW_STEPS = ("1 · Revue", "2 · Ton choix", "3 · Travail précis", "4 · Réalisation")
RELEASE_STEPS = ("1 · Périmètre", "2 · Préparation", "3 · Ton cadrage", "4 · Projet mis à jour")
CURRENT = {
    "confirm": None, "review": 0, "report": 1, "preparing": 2, "ready": 2, "execution": 3, "delivered": None,
}
RELEASE_CURRENT = {"confirm": 0, "review": 1, "report": 2, "saved": 3}

NUMBERS = ("Aucune", "Une", "Deux", "Trois", "Quatre", "Cinq", "Six", "Sept", "Huit", "Neuf", "Dix")
DECISIONS = (("open", "Garder la question ouverte"), ("later", "Reporter après cette release"),
             ("include", "Inclure dans la cible de cette release"))


def rituals_view(snapshot, query=""):
    """What the destination shows: ``catalogue`` (one entry per ritual of
    the Spec), ``operation`` (the ritual under way or whose launch is being
    prepared, None on the catalogue), ``projects`` (key, name of each
    declared project)."""
    params = urllib.parse.parse_qs(query)
    beads_row = snapshot.get("beads")
    beads = None if beads_row is None or beads_row.get("value") is None else [
        bead for bead in beads_row["value"] if isinstance(bead, dict)]
    records = {bead.get("title"): _record(bead, RITUAL) for bead in beads or []}
    catalogue = []
    for key, title, purpose, label, last, gender in CATALOGUE:
        record = records.get(title) or {}
        said = "inconnu%s : le tracker n’est pas lu" % gender if beads is None else "non renseigné%s" % gender
        catalogue.append({"key": key, "title": title, "purpose": purpose, "label": record.get("label") or label,
                          "last": record.get("last") or "%s : %s" % (last, said), "report": bool(record.get("report"))})
    projects = _projects(snapshot.get("projets"))
    operation = next(filter(None, (_record(bead, RITUAL_OPERATION) for bead in beads or [])), None)
    chosen = (params.get("rituel") or [None])[0]
    if params.get("vue") == ["catalogue"]:
        operation = None
    elif chosen in {key for key, *_ in CATALOGUE}:
        operation = _launch(chosen, (params.get("projet") or [None])[0], projects)
    return {"catalogue": catalogue, "operation": operation, "projects": projects}


def _record(bead, key):
    """The record ``key`` of ``bead``'s metadata, or None."""
    raw = (bead.get("metadata") or {}).get(key)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def _projects(row):
    if row is None or row.get("value") is None:
        return []
    projects, _ = projects_from_value(row["value"])
    return sorted(((p.project_id, p.display_name) for p in projects), key=lambda project: project[1])


def _launch(key, project_key, projects):
    """The launch of the ritual ``key`` chosen from the catalogue, before
    anything is launched: on the project ``project_key``, else the first."""
    title = next(title for k, title, *_ in CATALOGUE if k == key)
    project = next((name for k, name in projects if k == project_key), projects[0][1] if projects else "")
    return {"ritual": key, "title": title, "project": project,
            "lead": "cible révisable" if key == RELEASE else "revue à lancer", "step": "confirm"}


# --- rendering -----------------------------------------------------------------

def _e(text):
    return html.escape(str(text))


def _open(anchor, label, path, params=(), css=""):
    """A button that opens ``path`` with ``params``: the button of a form of
    its own sent by GET (its fields carry the query), no script."""
    fields = "".join('<input type="hidden" name="%s" value="%s">' % (_e(name), _e(value)) for name, value in params)
    return '<form class="pn-open" method="get" action="%s">%s<button type="submit"%s %s>%s</button></form>' % (
        _e(path), fields, ' class="%s"' % css if css else "", anchor, _e(label))


def _unwired(anchor, label, css=""):
    """A command no door records from here: drawn, unavailable."""
    return '<button type="button" disabled%s %s>%s</button>' % (' class="%s"' % css if css else "", anchor, _e(label))


def _unwired_note(*commands):
    names = " et ".join("« %s »" % command for command in commands)
    return ('<p class="pn-unwired">%s %s pas encore raccordé%s à cette vue : rien n’est lancé ni enregistré d’ici.</p>'
            % (names, "ne sont" if len(commands) > 1 else "n’est", "s" if len(commands) > 1 else ""))


def render_rituals(view, anchors):
    """The ``main`` of the destination for ``view``, numbered by ``anchors``
    as the reference numbers its parts."""
    operation = view["operation"]
    if operation is None:
        body = _render_catalogue(view["catalogue"], anchors)
    else:
        body = _render_operation(operation, view["projects"], anchors)
    return '<div class="pn-rituals">%s</div>' % body


def _render_catalogue(catalogue, anchors):
    parts = ['<h1 %s>Rituels</h1>' % anchors("h1"),
             '<p class="pn-page-lead" %s>Une revue produit des propositions. Tu choisis lesquelles faire préparer.</p>'
             % anchors("page-lead")]
    grid = anchors("ritual-grid")
    cards = []
    for ritual in catalogue:
        panel, label, title, purpose, last, actions = (anchors("panel"), anchors("small"), anchors("h2"),
                                                       anchors("p"), anchors("small"), anchors("actions"))
        buttons = _open(anchors("primary"), "Préparer le lancement", PATH, (("rituel", ritual["key"]),), "pn-primary")
        if ritual["report"]:
            buttons += ('<button type="button" class="pn-link" disabled title="Pas encore raccordé à cette vue" %s>'
                        "Voir le dernier rapport</button>" % anchors("link"))
        cards.append(
            '<section class="pn-panel pn-ritual-card" %s><small %s>%s</small><h2 %s>%s</h2><p %s>%s</p>'
            '<small %s>%s</small><div class="pn-actions" %s>%s</div></section>'
            % (panel, label, _e(ritual["label"]), title, _e(ritual["title"]), purpose, _e(ritual["purpose"]),
               last, _e(ritual["last"]), actions, buttons))
    parts.append('<div class="pn-ritual-grid" %s>%s</div>' % (grid, "".join(cards)))
    return "".join(parts)


def _render_operation(operation, projects, anchors):
    """The page of a ritual at its step: the way back to the catalogue, its
    title, its project, its path, then the panel of the step."""
    release = operation.get("ritual") == RELEASE
    step = operation.get("step")
    crumb = anchors("crumb")
    back = _open(anchors("link"), "← Rituels", PATH, (("vue", "catalogue"),), "pn-link")
    parts = ['<div class="pn-crumb" %s>%s</div>' % (crumb, back),
             '<h1 %s>%s</h1>' % (anchors("h1"), _e(operation.get("title") or "")),
             '<p class="pn-page-lead" %s>%s</p>' % (
                 anchors("page-lead"), _e(" · ".join(filter(None, (operation.get("project"), operation.get("lead"))))))]
    steps, current = (RELEASE_STEPS, RELEASE_CURRENT) if release else (REVIEW_STEPS, CURRENT)
    path = anchors("ritual-path")
    marks = []
    for number, label in enumerate(steps):
        if number == current.get(step):
            marks.append('<span class="pn-current" aria-current="step" %s>%s</span>' % (anchors("current"), label))
        else:
            marks.append("<span %s>%s</span>" % (anchors("span"), label))
    parts.append('<div class="pn-ritual-path" %s>%s</div>' % (path, "".join(marks)))
    draw = (RELEASE_PANELS if release else REVIEW_PANELS).get(step)
    if draw is None:
        parts.append('<section class="pn-panel" %s><h2 %s>Étape inconnue</h2><p %s>Le cockpit ne sait pas montrer '
                     "l’étape « %s » de ce rituel.</p></section>" % (anchors("panel"), anchors("h2"), anchors("p"),
                                                                     _e(step)))
    else:
        parts.append('<section class="pn-panel pn-step" %s>%s</section>'
                     % (anchors("panel"), draw(operation, projects, anchors)))
    return "".join(parts)


def _options(operation, projects, anchors):
    """The projects to choose from, the one of the ritual first."""
    names = [operation.get("project")] if operation.get("project") else []
    names += [name for _, name in projects if name not in names]
    return "".join('<option%s %s>%s</option>' % (" selected" if number == 0 else "", anchors("option"), _e(name))
                   for number, name in enumerate(names))


# The panels of a review, by step.

def _review_confirm(operation, projects, anchors):
    purpose = next((p for key, _, p, *_ in CATALOGUE if key == operation.get("ritual")), "")
    title, lead, label, select = anchors("h2"), anchors("p"), anchors("label"), anchors("ritual-target")
    options = _options(operation, projects, anchors)
    preview, cost = anchors("change-preview"), anchors("p")
    actions = anchors("actions")
    cancel = _open(anchors("button"), "Annuler", PATH, (("vue", "catalogue"),))
    launch = _unwired(anchors("primary"), "Lancer la revue", "pn-primary")
    return (
        '<h2 %s>Lancer la revue</h2><p %s>%s</p>'
        '<label %s>Périmètre<select id="ritual-target" %s>%s</select></label>'
        '<div class="pn-change-preview" %s>Produit un rapport et des propositions. Ne modifie aucun code ni paramètre.'
        "<p %s>Utilise un agent et consomme des tokens. Coût exact non connu.</p></div>"
        '<div class="pn-actions" %s>%s%s%s</div>'
    ) % (title, lead, _e(purpose), label, select, options, preview, cost, actions, cancel, launch,
         _unwired_note("Lancer la revue"))


def _review_under_way(operation, projects, anchors):
    title, lead = anchors("h2"), anchors("p")
    run = _open(anchors("link"), "Voir le run", "/runs", css="pn-link")
    return ('<h2 %s>Revue en cours</h2><p %s>L’agent examine les sources du périmètre %s.</p>%s'
            '<p class="pn-readonly-note" %s>Les propositions apparaîtront dans « Pour moi » à la fin de la revue.</p>'
            % (title, lead, _e(operation.get("project") or ""), run, anchors("readonly-note")))


def _review_report(operation, projects, anchors):
    report = operation.get("report") or {}
    proposals = [p for p in report.get("proposals") or [] if isinstance(p, dict)]
    count = len(proposals)
    heading = "%s proposition%s à examiner" % (NUMBERS[count] if count < len(NUMBERS) else count, "s" if count > 1 else "")
    parts = ['<h2 %s>%s</h2><p %s>%s</p>' % (anchors("h2"), _e(heading), anchors("p"), _e(report.get("summary") or ""))]
    for proposal in proposals:
        choice, box, text, title, why, scope = (anchors("proposal-choice"), anchors("input"), anchors("span"),
                                                anchors("strong"), anchors("small"), anchors("small"))
        parts.append(
            '<label class="pn-proposal-choice" %s><input type="checkbox"%s %s><span %s><strong %s>%s</strong>'
            "<small %s>%s</small><small %s>%s</small></span></label>"
            % (choice, " checked" if proposal.get("chosen") else "", box, text, title, _e(proposal.get("title") or ""),
               why, _e(proposal.get("why") or ""), scope, _e(proposal.get("scope") or "")))
    parts.append(_details(anchors, "Preuves et limites du rapport", report.get("evidence")))
    actions = anchors("actions")
    later = _open(anchors("button"), "Plus tard", PATH, (("vue", "catalogue"),))
    prepare = _unwired(anchors("primary"), "Faire préparer ma sélection", "pn-primary")
    parts.append('<div class="pn-actions" %s>%s%s%s</div>'
                 % (actions, later, prepare, _unwired_note("Faire préparer ma sélection")))
    return "".join(parts)


def _details(anchors, label, said):
    details, summary, text = anchors("details"), anchors("summary"), anchors("p")
    return "<details %s><summary %s>%s</summary><p %s>%s</p></details>" % (
        details, summary, _e(label), text, _e(said or "Contenu non fourni par la source."))


def _review_preparing(operation, projects, anchors):
    return ("<h2 %s>Préparation du travail</h2>"
            "<p %s>L’usine précise le périmètre, les critères et les limites des propositions choisies.</p>"
            "<p %s>Aucune réalisation commencée.</p>" % (anchors("h2"), anchors("p"), anchors("p")))


def _review_ready(operation, projects, anchors):
    work = operation.get("work") or {}
    title, subject, scope = anchors("h2"), anchors("h3"), anchors("p")
    preview, expected_title, expected, limits_title, limits = (anchors("change-preview"), anchors("strong"),
                                                               anchors("p"), anchors("strong"), anchors("p"))
    head = ('<h2 %s>Travail prêt à valider</h2><h3 %s>%s</h3><p %s>%s</p>'
            '<div class="pn-change-preview" %s><strong %s>Résultat attendu</strong><p %s>%s</p>'
            "<strong %s>Limites</strong><p %s>%s</p></div>"
            % (title, subject, _e(work.get("title") or ""), scope, _e(work.get("scope") or ""), preview,
               expected_title, expected, _e(work.get("expected") or ""), limits_title, limits,
               _e(work.get("limits") or "")))
    details = _details(anchors, "Travail précis et critères", work.get("criteria"))
    actions = anchors("actions")
    review = _unwired(anchors("button"), "Revoir la sélection")
    launch = _unwired(anchors("primary"), "Lancer les corrections", "pn-primary")
    return head + details + '<div class="pn-actions" %s>%s%s%s</div>' % (
        actions, review, launch, _unwired_note("Revoir la sélection", "Lancer les corrections"))


def _review_execution(operation, projects, anchors):
    return ("<h2 %s>Réalisation en cours</h2>"
            "<p %s>L’usine réalise et vérifie le travail validé. Le résultat reviendra pour ton jugement.</p>"
            % (anchors("h2"), anchors("p")))


def _review_delivered(operation, projects, anchors):
    return ("<h2 %s>Résultat prêt à juger</h2>"
            "<p %s>Les corrections sont terminées. Aucune acceptation ni fusion n’est déduite de leur fin.</p>"
            '<p class="pn-readonly-note" %s>Le parcours Essai / Avis validé s’appliquera au dossier de ce résultat.</p>'
            % (anchors("h2"), anchors("p"), anchors("readonly-note")))


REVIEW_PANELS = {
    "confirm": _review_confirm, "review": _review_under_way, "report": _review_report,
    "preparing": _review_preparing, "ready": _review_ready, "execution": _review_execution,
    "delivered": _review_delivered,
}


# The panels of the preparation of the next release, by step.

def _project_key(operation, projects):
    name = operation.get("project")
    return next((key for key, display in projects if display == name), None)


def _release_confirm(operation, projects, anchors):
    title, label, select = anchors("h2"), anchors("label"), anchors("select")
    options = _options(operation, projects, anchors)
    lead, preview, cost, actions = anchors("p"), anchors("change-preview"), anchors("p"), anchors("actions")
    back = _open(anchors("button"), "Retour aux rituels", PATH, (("vue", "catalogue"),))
    launch = _unwired(anchors("primary"), "Lancer la préparation", "pn-primary")
    return (
        '<h2 %s>Préparer le cadrage</h2><label %s>Projet<select %s>%s</select></label>'
        "<p %s>Relire les objectifs, les décisions, les résultats vérifiés et les dépendances connues. Proposer une "
        "cible de release et le jalon le plus utile pour avancer ou lever une incertitude.</p>"
        '<div class="pn-change-preview" %s>Tu pourras garder des questions ouvertes et modifier la proposition. '
        "Aucun périmètre figé, aucune réalisation lancée.<p %s>Utilise un agent et consomme des tokens. Coût non "
        "estimé ici.</p></div>"
        '<div class="pn-actions" %s>%s%s%s</div>'
    ) % (title, label, select, options, lead, preview, cost, actions, back, launch,
         _unwired_note("Lancer la préparation"))


def _release_under_way(operation, projects, anchors):
    return ("<h2 %s>Préparation en cours</h2>"
            "<p %s>Rapprochement des acquis, de la cible et des questions ouvertes. Le résultat sera une proposition "
            "à examiner.</p>" % (anchors("h2"), anchors("p")))


def _field(anchors, label, value, rows):
    holder, field = anchors("label"), anchors(anchor_slug(label))
    return '<label %s>%s<textarea aria-label="%s" rows="%d" %s>%s</textarea></label>' % (
        holder, _e(label), _e(label), rows, field, _e(value or ""))


def _release_report(operation, projects, anchors):
    framing = operation.get("framing") or {}
    parts = ['<h2 %s>Proposition à examiner</h2><p %s>Garde une cible provisoire et un prochain jalon précis. '
             "Les questions peuvent rester ouvertes.</p>" % (anchors("h2"), anchors("p")),
             _field(anchors, "Résultat attendu pour cette release", framing.get("expected"), 3)]
    columns, acquired_column, acquired_title = anchors("release-columns"), anchors("div"), anchors("h3")
    acquired = "".join('<p class="pn-ok" %s>✓ %s</p>' % (anchors("ok"), _e(line))
                       for line in framing.get("acquired") or []) or "<p>Aucun acquis vérifié.</p>"
    remaining_column, remaining_title = anchors("div"), anchors("h3")
    remaining = "".join("<p %s>○ %s</p>" % (anchors("p"), _e(line))
                        for line in framing.get("remaining") or []) or "<p>Aucun critère restant connu.</p>"
    parts.append('<div class="pn-release-columns" %s><div %s><h3 %s>Acquis à conserver</h3>%s</div>'
                 '<div %s><h3 %s>Critères restant à satisfaire</h3>%s</div></div>'
                 % (columns, acquired_column, acquired_title, acquired, remaining_column, remaining_title, remaining))
    if framing.get("question"):
        decision, legend = anchors("release-decision"), anchors("legend")
        chosen = framing.get("decision") or "open"
        radios = "".join('<label %s><input type="radio" name="release-decision" value="%s"%s %s> %s</label>'
                         % (anchors("label"), value, " checked" if value == chosen else "", anchors("input"), label)
                         for value, label in DECISIONS)
        parts.append('<fieldset class="pn-release-decision" %s><legend %s>%s</legend>%s</fieldset>'
                     % (decision, legend, _e(framing["question"]), radios))
    parts.append(_field(anchors, "Prochain jalon", framing.get("milestone"), 2))
    parts.append(_field(anchors, "Comment vérifier ce jalon", framing.get("check"), 2))
    estimate = framing.get("estimate") or {}
    notice, estimate_title, estimate_detail = anchors("release-notice"), anchors("strong"), anchors("p")
    parts.append('<div class="pn-release-notice" %s><strong %s>%s</strong><p %s>%s</p></div>'
                 % (notice, estimate_title, _e(estimate.get("title") or "Estimation non disponible"), estimate_detail,
                    _e(estimate.get("detail") or "Aucune donnée comparable fournie par la source.")))
    parts.append(_details(anchors, "Sources et inconnues", framing.get("sources")))
    actions = anchors("actions")
    key = _project_key(operation, projects)
    back = (_open(anchors("button"), "Revenir au projet sans conserver", project_page_url(key)) if key
            else _open(anchors("button"), "Revenir au projet sans conserver", PATH, (("vue", "catalogue"),)))
    keep = _unwired(anchors("primary"), "Conserver ce cadrage", "pn-primary")
    parts.append('<div class="pn-actions" %s>%s%s%s</div>' % (actions, back, keep, _unwired_note("Conserver ce cadrage")))
    parts.append('<p id="release-error" role="alert" %s></p>' % anchors("release-error"))
    return "".join(parts)


def _release_saved(operation, projects, anchors):
    project = operation.get("project") or ""
    key = _project_key(operation, projects)
    title, kept, next_step, actions = anchors("h2"), anchors("p"), anchors("p"), anchors("actions")
    see = _open(anchors("primary"), "Voir le projet", project_page_url(key), css="pn-primary") if key else \
        _unwired(anchors("primary"), "Voir le projet", "pn-primary")
    again = _open(anchors("link"), "Revoir le cadrage", PATH, (("rituel", RELEASE),) + ((("projet", key),) if key else ()),
                  "pn-link")
    return (
        "<h2 %s>Cadrage conservé</h2>"
        "<p %s>La cible révisable, le prochain jalon et les décisions ouvertes sont visibles dans le projet %s.</p>"
        "<p %s>Le jalon reste à préparer avant toute réalisation. Conserver le cadrage n’approuve pas une Spec ni un "
        "lancement de travaux.</p>"
        '<div class="pn-actions" %s>%s%s</div>'
    ) % (title, kept, _e(project), next_step, actions, see, again)


RELEASE_PANELS = {"confirm": _release_confirm, "review": _release_under_way, "report": _release_report,
                  "saved": _release_saved}


# The reference's type and spacing, on the tokens of the shell. Its
# defects are not copied: a text on the accent is --pn-accent-ink (white in
# the light theme, where the reference's dark ink is under 4.5:1), a muted
# text is --pn-muted-text, the box of a field or a button --pn-control-line
# (3:1 at least where --line is not), and every field shows its focus.
CSS = """
.pn-rituals h1{font-size:27px;margin:0 0 20px}
.pn-rituals h2{font-size:19px;margin:0 0 16px;overflow-wrap:anywhere}
.pn-rituals h3{font-size:16px;margin:16px 0;overflow-wrap:anywhere}
.pn-rituals p{line-height:1.5;margin:0 0 12px;overflow-wrap:anywhere}
.pn-rituals small{font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.pn-rituals strong{overflow-wrap:anywhere}
.pn-rituals :is(button,select,textarea,input){font:inherit;color:inherit}
.pn-rituals button{color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:10px 14px;cursor:pointer}
.pn-rituals button:hover{border-color:var(--accent)}
.pn-rituals button:disabled{opacity:.5;cursor:not-allowed}
.pn-rituals button.pn-primary{background:var(--accent);border-color:var(--accent);color:var(--pn-accent-ink)}
.pn-rituals button.pn-link{padding:0;border:0;border-radius:4px;background:none;color:var(--accent)}
.pn-rituals button.pn-link:hover{text-decoration:underline}
.pn-rituals :is(select,textarea,input):focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.pn-rituals .pn-page-lead{color:var(--pn-muted-text);margin:-10px 0 24px;line-height:1.6}
.pn-ritual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.pn-ritual-grid>*{min-width:0}
.pn-ritual-card{display:flex;flex-direction:column;padding:24px;margin:0}
.pn-ritual-card h2{margin:12px 0}
.pn-ritual-card p{color:var(--pn-muted-text);font-size:14px;flex:1}
.pn-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}
.pn-rituals .pn-unwired{flex-basis:100%;margin:0;font-size:13px;color:var(--pn-muted-text)}
.pn-crumb{display:flex;align-items:center;gap:12px;margin-bottom:24px}
.pn-ritual-path{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}
.pn-ritual-path span{font-size:12px;border:1px solid var(--line);border-radius:20px;padding:8px 12px}
.pn-ritual-path .pn-current{border-color:var(--accent);color:var(--accent)}
.pn-rituals label{display:block;margin:12px 0;overflow-wrap:anywhere}
.pn-rituals select{display:block;margin-top:8px;max-width:100%;background:var(--bg);color:var(--ink);
  border:1px solid var(--pn-control-line);padding:10px;border-radius:6px}
.pn-change-preview{border-left:3px solid var(--accent);padding:12px 15px;margin:20px 0;background:var(--bg);
  font-size:14px;overflow-wrap:anywhere}
.pn-change-preview p{margin:8px 0 0}
.pn-readonly-note{font-size:12px;color:var(--pn-muted-text)}
.pn-rituals .pn-proposal-choice{display:flex;gap:15px;align-items:flex-start;border:1px solid var(--line);
  border-radius:8px;padding:16px;margin:12px 0}
.pn-proposal-choice>span{min-width:0}
.pn-rituals input[type=checkbox],.pn-rituals input[type=radio]{border:0;margin:2px 0 0;flex-shrink:0;
  accent-color:var(--accent)}
.pn-proposal-choice input{width:18px;height:18px}
.pn-proposal-choice strong{display:block;margin-bottom:5px}
.pn-proposal-choice small{display:block;line-height:1.6}
.pn-rituals details{border-top:1px solid var(--line);padding:16px 0}
.pn-rituals summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-rituals details p{font-size:14px;margin:10px 0 0}
.pn-rituals textarea{display:block;width:100%;box-sizing:border-box;margin:8px 0 20px;padding:12px;
  background:var(--bg);color:var(--ink);border:1px solid var(--pn-control-line);border-radius:8px;resize:vertical}
.pn-release-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px;margin:22px 0}
.pn-release-columns>*{min-width:0}
.pn-release-columns h3{margin:0 0 12px}
.pn-ok{color:var(--ok)}
.pn-release-decision{border:1px solid var(--line);border-radius:10px;margin:22px 0;padding:16px;min-width:0}
.pn-release-decision legend{overflow-wrap:anywhere;max-width:100%}
.pn-release-decision label{display:flex;align-items:center;gap:8px;margin:12px 0}
.pn-release-notice{border-left:3px solid var(--warn);padding:14px 18px;margin:20px 0;background:var(--surface)}
.pn-release-notice p{margin:8px 0 0}
@media (max-width:900px){
  .pn-ritual-grid,.pn-release-columns{grid-template-columns:minmax(0,1fr)}
  .pn-release-columns{gap:16px}
}
@media (max-width:800px){.pn-rituals h1{font-size:24px}.pn-ritual-card{padding:18px}}
"""
