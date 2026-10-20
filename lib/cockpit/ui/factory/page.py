"""The destination Usine of Panorama (G1, af-wrxrmg, Prototype Fold of the
reference prototypes/c01-complete/frozen-panorama-factory at 632deea; Spec
af-fgcw0d, user stories 63, 65, 124, 160, 161, 162 and 175): the machine the
factory runs on, the connections the cockpit reads, the roles of the
delivery flow as the Factory's files configure them, beside what is observed
of them, and the zones that change the factory, still unavailable.

    render_factory_page(view) -> a function of the anchors of the page

``view`` holds what the page shows, already read: ``machine``,
``connections`` and ``agents``, the last check of each section
(cockpit.factory.checks: ``{"at", "value"}``); ``live``, the read model now;
``selected``, the role whose detail is open; ``notify_configured``;
``health_html`` and ``actions_html``, the zones the cockpit already had;
``now``.

A section says when it was checked, to the second, and holds its own
« Revérifier » (POST /api/usine/reverifier): reading the page again reads
nothing again. A connection says its state, its latency (how long the
cockpit's last read of it took) and its freshness, from the check; once its
source is no longer current it says how long ago it was seen, and a source
never read is « inconnu — la source ne répond pas », never 0, never a
failure. Nothing on the page is an example value: what the cockpit cannot
read is said unread.

Intent (Benjamin, his words, 2026-10-19 19:20 Paris): « enchaîne
directement sur Runs puis Usine. »
Mechanism (agent interpretation): the page served since PR #683 completed
on its real sources; settings, clean-up and stop stay visibly unavailable
until their tickets (G2, H).
"""
import html
import os
import platform
import shutil
import socket
from datetime import datetime

from account_home import account_home

from cockpit.core.freshness import FRESH
from cockpit.core.readmodel import PARIS

GIB = 1024 ** 3
UNKNOWN_SAYING = "inconnu — la source ne répond pas"
EFFORTS = {"minimal": "Minimal", "low": "Faible", "medium": "Moyen", "high": "Élevé", "xhigh": "Très élevé",
           "max": "Maximal"}
# What each source the cockpit reads is for, under its name.
PURPOSES = {
    "gc": "Lecture du travail de l’usine",
    "beads": "Tickets et demandes",
    "sessions": "Sessions au travail",
    "journal": "Événements du journal",
    "projets": "Projets déclarés",
    "runs": "Exécutions des workflows",
    "git": "Version de l’usine",
    "depots": "Dépôts des projets",
    "tailscale": "Accès privé à la VM",
}
SECTION_NAMES = {"machine": "la machine", "connexions": "les connexions", "agents": "la configuration"}


def _e(value):
    return html.escape(str(value), quote=True)


def _go(value):
    return ("%.1f" % (value / GIB)).replace(".", ",")


def _clock(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M:%S")


def _age(seconds):
    seconds = max(0, int(seconds))
    for unit, size in (("j", 86400), ("h", 3600), ("min", 60)):
        if seconds >= size:
            return "%d %s" % (seconds // size, unit)
    return "%d s" % seconds


def _latency(seconds):
    millis = seconds * 1000
    return ("%.1f ms" % max(millis, 0.1)).replace(".", ",") if millis < 10 else "%d ms" % round(millis)


def model_label(model):
    """« claude-opus-5-5 » is Claude Opus 5.5, « gpt-5.6-sol » GPT-5.6 Sol;
    another id is said as it is."""
    if not model:
        return "modèle non configuré"
    parts = model.split("-")
    if parts[0] == "claude" and len(parts) >= 3 and all(p.isdigit() for p in parts[2:]):
        return "Claude %s %s" % (parts[1].capitalize(), ".".join(parts[2:]))
    if parts[0] == "gpt" and len(parts) >= 2:
        return " ".join(["GPT-" + parts[1]] + [p.capitalize() for p in parts[2:]])
    return model


def effort_label(effort):
    return EFFORTS.get(effort, effort) if effort else "non configuré"


def read_machine(path=None):
    """What the machine the cockpit runs on holds now: cores, load, memory,
    disk. A part that cannot be read is None, never guessed."""
    out = {"host": socket.gethostname(), "system": "%s %s" % (platform.system(), platform.release()),
           "cores": os.cpu_count(), "load": None, "mem_total": None, "mem_used": None,
           "disk_total": None, "disk_used": None}
    try:
        out["load"] = os.getloadavg()[0]
    except OSError:
        pass
    try:
        info = {}
        with open("/proc/meminfo") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0]) * 1024
        out["mem_total"] = info["MemTotal"]
        out["mem_used"] = info["MemTotal"] - info.get("MemAvailable", info.get("MemFree", 0))
    except (OSError, KeyError, ValueError, IndexError):
        pass
    try:
        usage = shutil.disk_usage(path or account_home())
        out["disk_total"], out["disk_used"] = usage.total, usage.used
    except OSError:
        pass
    return out


