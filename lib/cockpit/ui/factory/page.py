"""The destination Usine of Panorama (G1, af-wrxrmg, Prototype Fold of the
reference prototypes/c01-complete/frozen-panorama-factory at 632deea; Spec
af-fgcw0d, user stories 63, 65, 124, 160, 161, 162 and 175): the machine the
factory runs on, the connections the cockpit reads, the roles of the
delivery flow as the Factory's files configure them, beside what is observed
of them, and the zones that change the factory, still unavailable.

    render_factory_page(view) -> a function of the anchors of the page

``view`` holds what the page shows, already read: ``machine``,
``connections``, ``providers`` and ``agents``, the last check of each
section (cockpit.factory.checks: ``{"at", "value"}``); ``live``, the read model now;
``selected``, the role whose detail is open; ``notify_configured``;
``health_html`` and ``actions_html``, the zones the cockpit already had;
``now``.

A section says when it was checked, to the second -- greyed « périmé, vu il
y a … » once that check is older than its validity -- and holds its own
« Revérifier maintenant » (POST /api/usine/reverifier): reading the page
again reads nothing again. A connection says its state, its latency (how
long the cockpit's last read of it took) and its freshness, from the check;
once its source is no longer current it is greyed « Périmé » with how long
ago it was seen, a source that has failed since (cockpit.core.freshness:
UNKNOWN, a last reading kept) is « Inconnu — la source ne répond plus »
with that age, and a source never read is « inconnu — la source ne répond
pas »: never 0, never a failure, never a latency. What the provider
failover observed of each provider (a quota exhausted, an error, a provider
disabled) is shown apart from the configuration, and said not observed
where the host holds no state of it, or no record of that pool. The
notifications, whose delivery is not measured, are never drawn verified;
the sessions of a role are said with the freshness of their source. Nothing on the page is an example value: what the cockpit cannot
read is said unread.

Intent (Benjamin, his words, 2026-10-19 19:20 Paris): « enchaîne
directement sur Runs puis Usine. »
Mechanism (agent interpretation): the page served since PR #683 completed
on its real sources; settings, clean-up and stop stay visibly unavailable
until their tickets (G2, H).
"""
import html
import json
import os
import platform
import shutil
import socket
from datetime import datetime

from account_home import account_home

from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.core.readmodel import PARIS

GIB = 1024 ** 3
UNKNOWN_SAYING = "inconnu — la source ne répond pas"
FAILING_SAYING = "Inconnu — la source ne répond plus"
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
SECTION_NAMES = {"machine": "la machine", "connexions": "les connexions", "fournisseurs": "les fournisseurs",
                 "agents": "la configuration"}
# What the provider failover observed of a provider or its pool.
NOT_RECORDED = "aucun relevé du repli"
AVAILABILITY = {"available": "aucune limite détectée", "exhausted": "quota épuisé", "low": "quota bas",
                "error": "en erreur", "disabled": "désactivé"}


def _e(value):
    return html.escape(str(value), quote=True)


def _go(value):
    return ("%.1f" % (value / GIB)).replace(".", ",")


