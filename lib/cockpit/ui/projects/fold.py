"""The page of a project, Prototype Fold of the reference « Projet, release
et historique » (E, af-8rbceu; Spec af-fgcw0d, user stories 46, 103, 124,
152 to 156 and 175; Validated Prototype prototype/cockpit-b-zones-20261012
at 632deea, prototypes/c01-complete/frozen-panorama-project).

    main = render_project_fold(view)    # a function of the page's anchors

From the top, as the reference draws them and numbers their anchors: the
way back to « Projets », the name of the project and its state, three
counts, « Prochaine release » read from the release plan of the project
(:mod:`cockpit.projects.release`), the current chantier and the roadmap,
the last change and the resources of the project. Below them, what the
page of the project already showed: its chantiers by stage, its work
outside a chantier and its history (``view["below"]``, HTML).

``view`` is plain data the server assembles (:func:`project_view`); nothing
here reads a source. A part whose source is not read says so, and why --
never a value of example, never a progress deduced: no global percentage,
no date of delivery.
"""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from cockpit.projects.release import estimate_of
from cockpit.projects.roadmap import current_step, roadmap_rows
from cockpit.ui.panorama.shell import open_button
from cockpit.ui.projects.panorama import project_counts, project_runs

PARIS = ZoneInfo("Europe/Paris")
NO_PROGRESS = "Aucun avancement déduit."


def _e(value):
    return html.escape(str(value), quote=True)


def _paris(at):
    """« 19/10/2026 à 14:05 » for an ISO instant, or None."""
    try:
        moment = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


def _release_missing(release, repo):
    """Why the release of the project is not known: what lacks, and where."""
    state = release.get("state")
    path = release.get("path", "")
    if state == "absent":
        return ("Cadrage de release et preuves non collectés. %s" % NO_PROGRESS,
                "Aucun cadrage de release dans le dépôt %s : le fichier %s n’existe pas. Ni cible, ni acquis, "
                "ni estimation à montrer." % (repo, path))
    if state == "unreadable":
        what = ("Le fichier de cadrage de release %s du dépôt %s" % (path, repo) if path
                else "Le cadrage de release du dépôt %s" % repo)
        return ("Cadrage de release illisible. %s" % NO_PROGRESS,
                "%s ne se lit pas : %s" % (what, release.get("reason", "")))
    if state == "undeclared":
        return ("Cadrage de release et preuves non collectés. %s" % NO_PROGRESS,
                "Ce projet ne déclare aucun dépôt de connaissance : aucun cadrage de release ne peut y être lu.")
    if state == "reading":
        return ("Lecture du dépôt du projet en cours. %s" % NO_PROGRESS,
                "Le cadrage de release s’affichera une fois le dépôt %s lu." % repo if repo else "")
    return ("Cadrage de release inconnu. %s" % NO_PROGRESS,
            "Les dépôts des projets ne sont pas lus par ce cockpit : le cadrage de release ne peut pas être lu.")


DECISION_TITLES = {"open": "Décision ouverte", "deferred": "Décision reportée", "included": "Périmètre élargi"}