def _recheck(section, selected, label="Revérifier"):
    """The button that checks one section again, and keeps the role open."""
    return ('<form class="fa-recheck" method="post" action="/api/usine/reverifier">'
            '<input type="hidden" name="section" value="%s"><input type="hidden" name="role" value="%s">'
            '<button type="submit" aria-label="Revérifier %s">%s</button></form>'
            % (_e(section), _e(selected or ""), _e(SECTION_NAMES[section]), _e(label)))


def _checked(label, check, section, selected):
    return ('<div class="fa-check"><span class="fa-chip">%s à %s (Paris)</span>%s</div>'
            % (_e(label), _clock(check["at"]), _recheck(section, selected)))


def _meter(a, label, value, percent, note):
    width = 0 if percent is None else max(0, min(100, percent))
    return ('<div class="fa-meter" %s><div class="fa-meter-head" %s><span>%s</span><strong>%s</strong></div>'
            '<div class="fa-bar" %s><span style="width:%d%%"></span></div><small>%s</small></div>'
            % (a("div"), a("gauge-top"), _e(label), _e(value), a("meter"), width, _e(note)))


def render_machine(a, check, selected):
    machine = check["value"]
    cores = machine["cores"] or 0
    load = machine["load"]
    cpu = None if load is None or not cores else round(100 * load / cores)
    mem_t, mem_u = machine["mem_total"], machine["mem_used"]
    disk_t, disk_u = machine["disk_total"], machine["disk_used"]
    disk = None if not disk_t else round(100 * disk_u / disk_t)
    summary = "%s · %s · %d cœurs%s" % (machine["host"], machine["system"], cores,
                                       " · %s Go de mémoire" % _go(mem_t) if mem_t else "")
    meters = (
        _meter(a, "Processeur", "non lu" if cpu is None else "%d %%" % cpu, cpu,
               "Charge non lue" if load is None
               else "Charge moyenne : %s / %d cœurs" % (("%.1f" % load).replace(".", ","), cores))
        + _meter(a, "Mémoire", "non lue" if mem_u is None else "%s Go" % _go(mem_u),
                 None if not mem_t else 100 * mem_u / mem_t,
                 "Mémoire non lue" if not mem_t else "%s Go de capacité totale" % _go(mem_t))
        + _meter(a, "Disque", "non lu" if disk is None else "%d %%" % disk, disk,
                 "Disque non lu" if disk is None else "%s Go utilisés sur %s Go" % (_go(disk_u), _go(disk_t)))
    )
    return ('<section class="pn-panel" %s><div class="fa-head" %s><div><h2>Machine d’exécution</h2>'
            '<p class="fa-muted">%s</p></div>%s</div><div class="fa-meters" %s>%s</div></section>'
            % (a("panel"), a("host-heading"), _e(summary), _checked("Vérifiée", check, "machine", selected),
               a("capacity"), meters))