def _clock(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M:%S")


def _duration(seconds):
    """« 3 j 4 h 12 min 7 s »: a length of time to the second, without the
    colons of a time of day."""
    seconds = max(0, int(seconds))
    parts = []
    for unit, size in (("j", 86400), ("h", 3600), ("min", 60)):
        if seconds >= size or parts:
            parts.append("%d %s" % (seconds // size, unit))
            seconds %= size
    return " ".join(parts + ["%d s" % seconds])


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
           "disk_total": None, "disk_used": None, "uptime": None}
    try:
        with open("/proc/uptime") as handle:
            out["uptime"] = float(handle.read().split()[0])
    except (OSError, ValueError, IndexError):
        pass
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


def _recheck(section, selected, label="Revérifier maintenant"):
    """The button that checks one section again, and keeps the role open."""
    return ('<form class="fa-recheck" method="post" action="/api/usine/reverifier">'
            '<input type="hidden" name="section" value="%s"><input type="hidden" name="role" value="%s">'
            '<button type="submit" aria-label="Revérifier maintenant %s">%s</button></form>'
            % (_e(section), _e(selected or ""), _e(SECTION_NAMES[section]), _e(label)))


def _checked(label, check, section, selected, now):
    """When the section was checked, greyed with its age once that check is
    no longer current, and its « Revérifier maintenant »."""
    said = "%s à %s (Paris)" % (label, _clock(check["at"]))
    if check.get("stale"):
        said += " · périmé, vu il y a %s" % _age(now - check["at"])
    return ('<div class="fa-check"><span class="fa-chip%s">%s</span>%s</div>'
            % (" fa-stale" if check.get("stale") else "", _e(said), _recheck(section, selected)))


def _meter(a, label, value, percent, note):
    width = 0 if percent is None else max(0, min(100, percent))
    return ('<div class="fa-meter" %s><div class="fa-meter-head" %s><span>%s</span><strong>%s</strong></div>'
            '<div class="fa-bar" %s><span style="width:%d%%"></span></div><small>%s</small></div>'
            % (a("div"), a("gauge-top"), _e(label), _e(value), a("meter"), width, _e(note)))


def render_machine(a, check, selected, now):
    machine = check["value"]
    cores = machine["cores"] or 0
    load = machine["load"]
    cpu = None if load is None or not cores else round(100 * load / cores)
    mem_t, mem_u = machine["mem_total"], machine["mem_used"]
    disk_t, disk_u = machine["disk_total"], machine["disk_used"]
    disk = None if not disk_t else round(100 * disk_u / disk_t)
    summary = "%s · %s · %d cœurs%s · %s" % (
        machine["host"], machine["system"], cores, " · %s Go de mémoire" % _go(mem_t) if mem_t else "",
        "en service depuis %s" % _duration(machine["uptime"]) if machine.get("uptime") is not None
        else "durée de service non lue")
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
            % (a("panel"), a("host-heading"), _e(summary), _checked("Vérifiée", check, "machine", selected, now),
               a("capacity"), meters))


def _connection_row(a, name, checked, live, now):
    """One connection: its state, latency and freshness. The check gives
    what was measured; the read model now says whether it is still current."""
    label = (live.get("display_name") or name).capitalize()
    purpose = PURPOSES.get(name, "Source lue par le cockpit")
    if live.get("read_at") is None:
        tone, state, value = "unknown", UNKNOWN_SAYING, ""
    elif live.get("freshness") == UNKNOWN:
        tone, state, value = "unknown", "%s · vu il y a %s" % (FAILING_SAYING, _age(now - live["read_at"])), ""
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
                % (("unknown", a("connection-row"), "unknown", "Configurées, remise non vérifiée") if notify_configured
                   else ("off", a("connection-row"), "off", "Non configurées")))
    return ('<section class="pn-panel" %s><div class="fa-head"><h2>Connexions</h2>%s</div>'
            '<ul class="fa-list">%s</ul><p class="fa-muted fa-note" %s>Latence : durée de la dernière lecture de '
            'chaque source par le cockpit. Une source qui ne répond plus est grisée avec son âge. Aucun envoi de '
            'notification n’est assimilé à une réception sur le téléphone.</p></section>'
            % (a("panel"), _checked("Vérifiées", check, "connexions", selected, now), "".join(rows), a("readonly-note")))


def _observed(status):
    """« quota épuisé jusqu’à 18:00 »: what the failover observed of a
    provider or its pool; « aucun relevé du repli » when the failover
    recorded nothing of it."""
    if not status.get("recorded"):
        return NOT_RECORDED
    said = AVAILABILITY.get(status.get("state"), status.get("state") or "non observé")
    if status.get("until") is not None and status.get("state") != "available":
        said += " jusqu’à %s" % _clock(status["until"])[:5]
    if status.get("state") == "disabled" and status.get("reason"):
        said += " (%s)" % status["reason"]
    return said