def _release(anchors, release, repo):
    """« Prochaine release »: the release plan read, or why there is none."""
    panel = anchors("panel")
    plan = release.get("plan") if release.get("state") == "read" else None
    if plan is None:
        said, why = _release_missing(release, repo)
        return ('<section class="pn-panel pf-release" %s><div class="pf-heading"><h2 %s>Prochaine release</h2></div>'
                '<p %s>%s</p><p class="pf-why" %s>%s</p></section>'
                % (panel, anchors("h2"), anchors("p"), _e(said), anchors("p"), _e(why)))
    heading = '<div class="pf-heading"><h2 %s>Prochaine release</h2><span class="pf-tag" %s>%s</span></div>' % (
        anchors("h2"), anchors("tag"), _e("Cible révisable · %s" % plan["status"] if plan["status"] else "Cible révisable"))
    goal = '<p class="pf-goal" %s>%s</p>' % (anchors("release-goal"), _e(plan["target"]))
    columns = anchors("release-columns")
    # Each proof is named by its gain: « Voir la preuve » alone, repeated,
    # would not tell which gain a control opens.
    gains = "".join(
        '<div class="pf-criterion" %s><strong %s>%s</strong><details %s><summary %s aria-label="%s">Voir la preuve'
        '</summary><p %s>%s</p></details></div>'
        % (anchors("release-criterion"), anchors("strong"), _e(g["title"]), anchors("details"), anchors("summary"),
           _e("Voir la preuve : %s" % g["title"]), anchors("p"), _e(g["proof"])) for g in plan["gains"])
    gained = ('<div %s><h3 %s><span class="pf-ok" %s>✓</span> Acquis vérifiés <small %s>%d</small></h3>%s</div>'
              % (anchors("div"), anchors("h3"), anchors("ok"), anchors("small"), len(plan["gains"]), gains))
    remaining = "".join('<p class="pf-criterion" %s>○ %s</p>' % (anchors("release-criterion"), _e(title))
                        for title in plan["remaining"])
    remains = '<div %s><h3 %s>Reste connu <small %s>%d</small></h3>%s</div>' % (
        anchors("div"), anchors("h3"), anchors("small"), len(plan["remaining"]), remaining)
    decisions = "".join(
        '<div class="pf-notice" %s><strong %s>%s</strong><p %s>%s</p></div>'
        % (anchors("release-notice"), anchors("strong"), _e(DECISION_TITLES[d["state"]]), anchors("p"),
           _e(d["note"] or d["question"])) for d in plan["decisions"])
    milestone = plan["milestone"]
    if milestone:
        state = '<span class="pf-tag" %s>%s</span>' % (anchors("tag"), _e(milestone["state"])) if milestone["state"] else ""
        next_step = ('<div class="pf-milestone" %s><small %s>PROCHAIN JALON</small><h3 %s>%s</h3><p %s>%s</p>%s</div>'
                     % (anchors("release-milestone"), anchors("small"), anchors("h3"), _e(milestone["title"]),
                        anchors("p"), _e(milestone["check"]), state))
    else:
        next_step = ('<div class="pf-milestone" %s><small %s>PROCHAIN JALON</small><p %s>Aucun jalon écrit dans le '
                     'cadrage de release.</p></div>' % (anchors("release-milestone"), anchors("small"), anchors("p")))
    estimate = estimate_of(plan)
    if estimate["shown"]:
        estimated = ('<div %s><strong %s>Fourchette indicative · %s</strong><p %s>%s</p><details %s>'
                     '<summary %s>Hypothèses et données</summary><p %s>%d résultats comparables · calculée le %s '
                     '(Paris).</p><p %s>%s</p></details></div>'
                     % (anchors("div"), anchors("strong"), _e(estimate["range"]), anchors("p"), _e(estimate["conditions"]),
                        anchors("details"), anchors("summary"), anchors("p"), estimate["comparables"],
                        _e(estimate["computed"]), anchors("p"), _e(estimate["hypotheses"])))
    else:
        estimated = '<div %s><strong %s>Estimation non disponible</strong><p %s>%s</p></div>' % (
            anchors("div"), anchors("strong"), anchors("p"), _e(estimate["reason"]))
    history = "".join('<p %s>• %s</p>' % (anchors("p"), _e(change)) for change in plan["history"]) or \
        '<p %s>Aucun changement de cible écrit.</p>' % anchors("p")
    evolution = ('<details %s><summary %s>Évolution de la cible</summary>%s<small %s>Les changements de périmètre sont '
                 'séparés des acquis. Aucun pourcentage global calculé.</small></details>'
                 % (anchors("details"), anchors("summary"), history, anchors("small")))
    second = anchors("release-columns")
    actions = '<div class="pf-actions" %s><a class="pf-primary" href="/rituels" %s>Préparer la prochaine release</a></div>' % (
        anchors("actions"), anchors("primary"))
    return ('<section class="pn-panel pf-release" %s>%s%s<div class="pf-columns" %s>%s%s</div>%s'
            '<div class="pf-columns" %s>%s%s</div>%s%s</section>'
            % (panel, heading, goal, columns, gained, remains, decisions, second, next_step, estimated, evolution,
               actions))