def _connection_row(a, name, checked, live, now):
    """One connection: its state, latency and freshness. The check gives
    what was measured; the read model now says whether it is still current."""
    label = (live.get("display_name") or name).capitalize()
    purpose = PURPOSES.get(name, "Source lue par le cockpit")
    if live.get("read_at") is None:
        tone, state, value = "unknown", UNKNOWN_SAYING, ""
    elif live.get("freshness") == FRESH:
        row = checked if checked and checked.get("freshness") == FRESH and checked.get("read_at") else live
        tone, state = "ok", "À jour · lu à %s" % _clock(row["read_at"])
        value = _latency(row["latency"]) if row.get("latency") is not None else "latence non mesurée"
    else:
        tone, state = "stale", "Périmé · vu il y a %s" % _age(now - live["read_at"])
        value = ("dernière latence %s" % _latency(live["latency"]) if live.get("latency") is not None
                 else "latence non mesurée")
    return ('<li class="fa-row fa-%s" %s><span class="fa-dot %s" aria-hidden="true"></span>'
            '<div><strong>%s</strong><small>%s · %s</small></div><span class="fa-val">%s</span></li>'
            % (tone, a("connection-row"), tone, _e(label), _e(purpose), _e(state), _e(value)))


def render_connections(a, check, live, notify_configured, now, selected):
    names = sorted(live, key=lambda name: (name != "gc", (live[name].get("display_name") or name)))
    rows = [_connection_row(a, name, check["value"].get(name), live[name], now) for name in names]
    rows.append('<li class="fa-row fa-%s" %s><span class="fa-dot %s" aria-hidden="true"></span><div>'
                '<strong>Notifications iPhone</strong><small>Envoi Pushover · %s</small></div>'
                '<span class="fa-val">latence non mesurée</span></li>'
                % (("ok", a("connection-row"), "ok", "configurées") if notify_configured
                   else ("off", a("connection-row"), "off", "non configurées")))
    return ('<section class="pn-panel" %s><div class="fa-head"><h2>Connexions</h2>%s</div>'
            '<ul class="fa-list">%s</ul><p class="fa-muted fa-note" %s>Latence : durée de la dernière lecture de '
            'chaque source par le cockpit. Une source qui ne répond plus est grisée avec son âge. Aucun envoi de '
            'notification n’est assimilé à une réception sur le téléphone.</p></section>'
            % (a("panel"), _checked("Vérifiées", check, "connexions", selected), "".join(rows), a("readonly-note")))


def _provider_line(provider):
    if provider is None:
        return "aucun fournisseur configuré"
    return "%s · effort %s" % (model_label(provider["model"]), effort_label(provider["effort"]).lower())


def _role_of(configuration, key):
    return next((role for role in configuration["roles"] if role["key"] == key), None)


def render_flow(a, configuration, selected):
    """The descending drawing of the delivery flow: the deterministic
    controller, then each step a role runs, which can be selected."""
    def fixed(title, note):
        return ('<div class="fa-node" %s><strong>%s</strong><small>%s</small></div>'
                % (a("flow-node"), _e(title), _e(note)))

    def agent(step):
        role = _role_of(configuration, step["role"])
        if role is None:
            return fixed(step["label"], "rôle non configuré")
        current = ' aria-current="true"' if role["key"] == selected else ""
        return ('<a class="fa-node fa-agent" href="/usine?role=%s#role"%s %s><strong>%s</strong><small>%s · %s</small></a>'
                % (_e(role["key"]), current, a("flow-node"), _e(step["label"]), _e(role["label"]),
                   _e(_provider_line(role["configured"]))))

    arrow = lambda: '<span class="fa-arrow" aria-hidden="true" %s>↓</span>' % a("flow-arrow")  # noqa: E731
    parts = [fixed("Contrôleur du flux de livraison", "Code déterministe · départs, transitions et plafonds")]
    for index, stage in enumerate(configuration["flow"]):
        if index == len(configuration["flow"]) - 1 and index:
            parts += [arrow(), fixed("Intégration et vérifications", "Code déterministe")]
        nodes = "".join(agent(step) for step in stage)
        parts += [arrow(), nodes if len(stage) == 1 else '<div class="fa-parallel" %s>%s</div>' % (a("flow-parallel"),
                                                                                                    nodes)]
    parts += [arrow(), fixed("Ton jugement → fusion du résultat accepté", "Décision humaine, puis exécution contrôlée")]
    return '<div class="fa-flow" %s>%s</div>' % (a("flow-down"), "".join(parts))