def render_providers(a, check, selected, now):
    """« Fournisseurs et accès API »: each pool of quota the providers draw
    on, the providers configured on it, and what the failover observed."""
    configuration = check["value"]
    availability = configuration["availability"]
    rows = []
    for pool in configuration["pools"]:
        if availability is None:
            tone, said = "unknown", "disponibilité non observée"
        else:
            status = availability["pools"].get(pool["key"]) or {}
            tone = ("unknown" if not status.get("recorded") else "ok" if status.get("state") == "available"
                    else "stale")
            said = _observed(status)
        rows.append('<li class="fa-row fa-%s" %s><span class="fa-dot %s" aria-hidden="true"></span><div>'
                    '<strong>%s</strong><small>%s</small></div><span class="fa-val">%s</span></li>'
                    % (tone, a("connection-row"), tone, _e(pool["label"]),
                       _e(" · ".join(pool["providers"]) or "aucun fournisseur configuré"), _e(said[:1].upper() + said[1:])))
    if availability is None:
        source = ("Aucun état du repli automatique sur cet hôte (.gc/provider-state.json) : la disponibilité des "
                  "fournisseurs n’y est pas observée.")
    else:
        source = ("Disponibilité observée par le repli automatique des fournisseurs%s : « aucune limite détectée » "
                  "ne mesure pas un quota." % (" à %s" % _clock(availability["at"]) if availability["at"] else ""))
    return ('<section class="pn-panel" %s><div class="fa-head"><h2>Fournisseurs et accès API</h2>%s</div>'
            '<ul class="fa-list">%s</ul><p class="fa-muted fa-note" %s>%s Aucune clé affichée. Un compte configuré ne '
            'prouve pas que son quota est disponible.</p></section>'
            % (a("panel"), _checked("Vérifiés", check, "fournisseurs", selected, now), "".join(rows), a("readonly-note"),
               _e(source)))


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
    if isinstance(bounds.get("correction_rounds"), int):
        parts.append("%s de correction" % _plural(bounds["correction_rounds"], "tour"))
    return "Limites du flux : %s. Limites configurées, pas un optimum calculé." % ", ".join(parts)


def _sessions_of(role, checked, live, now):
    """How many sessions of the role are at work: the count of the check
    while the source is current, the last count kept greyed « périmé » with
    its age once it is not, never a count once the source fails. The read
    model now says whether the source is still current, as for a connection."""
    live = live or {}
    if live.get("read_at") is None:
        return UNKNOWN_SAYING
    if live.get("freshness") == UNKNOWN:
        return "%s · vu il y a %s" % (FAILING_SAYING, _age(now - live["read_at"]))
    current = live.get("freshness") == FRESH
    row = checked if current and (checked or {}).get("freshness") == FRESH and checked.get("read_at") else live
    value = row.get("value")
    if not isinstance(value, dict):
        return UNKNOWN_SAYING
    held = [s for s in value.get("sessions") or [] if str(s.get("assignee") or "").startswith(role["agent"] or "\0")]
    if current:
        return str(len(held))
    return "%d · périmé, vu il y a %s" % (len(held), _age(now - live["read_at"]))


def _availability_of(role, availability):
    """What the failover observed of each provider of the role's chain, in
    its order."""
    chain = [p for p in [role["configured"], *role["fallbacks"]] if p]
    if availability is None:
        return "non observée sur cet hôte (aucun état du repli écrit)"
    if not chain:
        return "aucun fournisseur configuré"
    return " ; ".join("%s : %s" % (model_label(p["model"]), _observed(availability["providers"].get(p["name"]) or {}))
                      for p in chain)


def _form_hidden(fields):
    return "".join('<input type="hidden" name="%s" value="%s">' % (_e(k), _e(v)) for k, v in fields.items())


