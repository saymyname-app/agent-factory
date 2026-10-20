"""The destination Usine of Panorama: the machine the factory runs on, the
sources the cockpit reads, the agents seen at work, and the zones that
change the factory (stop, access) the cockpit already had.

It follows the Usine reference (prototypes/c01-complete/frozen-panorama-
factory at 632deea) for what the cockpit can read for real; what it cannot
read yet (provider quotas, the configuration form, the clean-up) is left
out rather than drawn with example values.

Intent (Benjamin, his words, 2026-10-19 19:20 Paris): « enchaîne
directement sur Runs puis Usine. »
Mechanism (agent interpretation): built directly, outside the paused convoy
af-pqfxmd; the machine is read where the cockpit runs, on the factory's VM.
"""
import html
import os
import platform
import shutil
import socket
from datetime import datetime

from account_home import account_home

from cockpit.core.freshness import FRESH, STALE
from cockpit.core.readmodel import PARIS

GIB = 1024 ** 3
FRESHNESS_TEXT = {FRESH: "À jour", STALE: "En retard"}
ROLE_TEXT = (("author", "Auteur livraison"), ("reviewer", "Relecteur livraison"), ("evaluator", "Évaluateur livraison"))


def _e(value):
    return html.escape(str(value), quote=True)


def _go(value):
    return ("%.1f" % (value / GIB)).replace(".", ",")


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


def _meter(label, value, percent, note):
    width = 0 if percent is None else max(0, min(100, percent))
    return ('<div class="fa-meter"><div class="fa-meter-head"><span>%s</span><strong>%s</strong></div>'
            '<div class="fa-bar"><span style="width:%d%%"></span></div><small>%s</small></div>'
            % (_e(label), _e(value), width, _e(note)))


def render_machine(machine, now):
    cores = machine["cores"] or 0
    load = machine["load"]
    cpu = None if load is None or not cores else round(100 * load / cores)
    mem_t, mem_u = machine["mem_total"], machine["mem_used"]
    disk_t, disk_u = machine["disk_total"], machine["disk_used"]
    disk = None if not disk_t else round(100 * disk_u / disk_t)
    meters = (
        _meter("Processeur", "—" if cpu is None else "%d %%" % cpu, cpu,
               "Charge non lue" if load is None else "Charge moyenne : %s / %d cœurs" % (("%.1f" % load).replace(".", ","), cores))
        + _meter("Mémoire", "—" if mem_u is None else "%s Go" % _go(mem_u),
                 None if not mem_t else 100 * mem_u / mem_t,
                 "Mémoire non lue" if not mem_t else "%s Go de capacité totale" % _go(mem_t))
        + _meter("Disque", "—" if disk is None else "%d %%" % disk, disk,
                 "Disque non lu" if disk is None else "%s Go utilisés sur %s Go" % (_go(disk_u), _go(disk_t)))
    )
    summary = "%s · %s · %d cœurs%s" % (machine["host"], machine["system"], cores,
                                       " · %s Go de mémoire" % _go(mem_t) if mem_t else "")
    return ('<section class="pn-panel"><div class="fa-head"><div><h2>Machine d’exécution</h2><p class="fa-muted">%s</p></div>'
            '<span class="fa-chip">Lu à %s (Paris)</span></div><div class="fa-meters">%s</div></section>'
            % (_e(summary), datetime.fromtimestamp(now, tz=PARIS).strftime("%H:%M"), meters))


def render_sources(snapshot, notify_configured):
    """« Connexions »: every source the cockpit reads, its freshness and
    when it was last read -- what the cockpit really knows of each."""
    rows = []
    for name, row in sorted(snapshot.items(), key=lambda item: item[1].get("display_name") or item[0]):
        state = row.get("freshness")
        read_at = row.get("read_at")
        when = datetime.fromtimestamp(read_at, tz=PARIS).strftime("%H:%M") if read_at else "jamais lu"
        tone = "ok" if state == FRESH else ("warn" if state == STALE else "bad")
        rows.append('<li class="fa-row"><span class="fa-dot %s"></span><div><strong>%s</strong><small>%s</small></div>'
                    '<span class="fa-val">%s</span></li>'
                    % (tone, _e((row.get("display_name") or name).capitalize()), _e(FRESHNESS_TEXT.get(state, "Inconnu")),
                       _e(when)))
    rows.append('<li class="fa-row"><span class="fa-dot %s"></span><div><strong>Notifications iPhone</strong>'
                '<small>Envoi Pushover</small></div><span class="fa-val">%s</span></li>'
                % ("ok" if notify_configured else "warn", "Configurées" if notify_configured else "Non configurées"))
    return ('<section class="pn-panel"><h2>Connexions</h2><ul class="fa-list">%s</ul>'
            '<p class="fa-muted fa-note">Heure de la dernière lecture réussie de chaque source (Paris).</p></section>'
            % "".join(rows))