def _current(anchors, view):
    """« Chantier actuel »: the chantier under way, or why none is said."""
    panel = anchors("panel")
    head = '<h2 class="pf-label"><small %s>CHANTIER ACTUEL</small></h2>' % anchors("small")
    state = view["chantiers_state"]
    if state == "loading":
        body = '<p %s>Lecture des chantiers en cours.</p>' % anchors("p")
    elif state == "failed":
        body = '<p %s>Lecture des chantiers impossible : le suivi des tâches ne répond pas.</p>' % anchors("p")
    elif view["current"] is None:
        body = '<p %s>Aucun chantier en cours.</p>' % anchors("p")
    else:
        current = view["current"]
        run = ('<div class="pf-actions" %s>%s</div>' % (anchors("actions"), open_button(current["run"], "Voir le run",
                                                                                         anchors("button")))
               if current.get("run") else "")
        body = '<h2 %s>%s</h2><p %s>%s</p>%s' % (anchors("h2"), _e(current["title"]), anchors("p"), _e(current["line"]), run)
    return '<section class="pn-panel" %s>%s%s</section>' % (panel, head, body)


def _roadmap(anchors, roadmap, repo, milestone):
    """« Roadmap »: the steps of the structured roadmap, each flagged when
    the tracker contradicts it, and the date of its last change."""
    panel = anchors("panel")
    head = '<h2 class="pf-label"><small %s>ROADMAP</small></h2>' % anchors("small")
    if roadmap["state"] != "read":
        said = {
            "undeclared": "Ce projet ne déclare aucune roadmap structurée : aucune étape à montrer.",
            "reading": "Lecture de la roadmap en cours.",
            "absent": "Aucune roadmap dans le dépôt %s : le fichier %s n’existe pas." % (repo, roadmap.get("path")),
            "unreadable": "Roadmap illisible : le fichier %s du dépôt %s ne se lit pas : %s" % (
                roadmap.get("path"), repo, roadmap.get("reason", "")),
            "unknown": "Roadmap inconnue : son dépôt %s ne se lit pas." % repo,
        }.get(roadmap["state"], "Les dépôts des projets ne sont pas lus par ce cockpit : roadmap inconnue.")
        return '<section class="pn-panel" %s>%s<p %s>%s</p></section>' % (panel, head, anchors("p"), _e(said))
    current = current_step(roadmap["rows"])
    title = '<h2 %s>%s</h2>' % (anchors("h2"), _e(current["title"])) if current else ""
    rows = "".join(
        '<div class="pf-row%s" %s><span %s>%s</span><span class="pf-status%s" %s>%s%s</span></div>'
        % (" pf-flagged" if row["flag"] else "", anchors("row"), anchors("span"), _e(row["title"]),
           " pf-done" if row["acquired"] else "", anchors("ok" if row["acquired"] else "span"),
           _e(row["label"]), (" · " + _e(row["flag"])) if row["flag"] else "") for row in roadmap["rows"])
    changed = _paris(roadmap.get("changed_at"))
    source = "Source : %s, %s" % (repo, roadmap["path"])
    note = "%s · modifiée le %s (Paris)." % (source, changed) if changed else "%s · date de modification inconnue." % source
    proposed = ('<p class="pf-note" %s>Prochain jalon proposé : %s.</p>' % (anchors("readonly-note"), _e(milestone))
                if milestone else "")
    return '<section class="pn-panel" %s>%s%s%s<p class="pf-note" %s>%s</p>%s</section>' % (
        panel, head, title, rows, anchors("p"), _e(note), proposed)