def render_setting(a, role, setting):
    """What the role panel shows of its setting (G2, af-f8nlhr): the
    control « Configurer », available or not with its reason, and the last
    outcome; or the editor, the scope of a change, a proposal prepared."""
    key = role["key"]
    mode = setting.get("mode") or "role"
    alert = '<p class="fa-alert" role="alert" data-usine-alert hidden></p>'
    if mode == "modifier":
        offered = setting["offered"]

        def choice(field, value, name, note, checked):
            index = next(counter)
            return ('<label class="fa-choice"><input type="radio" name="%s" value="%s" aria-label="%s" '
                    'aria-describedby="choix-%d"%s> %s <small id="choix-%d">%s</small></label>'
                    % (field, _e(value), _e(name), index, " checked" if checked else "", _e(name), index, _e(note)))

        counter = iter(range(10 ** 6))
        providers = "".join(
            choice("principal", p["name"], p["label"],
                   "en tête aujourd’hui" if p["current"] else "dans l’ordre du rôle · réglable" if p["supported"]
                   else "essai d’adoption du rôle à faire · proposition", p["current"])
            for p in offered["providers"])
        efforts = "".join(
            choice("effort", "" if e["current"] else e["key"], "Effort : %s" % EFFORTS.get(e["key"], e["key"]),
                   "celui du fournisseur en tête aujourd’hui" if e["current"] else "aucune porte ne le règle · proposition",
                   e["current"])
            for e in offered["efforts"])
        if not any(e["current"] for e in offered["efforts"]):
            efforts = choice("effort", "", "Effort inchangé", "celui du fournisseur choisi", True) + efforts
        fallbacks = choice("secours", "", "Secours inchangés", "l’ordre du rôle, sans ajout", True) + "".join(
            choice("secours", p["name"], "Ajouter en secours : %s" % p["label"],
                   "essai d’adoption du rôle à faire · proposition", False)
            for p in offered["fallbacks"])
        return (
            '<form class="fa-setting" method="get" action="/usine#role">%s'
            '<fieldset><legend>Fournisseur en tête des prochaines sessions</legend>%s</fieldset>'
            '<fieldset><legend>Effort de raisonnement</legend>%s</fieldset>'
            '<fieldset><legend>Secours</legend>%s</fieldset>'
            '<p class="fa-muted">Seul l’ordre des fournisseurs déjà essayés pour le rôle se règle par sa porte. Un '
            'autre fournisseur, un autre effort ou un nouveau secours ne devient pas utilisable par simple sélection : '
            'il est préparé comme proposition.</p>'
            '<div class="fa-actions"><a class="fa-link" href="/usine?role=%s#role">Annuler</a>'
            '<button type="submit">Voir la portée</button></div></form>'
        ) % (_form_hidden({"role": key, "reglage": "portee"}), providers, efforts, fallbacks, _e(key))
    if mode == "portee":
        plan = setting["plan"]
        back = "/usine?role=%s&reglage=modifier#role" % key
        rows = [("Valeur actuelle", plan["current_text"]), ("Nouvelle valeur", plan["new_text"]),
                ("Portée", "%s · Nouvelles sessions uniquement : les sessions ouvertes gardent leur fournisseur."
                 % plan["label"]),
                ("Conséquences", plan["consequences"])]
        if not plan["changes"]:
            act = ""
        else:
            action, label = (("regler", "Appliquer ce changement") if plan["supported"]
                             else ("preparer_reglage", "Préparer ce changement"))
            act = ('<button type="button" data-usine-action="%s" data-body="%s" data-next="%s">%s</button>'
                   % (action, _e(json.dumps({"role": key, "principal": plan["principal"], "effort": plan["effort"],
                                             "secours": plan["fallback"], "confirm": True})),
                      _e("/usine?role=%s&reglage=%s#role" % (key, "fait" if plan["supported"] else "propose")),
                      label))
        blocked = setting.get("blocked")
        if blocked and act:
            act = act.replace("<button ", "<button disabled ", 1)
        return (
            '<div class="fa-setting"><p class="fa-kicker">Changement à confirmer</p><dl class="fa-rows">%s</dl>%s'
            '<div class="fa-actions"><a class="fa-link" href="%s">Retour</a>%s</div>'
            '%s</div>'
        ) % ("".join("<div><dt>%s</dt><dd>%s</dd></div>" % (_e(k), _e(v)) for k, v in rows),
             '<p class="fa-muted">%s</p>' % _e(blocked) if blocked else "", _e(back), act, alert)
    outcome = setting.get("outcome")
    said = '<p class="fa-outcome" role="status">%s</p>' % _e(outcome) if outcome else ""
    blocked = setting.get("blocked")
    return (
        '%s<form class="fa-setting" method="get" action="/usine#role">%s<button type="submit"%s>Configurer</button>'
        '</form><p class="fa-muted">%s</p>'
    ) % (said, _form_hidden({"role": key, "reglage": "modifier"}), " disabled" if blocked else "",
         _e(blocked or "Change le fournisseur en tête de ce rôle, son effort ou ses secours ; tu vois la portée "
                       "avant de confirmer."))


