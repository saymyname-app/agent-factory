"""The procedure of the settings that ask the operator's hand on the VM (I,
af-cp4fzd; Spec af-fgcw0d, user stories 61 and 98: « une procédure courte
adaptée à la VM pour les réglages Pushover, heartbeat et accès qui
nécessitent mon action, afin de réutiliser les comptes existants sans achat
ou compte supplémentaire imposé » ; « les secrets restent dans des fichiers
privés hors dépôt sur l'hôte qui les utilise »). Served at
GET /usine/procedure, linked from the section « Accès ».

It names the files of this host -- where the cockpit reads its local
settings and, once set, its secret files -- and the commands of
bin/cockpit-setup-wizard that write them. It never reads a secret file and
shows no value of one: a path is said, never what it holds. Pure function --
no I/O.
"""
import html

TITLE = "Procédure des réglages sur la VM"
# Where the procedure proposes the secret files, when none is set yet: in
# the home of the account that runs the cockpit on the VM, outside every
# repository, readable by that account alone.
SUGGESTED_PUSHOVER_FILE = "~/.config/agent-factory/pushover.json"
SUGGESTED_HEARTBEAT_FILE = "~/.config/agent-factory/heartbeat-url"
WIZARD = "bin/cockpit-setup-wizard"
# The check « Usine muette » on Healthchecks.io: a heartbeat every five
# minutes, the alert after ten more of silence -- fifteen at most (user
# story 67).
PERIOD_MINUTES = 5
GRACE_MINUTES = 10

CSS = """
.pr-steps{display:grid;gap:14px;margin:0;padding:0;list-style:none}
.pr-steps>li{min-width:0}
.pr-state{margin:0 0 8px;color:var(--pn-muted-text,var(--muted))}
.pr-steps ol{margin:6px 0 0;padding-left:1.4em}
.pr-steps ol li{margin:4px 0}
.pr-steps code,.pr-cmd{font-family:var(--mono);font-size:.93em;overflow-wrap:anywhere}
.pr-cmd{display:block;margin:6px 0;padding:8px 10px;border:1px solid var(--line);border-radius:8px;
  background:var(--surface-2);white-space:pre-wrap}
.pr-back{margin:14px 0 0}
"""


def _code(text):
    return "<code>%s</code>" % html.escape(text)


def _cmd(text):
    return '<span class="pr-cmd">%s</span>' % html.escape(text)


def _state(path, ready, what):
    """Whether the setting is in place on this host: its file set and read
    by the cockpit (``ready``), set but absent or invalid, or not set."""
    if path and ready:
        return '<p class="pr-state">En place sur cette VM : %s lu dans %s.</p>' % (html.escape(what), _code(path))
    if path:
        return ('<p class="pr-state">Pas en place sur cette VM : %s est attendu dans %s, mais ce fichier est '
                'absent ou invalide.</p>' % (html.escape(what), _code(path)))
    return '<p class="pr-state">Pas encore en place sur cette VM : %s absent.</p>' % html.escape(what)


def _step(title, state, items):
    return '<li class="pn-panel"><h2>%s</h2>%s<ol>%s</ol></li>' % (
        html.escape(title), state, "".join("<li>%s</li>" % item for item in items))