def _plural(count, word):
    return "%d %s%s" % (count, word, "s" if count > 1 else "")


def _bounds_line(bounds):
    if not isinstance(bounds, dict):
        return "Limites du flux non lues."
    resumes = [value for value in (bounds.get("resumes") or {}).values() if isinstance(value, int)]
    parts = []
    if resumes:
        parts.append(("%s au plus par cause" % _plural(max(resumes), "reprise")) if len(set(resumes)) == 1
                     else "jusqu’à %s selon la cause" % _plural(max(resumes), "reprise"))
    if isinstance(bounds.get("open_planning_exceptions"), int):
        parts.append("%s" % _plural(bounds["open_planning_exceptions"], "exception") + " ouverte"
                     + ("s" if bounds["open_planning_exceptions"] > 1 else ""))
    if isinstance(bounds.get("end_rounds"), int):
        parts.append("%s de fin" % _plural(bounds["end_rounds"], "tour"))
    return "Limites du flux : %s. Limites configurées, pas un optimum calculé." % ", ".join(parts)


def _sessions_of(role, sessions_row):
    value = (sessions_row or {}).get("value")
    if not isinstance(value, dict) or (sessions_row or {}).get("read_at") is None:
        return "non lues"
    held = [s for s in value.get("sessions") or [] if str(s.get("assignee") or "").startswith(role["agent"] or "\0")]
    return str(len(held))


def render_role(a, configuration, sessions_row, in_service, key):
    role = _role_of(configuration, key)
    if role is None:
        return ('<section class="fa-role" id="role" %s><h3 %s>Rôle inconnu</h3><p>Ce rôle n’est pas dans la '
                'configuration lue.</p></section>' % (a("section"), a("h3")))
    configured = role["configured"]
    rows = [
        ("Fournisseur", configured["pool"] if configured else "aucun fournisseur configuré"),
        ("Modèle configuré", model_label(configured["model"]) if configured else "—"),
        ("Effort", effort_label(configured["effort"]) if configured else "—"),
        ("Accès", ("lecture seule" if configured["read_only"] else "écriture") if configured else "—"),
        ("Concurrence", "%s maximum" % _plural(role["max_sessions"], "session") if role["max_sessions"] is not None
         else "plafond non configuré"),
    ]
    fallbacks = ("Secours, dans l’ordre : %s." % " ; ".join(
        "%s (%s)" % (_provider_line(p), p["pool"] or p["label"]) for p in role["fallbacks"])
        if role["fallbacks"] else "Aucun secours inter-fournisseur configuré.")
    if in_service is None:
        serving = "non observé sur cet hôte (aucun état de repli écrit)"
    else:
        name = in_service.get(role["agent"])
        serving = "non observé" if not name else next(
            (model_label(p["model"]) for p in [configured, *role["fallbacks"]] if p and p["name"] == name), name)
    return (
        '<section class="fa-role" id="role" %s><h3 %s>%s</h3>'
        '<p class="fa-kicker">Configuration</p><dl class="fa-rows">%s</dl><p>%s</p>'
        '<p class="fa-muted">%s</p>'
        '<p class="fa-kicker">Observé</p><dl class="fa-rows"><div><dt>Fournisseur en service</dt><dd>%s</dd></div>'
        '<div><dt>Sessions de ce rôle au travail</dt><dd>%s</dd></div></dl>'
        '<p class="fa-muted">Disponibilité des API et quotas : non mesurés par le cockpit.</p>'
        '<button type="button" disabled>Configurer</button>'
        '<p class="fa-muted">Les réglages ne sont pas encore raccordés à leur porte.</p></section>'
    ) % (a("section"), a("h3"), _e(role["label"]),
         "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (_e(k), _e(v)) for k, v in rows), _e(fallbacks),
         _e(_bounds_line(configuration["bounds"])), _e(serving), _e(_sessions_of(role, sessions_row)))