def render_role(a, configuration, sessions_row, live_sessions, in_service, key, now, setting=None):
    setting = setting or {}
    role = _role_of(configuration, key)
    if setting.get("mode") == "propose" and role is not None:
        return ('<section class="fa-role" id="role" %s><h3 %s>%s</h3><p class="fa-outcome" role="status">%s</p>'
                '<p><a class="fa-link" href="/">Voir la proposition dans Pour moi</a> · '
                '<a class="fa-link" href="/usine?role=%s#role">Revenir au rôle</a></p></section>'
                % (a("section"), a("h3"), _e(role["label"]), _e(setting.get("outcome") or
                   "Aucune proposition préparée depuis ce rôle."), _e(key)))
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
        '<div><dt>Disponibilité observée</dt><dd>%s</dd></div>'
        '<div><dt>Sessions de ce rôle au travail</dt><dd>%s</dd></div></dl>%s</section>'
    ) % (a("section"), a("h3"), _e(role["label"]),
         "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (_e(k), _e(v)) for k, v in rows), _e(fallbacks),
         _e(_bounds_line(configuration["bounds"])), _e(serving),
         _e(_availability_of(role, configuration["availability"])), _e(_sessions_of(role, sessions_row, live_sessions, now)),
         render_setting(a, role, setting))


def render_agents(a, check, live, selected, now, setting=None):
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
    ) % (a("panel"), _checked("Configuration lue", check, "agents", selected, now), unreadable, a("section-grid"),
         render_flow(a, configuration, selected),
         render_role(a, configuration, sessions_row, live.get("sessions"), configuration["in_service"], selected, now,
                     setting),
         others)


CLEAN_REASONS = {
    "local-changes": ("avec modifications locales", "conservé", "Modifications locales : rien n’est retiré"),
    "not-merged": ("en cours", "conservé", "Travail en cours : branche pas encore fusionnée"),
    "unpushed": ("non publié", "protégé", "Commits non poussés : exclusion et examen requis"),
    "unpushed-unreported": ("non publié", "protégé",
                            "Commits non poussés : exclusion, mais leur signalement a échoué ; examine-le toi-même"),
    "changed": ("remplacé depuis l’aperçu", "conservé", "Autre espace sous ce nom : rien n’est retiré"),
    "detached": ("sans branche", "conservé", "Aucune branche : examen requis"),
    "kept": ("laissé en place", "conservé", "Laissé en place par la porte"),
}


def _espaces(count, words, state):
    """« 1 espace en cours · conservé », « 2 espaces en cours · conservés »."""
    plural = count > 1
    return "%d espace%s %s · %s%s" % (count, "s" if plural else "", words, state, "s" if plural else "")


def _kept_groups(kept):
    groups = []
    for reason, (words, state, note) in CLEAN_REASONS.items():
        found = [element for element in kept if element["reason"] == reason]
        if found:
            groups.append('<li><strong>%s</strong><small>%s</small></li>' % (_e(_espaces(len(found), words, state)),
                                                                             _e(note)))
    return "".join(groups)