def render_procedure(settings):
    """``settings``: what this host says of itself, paths only --
    ``local_config`` (the local settings file of the cockpit),
    ``pushover_file`` and ``heartbeat_file`` (the secret files, empty when
    unset), ``pushover_ready`` and ``heartbeat_ready`` (whether the cockpit
    reads them), ``public_url`` (the address the cockpit is opened at,
    empty when unset), ``port`` (the cockpit's own port),
    ``supervisor_port`` (the port of the supervisor it reads)."""
    local = settings.get("local_config") or ""
    pushover = settings.get("pushover_file") or ""
    heartbeat = settings.get("heartbeat_file") or ""
    public_url = settings.get("public_url") or ""
    port = settings.get("port") or 0
    supervisor_port = settings.get("supervisor_port") or 0
    pushover_path = pushover or SUGGESTED_PUSHOVER_FILE
    heartbeat_path = heartbeat or SUGGESTED_HEARTBEAT_FILE
    https = public_url.startswith("https://")

    intro = (
        "<p>Trois réglages demandent ta main, une fois, sur la VM qui fait tourner l’usine. Ils réutilisent "
        "tes comptes existants (Pushover, Healthchecks.io, Tailscale) : aucun achat ni compte de plus. "
        "Chaque commande se lance dans le dépôt de l’usine, sur la VM. Les secrets vont dans des fichiers "
        "privés de la VM, hors de tout dépôt, lisibles par ton seul compte : le cockpit les lit, ne les "
        "affiche jamais et ne les écrit dans aucun journal.</p>"
        "<p>Les chemins choisis sont écrits dans le fichier de réglages local du cockpit, %s, "
        "qui n’est pas versionné.</p>"
    ) % _code(local or "cockpit-local.json")

    steps = [
        _step(
            "1. Notifications iPhone (Pushover)",
            _state(pushover, settings.get("pushover_ready"), "le fichier de secrets Pushover"),
            [
                "Dans ton compte Pushover, relève le jeton de l’application, ta clé utilisateur et la clé "
                "de chiffrement de bout en bout que montre l’app iPhone.",
                "Écris-les dans le fichier privé, sans les taper en argument : la commande les lit sur son "
                "entrée, au format JSON (token, user_key, e2e_key)."
                + _cmd("%s pushover-secrets --path %s" % (WIZARD, pushover_path)),
                "Ajoute %s au fichier de réglages local, puis redémarre le cockpit."
                % _code('"pushover_secrets_file": "%s"' % pushover_path),
            ],
        ),
        _step(
            "2. Signal de vie de l’usine (heartbeat Healthchecks.io)",
            _state(heartbeat, settings.get("heartbeat_ready"), "l’adresse du signal de vie"),
            [
                "Dans ton compte Healthchecks.io, crée ou garde le contrôle « Usine muette » : période "
                "%d min, délai de grâce %d min, notification de retour désactivée, alerte Pushover en "
                "priorité 1 répétée toutes les deux heures. Une VM muette t’alerte ainsi en quinze minutes "
                "au plus." % (PERIOD_MINUTES, GRACE_MINUTES),
                "Écris l’adresse de ping du contrôle dans le fichier privé ; la commande la lit sur son "
                "entrée." + _cmd("%s heartbeat-secret --path %s" % (WIZARD, heartbeat_path)),
                "Vérifie les paramètres du contrôle."
                + _cmd("%s healthchecks-check --period-minutes %d --grace-minutes %d --up-notifications off"
                       % (WIZARD, PERIOD_MINUTES, GRACE_MINUTES)),
                "Ajoute %s au fichier de réglages local, puis redémarre le cockpit. Le signal ne part que "
                "lorsque le superviseur et les tickets sont lus à jour." % _code(
                    '"heartbeat_url_file": "%s"' % heartbeat_path),
            ],
        ),
        _step(
            "3. Accès depuis le PC et l’iPhone (Tailscale Serve)",
            ('<p class="pr-state">En place : le cockpit s’ouvre à %s.</p>' % _code(public_url)) if https
            else '<p class="pr-state">Pas encore en place : aucune adresse HTTPS configurée.</p>',
            [
                "Sur la VM, expose le cockpit à ton réseau Tailscale seul, en HTTPS. La commande refuse "
                "Funnel (l’accès public) et le port du superviseur (%s, celui que le cockpit lit), qui "
                "n’est jamais exposé." % supervisor_port
                + _cmd("%s serve --target-port %s --gc-port %s" % (WIZARD, port, supervisor_port)),
                "Ajoute au fichier de réglages local l’adresse HTTPS du nœud de l’usine, en %s et %s, et "
                "ton identité Tailscale en %s : le cockpit refuse toute autre identité, en lecture comme en "
                "action." % (_code('"public_url"'), _code('"allowed_origin"'), _code('"benjamin_login"')),
                "Redémarre le cockpit, puis ouvre cette adresse depuis le PC et depuis l’iPhone.",
            ],
        ),
        _step(
            "4. Vérifier",
            "",
            [
                "Sur la page Usine, la santé ne signale plus de secret absent ni d’adresse manquante, et la "
                "section « Accès » donne l’adresse HTTPS.",
                "La réception réelle sur l’iPhone et l’alerte d’une VM muette restent à essayer une fois, "
                "avec toi.",
            ],
        ),
    ]
    return (
        '<div class="pn-head"><h1>%s</h1></div>'
        '<section class="pn-panel">%s</section>'
        '<ol class="pr-steps">%s</ol>'
        '<p class="pr-back"><a href="/usine#acces">Retour à la page Usine</a></p>'
    ) % (html.escape(TITLE), intro, "".join(steps))
