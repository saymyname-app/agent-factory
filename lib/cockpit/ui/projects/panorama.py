"""The destination Projets of Panorama: a card per declared project, then
the head of a project's page -- its counts and its last runs -- above the
chantiers, actions and history the project page already draws.

It follows the Projets reference (prototypes/c01-complete/frozen-panorama-
project at 632deea) for what the cockpit reads for real; the release target,
its estimate and the roadmap of the reference have no source yet and are
left out rather than drawn with example values.

Intent (Benjamin, his words, 2026-10-19 19:42 Paris): « enchaîne sur la
page suivante. »
Mechanism (agent interpretation): Projets, next in the navigation after
Vue d'ensemble, Runs and Usine; built directly, outside the paused convoy.
"""
import html

from cockpit.runs.derive import DONE, WAIT
from cockpit.ui.projects.project_page import project_page_url
from cockpit.ui.runs.page import run_card

WEEK_SECONDS = 7 * 86400


def _e(value):
    return html.escape(str(value), quote=True)


def project_runs(runs, project_id):
    """The runs of a project: those dispatched to its rig."""
    return [run for run in runs or [] if run.get("rig") == project_id]


def project_counts(project, runs, now):
    """(waiting chantiers, active chantiers, runs merged in 7 days, runs in
    progress) of a project."""
    chantiers = [c for c in project.chantiers if not c.termine and not c.abandonne]
    waiting = [c for c in chantiers if c.etat == "a_toi_de_jouer"]
    merged = [r for r in runs if r["status"] == "Fusionné" and r["end"] >= now - WEEK_SECONDS]
    live = [r for r in runs if r["state"] != DONE]
    return len(waiting), len(chantiers), len(merged), len(live)


def _badge(waiting, live):
    if waiting:
        return "wait", "À toi de jouer · %d" % waiting
    if live:
        return "live", "En cours"
    return "", "Calme"


def render_projects_list(projects, runs, now, checked=None):
    """Main part of /projets: a card per declared project."""
    cards = []
    for project in projects:
        own = project_runs(runs, project.project_id)
        waiting, active, merged, live = project_counts(project, own, now)
        tone, label = _badge(waiting, live)
        current = next((c for c in project.chantiers if not c.termine and not c.abandonne and c.etat != "a_toi_de_jouer"),
                       None)
        last = own[0] if own else None
        cards.append(
            '<article class="pj-card"><div class="pj-top"><span>%s</span><span class="pj-badge %s">%s</span></div>'
            '<h2>%s</h2><p>%s</p><dl class="pj-nums"><div><dt>Chantiers ouverts</dt><dd>%d</dd></div>'
            '<div><dt>Runs fusionnés · 7 j</dt><dd>%d</dd></div><div><dt>Runs ouverts</dt><dd>%d</dd></div></dl>'
            '<div class="pj-foot"><p class="pj-last">%s</p><a href="%s">Page projet</a></div></article>'
            % (_e(project.project_id), tone, _e(label), _e(project.display_name),
               _e("Chantier actuel : %s" % current.titre if current else "Aucun chantier en cours"),
               active, merged, live,
               _e("Dernier run : %s · %s" % (last["ticket"], last["status"]) if last else "Aucun run lu pour ce projet"),
               _e(project_page_url(project.project_id))))
    when = " · vérifié à %s (Paris)" % _e(checked) if checked else ""
    body = '<div class="pj-grid">%s</div>' % "".join(cards) if cards else \
        '<section class="pn-panel"><p>Aucun projet déclaré.</p></section>'
    return ('<div class="pn-head"><h1>Projets</h1><p class="pj-sub">Les projets déclarés à l’usine%s.</p></div>%s'
            % (when, body))


def render_project_head(project, runs, now):
    """The head of /projet/<id>: back link, name, counts, last runs."""
    own = project_runs(runs, project.project_id)
    waiting, active, merged, live = project_counts(project, own, now)
    tone, label = _badge(waiting, live)
    metrics = "".join('<div class="pj-metric"><strong>%d</strong><span>%s</span></div>' % (n, _e(t)) for n, t in (
        (waiting, "Décisions attendues"), (active, "Chantiers ouverts"), (merged, "Runs fusionnés · 7 jours"),
        (live, "Runs ouverts")))
    last = own[:3]
    runs_html = ('<div class="pj-runs">%s</div>' % "".join(run_card(run) for run in last) if last
                 else "<p>Aucun run lu pour ce projet.</p>")
    return ('<a class="pj-back" href="/projets">← Projets</a><div class="pj-title"><h1>%s</h1>'
            '<span class="pj-badge pill %s">%s</span></div><div class="pj-metrics">%s</div>'
            '<section class="pn-panel"><div class="pj-panel-head"><h2>Derniers runs</h2><a href="/runs">Tout voir</a></div>%s</section>'
            % (_e(project.display_name), tone, _e(label), metrics, runs_html))


CSS = """
.pj-sub{margin:0 0 20px;color:var(--pn-muted-text)}
.pj-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.pj-card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:20px;color:inherit;text-decoration:none}
.pj-card:hover{border-color:var(--accent)}
.pj-card h2{margin:10px 0 6px;font-size:21px}
.pj-card p{margin:0;color:var(--pn-muted-text);font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.pj-top{display:flex;justify-content:space-between;gap:10px;font-size:12px;color:var(--pn-muted-text)}
.pj-badge{color:var(--ok);white-space:nowrap}.pj-badge.live{color:var(--accent)}.pj-badge.wait{color:var(--pn-warn-text)}
.pj-badge.pill{border:1px solid var(--line);border-radius:999px;padding:5px 10px;font-size:12px}
.pj-nums{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}
.pj-nums dt{font-size:12px;color:var(--pn-muted-text)}.pj-nums dd{margin:4px 0 0;font-size:22px;font-weight:700}
.pj-last{font-size:13px!important}
.pj-foot{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.pj-foot a{color:var(--accent);white-space:nowrap}
.pj-back{display:inline-block;margin-bottom:14px;color:var(--accent);text-decoration:none}
.pj-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px}
.pj-title h1{font-size:27px;margin:0}
.pj-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}
.pj-metric{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px}
.pj-metric strong{display:block;font-size:24px}.pj-metric span{font-size:12px;color:var(--pn-muted-text)}
.pj-panel-head{display:flex;justify-content:space-between;align-items:baseline}
.pj-panel-head a{color:var(--accent)}
.pj-runs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
@media (max-width:1100px){.pj-runs{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.pj-runs{grid-template-columns:1fr}}
@media (max-width:800px){.pj-grid,.pj-metrics{grid-template-columns:1fr 1fr}.pj-nums{grid-template-columns:1fr 1fr 1fr}}
"""