# Why the door makes a work space a candidate (bin/factory-maintain
# clean-worktrees): its branch merged, or untouched past its idle days.
CANDIDATE_WHY = {
    "merged": ("terminé", "Branches fusionnées et publiées · aucun changement local"),
    "idle": ("inactif", "Branches publiées mais non fusionnées, sans commit depuis plus de 7 jours · aucun changement "
             "local"),
}


def _element_line(element):
    if element.get("outcome") == "candidate":
        said = "candidat : %s" % ("branche fusionnée" if element.get("why") == "merged"
                                  else "branche non fusionnée, inactive")
        return "<li>%s — %s%s</li>" % (_e(element["name"]), _e(said), _e(_at_commit(element)))
    if element.get("outcome") == "removed":
        said = "retiré"
    elif element.get("outcome") == "not-removed":
        said = "non retiré : la porte n’a pas pu le retirer"
    else:
        words, state, note = CLEAN_REASONS.get(element.get("reason"), CLEAN_REASONS["kept"])
        said = "%s : %s" % (state, note.split(" :")[0].lower())
    return "<li>%s — %s%s</li>" % (_e(element["name"]), _e(said), _e(_at_commit(element)))


def _at_commit(element):
    return " (commit %s)" % element["sha"][:12] if element.get("sha") else ""


def render_cleanup(a, cleanup):
    """« Nettoyer les espaces inutilisés » (G2, af-f8nlhr): the control that
    previews the scope, the preview itself -- candidates, then what is kept
    and why, each element named in the folded details -- with the
    confirmation of that scope, and the result of the last cleaning, one
    line per element."""
    cleanup = cleanup or {}
    head = '<section class="pn-panel" %s><h2>Nettoyer les espaces inutilisés</h2>' % a("panel")
    alert = '<p class="fa-alert" role="alert" data-usine-alert hidden></p>'
    if cleanup.get("mode") == "apercu":
        preview, error = cleanup.get("preview"), cleanup.get("error")
        if preview is None:
            return head + ('<p class="fa-warn">Aperçu impossible : %s</p><div class="fa-actions">'
                           '<a class="fa-link" href="/usine">Retour</a></div></section>' % _e(error or "porte muette"))
        candidates, kept = preview["candidates"], preview["kept"]
        count = len(candidates)
        found = "".join(
            '<li><strong>%s</strong><small>%s</small></li>'
            % (_e(_espaces(len(group), words + ("s" if len(group) > 1 else ""), "candidat")), _e(note))
            for words, note, group in ((words, note, [e for e in candidates if e.get("why") == why])
                                       for why, (words, note) in CANDIDATE_WHY.items()) if group
        ) or '<li><strong>Aucun espace à retirer</strong></li>'
        listed = ("".join(_element_line(dict(element, outcome="candidate")) for element in candidates)
                  + "".join(_element_line(element) for element in kept))
        confirm, blocked = "", cleanup.get("blocked")
        if count:
            label = "Confirmer 1 candidat" if count == 1 else "Confirmer les %d candidats" % count
            confirm = ('<button type="button" data-usine-action="nettoyer" data-body="%s" data-next="/usine?nettoyage=fait"'
                       ' data-expires-in="%s" data-expired="%s"%s>%s</button>'
                       % (_e(json.dumps({"perimetre": [{"name": e["name"], "sha": e["sha"]} for e in candidates],
                                         "confirm": True})),
                          _e("%g" % cleanup.get("validity_seconds", 300)),
                          _e("Nettoyage indisponible : l’aperçu du périmètre est périmé ; examine-le de nouveau avant "
                             "de confirmer."), " disabled" if blocked else "", label))
        return head + (
            '<p>Périmètre relu à l’instant par la porte de maintenance. Seuls les candidats confirmés sont retirés ; '
            'un périmètre qui change avant ta confirmation est recalculé.</p><ul class="fa-list fa-clean">%s%s</ul>'
            '<details><summary>Voir chaque espace</summary><ul>%s</ul></details>'
            '<div class="fa-actions"><a class="fa-link" href="/usine?nettoyage=apercu">Examiner de nouveau</a>'
            '<a class="fa-link" href="/usine">Annuler</a>%s</div><p class="fa-muted" data-usine-expired%s>%s</p>%s'
            '</section>'
        ) % (found, _kept_groups(kept), listed, confirm, "" if blocked else " hidden", _e(blocked or ""), alert)
    result = cleanup.get("result")
    done = ""
    if result:
        elements = result["elements"]
        removed = sum(1 for e in elements if e["outcome"] == "removed")
        left = len(elements) - removed
        summary = "%d espace%s retiré%s · %d espace%s conservé%s" % (
            removed, "s" if removed > 1 else "", "s" if removed > 1 else "", left, "s" if left > 1 else "",
            "s" if left > 1 else "")
        done = ('<p class="fa-outcome" role="status">Nettoyage du %s : %s.</p>'
                '<details><summary>Résultat par élément</summary><ul>%s</ul></details>'
                % (_e(result["at"]), _e(summary), "".join(_element_line(e) for e in elements)))
    blocked = cleanup.get("blocked")
    return head + (
        '<p>Prévisualiser les candidats et protéger les travaux encore utiles.</p>%s'
        '<form class="fa-actions" method="get" action="/usine"><input type="hidden" name="nettoyage" value="apercu">'
        '<button type="submit"%s>Examiner le périmètre</button></form>%s</section>'
    ) % (done, " disabled" if blocked else "",
         '<p class="fa-muted">%s</p>' % _e(blocked) if blocked else "")