def _last_change(anchors, view):
    panel = anchors("panel")
    last = view["last_change"]
    if last is None:
        said = ("Derniers changements inconnus tant que les chantiers ne sont pas lus."
                if view["chantiers_state"] != "read" else "Aucun chantier terminé pour ce projet.")
        body = '<p %s>%s</p>' % (anchors("p"), _e(said))
    else:
        body = '<p %s><span class="pf-ok" %s>●</span> %s</p><small %s>%s</small>' % (
            anchors("p"), anchors("ok"), _e(last["title"]), anchors("small"), _e(last["issue"]))
    link = '<div class="pf-link" %s>%s</div>' % (anchors("event-link"),
                                                 open_button("/journal", "Voir le journal", anchors("link"), "pf-linkbtn"))
    return '<section class="pn-panel" %s><h2 %s>Derniers changements</h2>%s%s</section>' % (
        panel, anchors("h2"), body, link)


def _resources(anchors, view, release, repo):
    panel = anchors("panel")
    plan = release.get("plan") if release.get("state") == "read" else None
    goal = _e(plan["target"]) if plan else "Aucun cadrage de release lu : objectif et périmètre inconnus."
    sources = ("Chantiers et historique : suivi des tâches. Roadmap et cadrage de release : %s. "
               "Runs : livraisons de ce projet. Une PR fusionnée ne compte pas comme un résultat accepté." % (
                   "dépôt %s" % repo if repo else "aucun dépôt déclaré"))
    return ('<section class="pn-panel" %s><h2 %s>Ressources du projet</h2>'
            '<details %s><summary %s>Objectif et périmètre</summary><p %s>%s</p></details>'
            '<details %s><summary %s>Sources et mesures</summary><p %s>%s</p></details></section>'
            % (panel, anchors("h2"), anchors("details"), anchors("summary"), anchors("p"), goal, anchors("details"),
               anchors("summary"), anchors("p"), _e(sources)))


def _knowledge(depots, descriptor):
    """The release plan and the roadmap of the project, as the depots source
    holds them: ``(release, roadmap)``."""
    project_id = descriptor["project_id"]
    if not descriptor.get("knowledge_repo") or not descriptor.get("roadmap_path"):
        return {"state": "undeclared"}, {"state": "undeclared"}
    if depots is None:
        return {"state": "not_read"}, {"state": "not_read"}
    value = depots.get("value")
    if value is None:
        state = "reading" if depots.get("failed_at") is None else "unknown"
        return ({"state": "reading"} if state == "reading" else
                {"state": "unreadable", "path": "", "reason": "le dépôt ne répond pas"}), {"state": state}
    release = (value.get("releases") or {}).get(project_id) or {"state": "not_read"}
    read = (value.get("roadmaps") or {}).get(project_id) or {}
    if not read.get("ok"):
        # Which file lacks or does not read, as the depots source says; a
        # read of an earlier cockpit says neither: its repository is unknown.
        state = read.get("state") if read.get("state") in ("absent", "unreadable") else "unknown"
        return release, {"state": state, "path": read.get("path") or descriptor["roadmap_path"],
                         "reason": read.get("reason", "")}
    return release, {"state": "read", "steps": (value.get("steps") or {}).get(project_id) or [],
                     "changed_at": read.get("changed_at"), "path": descriptor["roadmap_path"]}