def render_agents(a, check, selected):
    configuration, sessions_row = check["value"]["configuration"], check["value"]["sessions"]
    others = "".join(
        "<li><strong>%s</strong> · %s</li>" % (_e(other["label"]), _e(_provider_line(other["configured"])))
        for other in configuration["other_roles"])
    unreadable = ("<p class=\"fa-warn\">Fichiers de configuration illisibles : %s.</p>"
                  % _e(", ".join(configuration["unreadable"])) if configuration["unreadable"] else "")
    return (
        '<section class="pn-panel" %s><div class="fa-head"><div><h2>Agents dans le workflow</h2>'
        '<p class="fa-muted">Configuration de l’usine, distinguée de ce qui est observé · les sessions en cours '
        'sont dans <a href="/runs">Runs</a></p></div>%s</div>%s'
        '<div class="fa-agents" %s>%s%s</div>'
        '<div class="fa-others"><p class="fa-kicker">Hors du flux de livraison</p><ul>%s</ul></div>'
        '<details><summary>Sources de la configuration</summary><p>Rôles, fournisseurs, modèles, efforts, secours et '
        'limites lus dans config/delivery-roles.json, config/provider-policy.json, city.toml et '
        'config/delivery-flow.json. Le fournisseur en service est lu dans city.provider.toml, écrit par le repli '
        'automatique. Le dessin simplifie le flux : corrections et reprises reviennent à l’auteur ; il ne '
        'remplace pas les transitions du moteur.</p></details></section>'
    ) % (a("panel"), _checked("Configuration lue", check, "agents", selected), unreadable, a("section-grid"),
         render_flow(a, configuration, selected),
         render_role(a, configuration, sessions_row, configuration["in_service"], selected), others)


def render_unavailable(a, actions_html):
    return (
        '<section class="pn-panel" %s><h2>Suspension, reprise et arrêt</h2><p>La VM héberge l’usine. Fermer ou '
        'éteindre ce PC client n’arrête pas la VM.</p><div class="fa-actions">'
        '<button type="button" disabled>Demander la suspension</button>'
        '<button type="button" disabled>Préparer l’arrêt de la machine</button></div>'
        '<p class="fa-muted">Indisponible : l’arrêt propre et la reprise vérifiée ne sont pas encore raccordés.</p>'
        '<div class="fa-legacy">%s</div></section>'
        '<section class="pn-panel" %s><h2>Nettoyer les espaces inutilisés</h2><p>Prévisualiser les candidats et '
        'protéger les travaux encore utiles.</p><div class="fa-actions">'
        '<button type="button" disabled>Examiner le périmètre</button></div>'
        '<p class="fa-muted">Indisponible : le nettoyage n’est pas encore raccordé.</p></section>'
    ) % (a("panel"), actions_html, a("panel"))


def render_factory_page(view):
    """The main part of the page, as a function of its anchors."""
    def draw(a):
        return (
            '<div class="pn-head"><h1 %s>Usine</h1><p class="fa-sub" %s>Ressources, connexions et réglages de '
            'l’environnement d’exécution.</p></div>%s<div class="fa-two" %s>%s</div>%s'
            '<div class="fa-legacy">%s</div>%s'
        ) % (a("h1"), a("page-lead"), render_machine(a, view["machine"], view["selected"]), a("section-grid"),
             render_connections(a, view["connections"], view["live"], view["notify_configured"], view["now"],
                                view["selected"]),
             render_agents(a, view["agents"], view["selected"]), view["health_html"],
             render_unavailable(a, view["actions_html"]))
    return draw