# The gestures of the page (G2, af-f8nlhr): a button `data-usine-action`
# sends its `data-body` (JSON) to POST /api/actions/<action>, as the page's
# own origin, with its session cookie. Done: the page `data-next` is opened,
# which shows what the cockpit read back. Refused or expired: the words of
# the cockpit are shown beside it and nothing is said done; after an
# uncertain outcome the button stays off -- the page says to read the
# source again first, as after a scope recomputed. The focus, taken from the button while it is off,
# comes back to it, or to the words of the refusal when it stays off. A
# button `data-expires-in` (seconds) goes off once what it confirms is
# stale, its `data-expired` words shown in the `data-usine-expired` beside it.
USINE_SCRIPT = """<script>
(function () {
  function say(alert, words) {
    if (!alert) { return; }
    alert.textContent = words;
    alert.hidden = false;
  }
  function settle(button, label, off, alert) {
    button.textContent = label;
    button.disabled = off;
    if (!off) { button.focus(); return; }
    if (alert) { alert.setAttribute('tabindex', '-1'); alert.focus(); }
  }
  document.querySelectorAll('[data-expires-in]').forEach(function (button) {
    var seconds = parseFloat(button.getAttribute('data-expires-in'));
    if (!(seconds > 0)) { return; }
    setTimeout(function () {
      button.disabled = true;
      var holder = button.closest('.pn-panel') || document.body;
      var note = holder.querySelector('[data-usine-expired]');
      if (note) { note.textContent = button.getAttribute('data-expired'); note.hidden = false; }
    }, seconds * 1000);
  });
  document.addEventListener('click', function (event) {
    var button = event.target.closest ? event.target.closest('[data-usine-action]') : null;
    if (!button || button.disabled) { return; }
    var holder = button.closest('.fa-setting, .pn-panel') || document.body;
    var alert = holder.querySelector('[data-usine-alert]');
    var label = button.textContent;
    button.disabled = true;
    button.textContent = 'Envoi à la porte…';
    if (alert) { alert.hidden = true; alert.textContent = ''; }
    fetch('/api/actions/' + button.getAttribute('data-usine-action'), {
      method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
      body: button.getAttribute('data-body')
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (response.ok && body.ok) { window.location.assign(button.getAttribute('data-next')); return; }
        say(alert, body.error || ('Le cockpit a refusé la commande (' + response.status + ').'));
        // A scope recomputed asks a new preview: this one confirms no more.
        settle(button, label, body.incertain === true || Array.isArray(body.perimetre), alert);
      });
    }, function () {
      say(alert, 'Le cockpit ne répond pas : l’issue de la commande est incertaine. '
        + 'Revérifie la section avant de réessayer.');
      settle(button, label, true, alert);
    });
  });
})();
</script>"""