def project_view(descriptor, project, chantiers_state, depots, roadmap_chantiers, runs, now, historique, below):
    """The plain data :func:`render_project_fold` draws. ``descriptor``: the
    project as declared; ``project``: its chantiers as read
    (:class:`cockpit.projects.model.Project`), None while they are not
    (``chantiers_state``: read, loading or failed); ``depots``: the row of
    the depots source, or None when this cockpit reads no repository;
    ``roadmap_chantiers``: ``{step id: [{"closed", "merged", "accepted"}]}``;
    ``historique``: the chantiers ended, most recent last; ``below``: HTML
    drawn under the parts of the reference."""
    release, roadmap = _knowledge(depots, descriptor)
    if roadmap["state"] == "read":
        # Chantiers not read: the tracker says nothing of the steps (R3).
        roadmap["rows"] = roadmap_rows(roadmap["steps"], (roadmap_chantiers or {}) if project is not None else None)
    own = project_runs(runs, descriptor["project_id"])
    if project is None:
        metrics = [("—", "Décisions attendues · inconnu"), ("—", "Chantiers ouverts · inconnu"),
                   ("—", "Runs fusionnés · 7 jours · inconnu")]
        badge, current = ("", "État inconnu"), None
    else:
        waiting, active, merged, live = project_counts(project, own, now)
        metrics = [(waiting, "Décisions attendues"), (active, "Chantiers ouverts"), (merged, "Runs fusionnés · 7 jours")]
        badge = ("wait", "À toi de jouer · %d" % waiting) if waiting else (("live", "En cours") if live else ("", "Calme"))
        chantier = next((c for c in project.chantiers if not c.termine and not c.abandonne), None)
        current = None
        if chantier is not None:
            line = "À toi de jouer" if chantier.etat == "a_toi_de_jouer" else "Aucune décision attendue"
            run = next((r for r in own if r.get("href")), None)
            current = {"title": chantier.titre, "line": "%s · %s" % (chantier.detail, line) if chantier.detail else line,
                       "run": run["href"] if run else None}
    last = (historique or [None])[-1]
    return {
        "project_id": descriptor["project_id"], "name": descriptor.get("display_name") or descriptor["project_id"],
        "repo": descriptor.get("knowledge_repo") or "", "badge": badge, "metrics": metrics,
        "chantiers_state": chantiers_state, "current": current, "release": release, "roadmap": roadmap,
        "last_change": {"title": last.titre, "issue": last.detail or last.stage} if last else None,
        "below": below,
    }


def render_project_fold(view):
    """The main part of /projet/<id>: a function of the page's anchors (see
    :func:`cockpit.ui.panorama.shell.render_shell`). ``view``: see
    :func:`project_view`."""

    def draw(anchors):
        repo = view["repo"]
        release = view["release"]
        plan = release.get("plan") if release.get("state") == "read" else None
        crumb = '<div class="pf-crumb" %s>%s</div>' % (
            anchors("crumb"), open_button("/projets", "← Projets", anchors("link"), "pf-linkbtn"))
        tone, label = view["badge"]
        hero = ('<div class="pf-hero" %s><div %s><h1 %s>%s</h1></div><span class="pf-tag pj-badge %s" %s>%s</span></div>'
                % (anchors("project-hero"), anchors("div"), anchors("h1"), _e(view["name"]), tone, anchors("tag"),
                   _e(label)))
        kpis = "".join('<div %s><strong %s>%s</strong><small %s>%s</small></div>'
                       % (anchors("div"), anchors("strong"), _e(value), anchors("small"), _e(caption))
                       for value, caption in view["metrics"])
        metrics = '<div class="pf-kpis" %s>%s</div>' % (anchors("compact-kpis"), kpis)
        release_html = _release(anchors, release, repo)
        grid = anchors("section-grid")
        upper = _current(anchors, view) + _roadmap(anchors, view["roadmap"], repo,
                                                     plan["milestone"]["title"] if plan and plan["milestone"] else None)
        grid2 = anchors("section-grid")
        lower = _last_change(anchors, view) + _resources(anchors, view, release, repo)
        return ('%s%s%s%s<div class="pf-grid" %s>%s</div><div class="pf-grid" %s>%s</div>%s'
                % (crumb, hero, metrics, release_html, grid, upper, grid2, lower, view["below"]))

    return draw