CSS = """
.fa-sub{margin:0 0 20px;color:var(--pn-muted-text)}
.fa-muted{color:var(--pn-muted-text);font-size:13px}
.fa-warn{color:var(--pn-warn-text)}
.fa-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.fa-head h2{margin:0 0 6px}
.fa-head>div{min-width:0}
.fa-check{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.fa-chip{border:1px solid var(--line);border-radius:999px;padding:5px 10px;font-size:12px}
.fa-recheck{display:contents}
.pn-main button{font:inherit;font-size:13px;color:var(--ink);background:var(--surface);
  border:1px solid var(--pn-control-line);border-radius:8px;padding:7px 12px;cursor:pointer}
.pn-main button:disabled{cursor:not-allowed;color:var(--pn-muted-text);border-style:dashed}
.fa-meters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.fa-meter-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.fa-meter-head strong{font-size:22px}
.fa-bar{height:6px;border-radius:6px;background:var(--line);overflow:hidden;margin-bottom:10px}
.fa-bar span{display:block;height:100%;background:var(--accent)}
.fa-meter small{font-size:12px;color:var(--pn-muted-text)}
.fa-two{display:grid;grid-template-columns:minmax(0,1fr);gap:20px}
.fa-list{list-style:none;margin:0;padding:0}
.fa-row{display:grid;grid-template-columns:12px minmax(0,1fr) auto;gap:10px;align-items:center;padding:12px 0;
  border-bottom:1px solid var(--line)}
.fa-row:last-child{border-bottom:0}
.fa-row strong{display:block;font-size:14px}
.fa-row small{display:block;font-size:12px;color:var(--pn-muted-text);margin-top:3px;overflow-wrap:anywhere}
.fa-row.fa-stale strong,.fa-row.fa-stale .fa-val,.fa-row.fa-unknown strong,.fa-row.fa-off strong{color:var(--pn-muted-text)}
.fa-val{font-size:14px;text-align:right}
.fa-dot{width:8px;height:8px;border-radius:100%;background:var(--line)}
.fa-dot.ok{background:var(--ok)}.fa-dot.stale{background:var(--pn-muted-text)}
.fa-dot.unknown,.fa-dot.off{background:transparent;border:1px solid var(--pn-muted-text)}
.fa-note{margin-top:12px!important}
.fa-agents{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}
.fa-flow{display:flex;flex-direction:column;align-items:stretch;gap:4px}
.fa-node{display:block;border:1px solid var(--line);border-radius:8px;padding:10px 12px;color:inherit;
  text-decoration:none;background:var(--bg)}
.fa-node strong{display:block;font-size:14px}.fa-node small{display:block;font-size:12px;color:var(--pn-muted-text);
  margin-top:3px;overflow-wrap:anywhere}
a.fa-agent{border-color:var(--pn-control-line);background:var(--surface)}
a.fa-agent:hover{border-color:var(--accent)}
a.fa-agent[aria-current="true"]{background:var(--pn-surface-2);border-color:var(--accent)}
.fa-parallel{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px}
.fa-arrow{align-self:center;color:var(--pn-muted-text);line-height:1}
.fa-role h3{font-size:17px;margin:0 0 10px}
.fa-role p{margin:10px 0}
.fa-kicker{font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--pn-muted-text);margin:14px 0 6px!important}
.fa-rows{margin:0}
.fa-rows div{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid var(--line)}
.fa-rows dt{color:var(--pn-muted-text)}.fa-rows dd{margin:0;text-align:right;font-weight:600;overflow-wrap:anywhere}
.fa-others ul{margin:0;padding-left:18px}.fa-others li{margin:4px 0;overflow-wrap:anywhere}
.fa-actions{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 8px}
.pn-panel details{margin-top:14px}.pn-panel summary{cursor:pointer;color:var(--pn-muted-text)}
.fa-legacy section{margin:12px 0 0}
.fa-legacy,.fa-legacy *{white-space:normal;overflow-wrap:anywhere;min-width:0}
.fa-legacy h2{font-size:19px}
@media (max-width:900px){.fa-meters,.fa-agents{grid-template-columns:1fr}}
"""