def render_unavailable(a, actions_html):
    return (
        '<section class="pn-panel" %s><h2>Suspension, reprise et arrêt</h2><p>La VM héberge l’usine. Fermer ou '
        'éteindre ce PC client n’arrête pas la VM.</p><div class="fa-actions">'
        '<button type="button" disabled>Demander la suspension</button>'
        '<button type="button" disabled>Préparer l’arrêt de la machine</button></div>'
        '<p class="fa-muted">Indisponible : l’arrêt propre et la reprise vérifiée ne sont pas encore raccordés.</p>'
        '<div class="fa-legacy">%s</div></section>'
    ) % (a("panel"), actions_html)


def render_factory_page(view):
    """The main part of the page, as a function of its anchors."""
    def draw(a):
        return (
            '<div class="pn-head"><h1 %s>Usine</h1><p class="fa-sub" %s>Ressources, connexions et réglages de '
            'l’environnement d’exécution.</p></div>%s<div class="fa-two" %s>%s</div>%s'
            '<div class="fa-legacy">%s</div>%s'
        ) % (a("h1"), a("page-lead"), render_machine(a, view["machine"], view["selected"], view["now"]), a("section-grid"),
             render_connections(a, view["connections"], view["live"], view["notify_configured"], view["now"],
                                view["selected"]) + render_providers(a, view["providers"], view["selected"], view["now"]),
             render_agents(a, view["agents"], view["live"], view["selected"], view["now"], view.get("setting")),
             view["health_html"], render_unavailable(a, view["actions_html"]) + render_cleanup(a, view.get("cleanup"))
             + USINE_SCRIPT)
    return draw


CSS = """
.fa-setting{margin-top:14px}
.fa-setting fieldset{border:1px solid var(--line);border-radius:8px;margin:0 0 10px;padding:10px 12px;min-width:0}
.fa-setting legend{padding:0 4px;font-size:13px;color:var(--pn-muted-text)}
.fa-choice{display:block;padding:8px 0;overflow-wrap:anywhere}
.fa-choice small{display:block;margin-left:26px;font-size:12px;color:var(--pn-muted-text)}
.fa-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:10px}
.fa-link{color:var(--ink);text-underline-offset:3px}
.fa-outcome{border-left:3px solid var(--accent);padding:6px 10px;margin:12px 0}
.fa-alert{border-left:3px solid var(--pn-warn-text);color:var(--pn-warn-text);padding:6px 10px;margin:12px 0}
.fa-clean li{display:block;padding:10px 0;border-bottom:1px solid var(--line)}
.fa-clean li:last-child{border-bottom:0}
.fa-clean small{display:block;font-size:12px;color:var(--pn-muted-text);margin-top:3px}
.fa-sub{margin:0 0 20px;color:var(--pn-muted-text)}
.fa-muted{color:var(--pn-muted-text);font-size:13px}
.fa-warn{color:var(--pn-warn-text)}
.fa-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.fa-head h2{margin:0 0 6px}
.fa-head>div{min-width:0}
.fa-check{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.fa-chip{border:1px solid var(--line);border-radius:999px;padding:5px 10px;font-size:12px}
.fa-chip.fa-stale{color:var(--pn-muted-text)}
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
.fa-row.fa-stale,.fa-row.fa-unknown,.fa-row.fa-off{color:var(--pn-muted-text)}
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