CSS = """
.pf-crumb{margin-bottom:24px}
.pf-linkbtn{font:inherit;padding:0;border:0;background:none;color:var(--accent);cursor:pointer;text-decoration:underline;
  text-underline-offset:3px}
.pf-hero{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:6px}
.pf-hero h1{font-size:27px;margin:0;overflow-wrap:anywhere}
.pf-tag{border:1px solid var(--line);border-radius:24px;padding:4px 9px;font-size:12px;white-space:nowrap}
.pf-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0}
.pf-kpis>div{padding:16px;border:1px solid var(--line);border-radius:8px;min-width:0}
.pf-kpis strong{font-size:24px;display:block;margin-bottom:6px}
.pf-kpis small,.pf-release small,.pf-note,.pf-why{color:var(--pn-muted-text)}
.pn-main small{font-size:12px;overflow-wrap:anywhere}
/* The label of a section, small as the reference draws it, and its heading. */
.pn-panel h2.pf-label,.pf-grid h2.pf-label{font:inherit;color:inherit;margin:0}
.pf-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.pf-heading h2{margin:0}
.pf-goal{font-size:21px;max-width:850px;margin:12px 0 0!important}
.pf-why{margin-top:8px!important}
.pf-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px;margin:22px 0}
.pf-columns>*{min-width:0}
.pf-columns h3{font-size:16px;margin:0 0 4px}
.pf-criterion{border-bottom:1px solid var(--line);padding:12px 0;margin:0}
.pf-criterion strong{font-size:14px;overflow-wrap:anywhere}
.pf-ok,.pf-done{color:var(--ok)}
.pf-notice{border-left:3px solid var(--warn);padding:14px 18px;margin:20px 0;background:var(--surface)}
.pf-milestone{border-left:3px solid var(--accent);padding-left:18px}
.pf-milestone h3{margin:8px 0}
.pf-milestone .pf-tag{display:inline-block;margin-top:10px;white-space:normal}
.pf-release details,.pf-grid details{border-top:1px solid var(--line);padding:16px 0}
.pf-release details p,.pf-grid details p{font-size:14px;margin-top:8px}
.pf-release summary,.pf-grid summary{cursor:pointer;color:var(--pn-muted-text)}
.pf-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}
.pf-primary{display:inline-block;background:var(--accent);color:var(--pn-accent-ink);border-radius:8px;padding:10px 14px;
  text-decoration:none;font-weight:600}
.pf-actions button{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:8px 14px;cursor:pointer}
.pf-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.pf-grid>*{min-width:0}
.pf-grid h2{font-size:19px;margin:12px 0}
.pf-row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:14px 0;
  border-bottom:1px solid var(--line)}
.pf-row>span:first-child{min-width:0;overflow-wrap:anywhere}
.pf-row .pf-status{text-align:right;flex:0 1 45%}
.pf-flagged .pf-status{color:var(--pn-warn-text);font-weight:600}
.pf-note{font-size:12px;margin-top:12px!important}
.pf-link{margin-top:10px}
/* What the page of the project already drew, below the parts of the
   reference: the box of « Revérifier » and the heads of the stages, read
   at 3:1 and 4.5:1 in both themes (Testing Decisions 5). */
.cockpit-pp-fresh{margin:8px 0 4px}
.cockpit-pp-fresh .recheck{border-color:var(--pn-control-line);color:var(--ink);cursor:pointer}
.cockpit-project-page .v1 .bh{color:var(--pn-muted-text)}
.pn-main .cockpit-projects[data-state="unknown"] .unknown{color:var(--pn-warn-text)}
@media (max-width:800px){
  .pf-kpis{grid-template-columns:1fr 1fr}
  .pf-columns{grid-template-columns:minmax(0,1fr);gap:16px}
  .pf-goal{font-size:18px}
  .pf-grid{grid-template-columns:minmax(0,1fr)}
  .pf-row{flex-direction:column;gap:6px}
  .pf-row .pf-status{text-align:left}
}
"""