def render_agents(runs, sessions_row):
    """« Agents dans le workflow »: the model each role ran on, as seen on
    the most recent run that launched it, and the sessions at work now."""
    seen = {}
    for run in runs or []:
        for role, _ in ROLE_TEXT:
            record = (run.get("models") or {}).get(role)
            if role not in seen and isinstance(record, dict):
                seen[role] = (record, run)
    rows = []
    for role, label in ROLE_TEXT:
        if role in seen:
            record, run = seen[role]
            rows.append('<li class="fa-row"><span class="fa-dot ok"></span><div><strong>%s</strong><small>%s · vu sur '
                        '<a href="%s">%s</a></small></div><span class="fa-val">%s</span></li>'
                        % (_e(label), _e(record.get("provider") or "fournisseur inconnu"), _e(run["href"]),
                           _e(run["ticket"]), _e(record.get("model") or "?")))
        else:
            rows.append('<li class="fa-row"><span class="fa-dot"></span><div><strong>%s</strong><small>Aucun run lu ne '
                        'l’a lancé</small></div><span class="fa-val">—</span></li>' % _e(label))
    value = (sessions_row or {}).get("value") or {}
    sessions = value.get("sessions") if isinstance(value, dict) else None
    at_work = ("Agents de livraison au travail maintenant : %d" % len(sessions)) if sessions is not None \
        else "Agents au travail : non lus"
    return ('<section class="pn-panel"><h2>Agents dans le workflow</h2><p class="fa-muted">%s · le détail de chaque '
            'livraison est dans <a href="/runs">Runs</a>.</p><ul class="fa-list">%s</ul></section>'
            % (_e(at_work), "".join(rows)))


def render_factory_page(machine, snapshot, runs, notify_configured, health_html, actions_html, now):
    return ('<div class="pn-head"><h1>Usine</h1><p class="fa-sub">Ressources, connexions et réglages de '
            'l’environnement d’exécution.</p></div>%s<div class="fa-two">%s%s</div>'
            '<section class="pn-panel fa-legacy">%s</section>'
            '<section class="pn-panel fa-legacy"><h2>Suspension, arrêt et accès</h2><p class="fa-muted">La VM héberge '
            'l’usine. Fermer ou éteindre ce PC n’arrête pas la VM.</p>%s</section>'
            % (render_machine(machine, now), render_sources(snapshot, notify_configured),
               render_agents(runs, snapshot.get("sessions")), health_html, actions_html))


CSS = """
.fa-sub{margin:0 0 20px;color:var(--pn-muted-text)}
.fa-muted{color:var(--pn-muted-text);font-size:13px}
.fa-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.fa-head h2{margin:0 0 6px}
.fa-chip{border:1px solid var(--line);border-radius:999px;padding:5px 10px;font-size:12px}
.fa-meters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.fa-meter-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.fa-meter-head strong{font-size:22px}
.fa-bar{height:6px;border-radius:6px;background:var(--line);overflow:hidden;margin-bottom:10px}
.fa-bar span{display:block;height:100%;background:var(--accent)}
.fa-meter small{font-size:12px;color:var(--pn-muted-text)}
.fa-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.fa-two .pn-panel{margin-bottom:20px}
.fa-list{list-style:none;margin:0;padding:0}
.fa-row{display:grid;grid-template-columns:12px 1fr auto;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.fa-row:last-child{border-bottom:0}
.fa-row strong{display:block;font-size:14px}.fa-row small{display:block;font-size:12px;color:var(--pn-muted-text);margin-top:3px}
.fa-row a{color:inherit}
.fa-val{font-size:14px;white-space:nowrap}
.fa-dot{width:8px;height:8px;border-radius:100%;background:var(--line)}
.fa-dot.ok{background:var(--ok)}.fa-dot.warn{background:var(--warn)}.fa-dot.bad{background:#d05a5a}
.fa-note{margin-top:12px!important}
.fa-legacy section{margin:12px 0 0}
.fa-legacy,.fa-legacy *{white-space:normal;overflow-wrap:anywhere;min-width:0}
.fa-legacy h2{font-size:19px}
@media (max-width:900px){.fa-two,.fa-meters{grid-template-columns:1fr}}
"""
