"""The destination « Rituels » of B/Panorama (Spec af-2zseit, user stories
167 to 175; prototypes/c01-complete/frozen-panorama-rituals), built
directly from T41's fold (af-r4hrt7, commit 8ef15917), keeping only what
has a real source.

    rituals = read_rituals(path)
    main_html = render_rituals(rituals, anchors)

The catalogue -- the five rituals of the Spec, each what it is for and how
it is launched -- is the cockpit's own. When each last ran comes from the
rituals file of the Factory (``docs/rituals.toml``, read by
``bin/rituals-status``): a ritual whose id starts with the key of a card
(``architecture:factory`` for « Revue d’architecture ») says there its last
run, or that it is paused and why. A card the file names nothing for says
« non renseigné ». Launching a ritual and the pages of a ritual under way
have no door yet: they are left out, not drawn with example values.
"""
import html
import tomllib
from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

# key, title, what it is for, how it is launched, how its last run is
# named (and the gender of « non renseigné »).
CATALOGUE = (
    ("release", "Préparer la prochaine release",
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

# The scope after the colon of a ritual id, as the cockpit names it.
SCOPES = {"factory": "Usine"}


def read_rituals(path):
    """The ``[[ritual]]`` entries of the rituals file at ``path``: a list,
    or None when the file cannot be read (no path, missing, not TOML)."""
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            rituals = tomllib.load(handle).get("ritual")
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return [ritual for ritual in rituals if isinstance(ritual, dict)] if isinstance(rituals, list) else None


def _date(value):
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(PARIS)
    return moment.strftime("%d/%m/%Y")


def _last_lines(key, name, gender, rituals):
    """The lines of a card on when it last ran, from the rituals file."""
    if rituals is None:
        return ["%s : inconnu%s, docs/rituals.toml n’est pas lu" % (name, gender)]
    lines = []
    for ritual in rituals:
        ritual_id = str(ritual.get("id") or "")
        if ritual_id.split(":", 1)[0] != key:
            continue
        scope = ritual_id.split(":", 1)[1] if ":" in ritual_id else ""
        label = "%s (%s)" % (name, SCOPES.get(scope, scope)) if scope else name
        last = ritual.get("last_done")
        if last == "paused":
            line = "%s : en pause · %s" % (label, ritual.get("paused_reason") or "sans raison écrite")
            if ritual.get("resume_when"):
                line += " · reprise : %s" % ritual["resume_when"]
        elif last:
            line = "%s : %s" % (label, _date(last))
        else:
            line = "%s : non renseigné%s" % (label, gender)
        if isinstance(ritual.get("threshold"), int) and ritual.get("kind") == "pr_threshold":
            line += " · %sdue après %d PR fusionnées dans %s" % (
                "puis " if last == "paused" else "", ritual["threshold"], ritual.get("base_branch") or "main")
        lines.append(line)
    return lines or ["%s : non renseigné%s" % (name, gender)]


def _e(text):
    return html.escape(str(text))


def render_rituals(rituals, anchors):
    """The ``main`` of the destination, numbered by ``anchors`` as the
    reference numbers its parts; ``rituals``: what :func:`read_rituals`
    returned."""
    parts = ['<h1 %s>Rituels</h1>' % anchors("h1"),
             '<p class="pn-page-lead" %s>Une revue produit des propositions. Tu choisis lesquelles faire préparer.</p>'
             % anchors("page-lead")]
    cards = []
    grid = anchors("ritual-grid")
    for key, title, purpose, label, name, gender in CATALOGUE:
        panel, small, h2, p = anchors("panel"), anchors("small"), anchors("h2"), anchors("p")
        last = "".join("<small %s>%s</small>" % (anchors("small"), _e(line))
                       for line in _last_lines(key, name, gender, rituals))
        cards.append('<section class="pn-panel pn-ritual-card" %s><small %s>%s</small><h2 %s>%s</h2><p %s>%s</p>%s'
                     "</section>" % (panel, small, _e(label), h2, _e(title), p, _e(purpose), last))
    parts.append('<div class="pn-ritual-grid" %s>%s</div>' % (grid, "".join(cards)))
    parts.append('<p class="pn-unwired">Lancer un rituel n’est pas encore raccordé à cette vue : rien n’est lancé '
                 "ni enregistré d’ici.</p>")
    return '<div class="pn-rituals">%s</div>' % "".join(parts)


# The reference's type and spacing on the tokens of the shell (T41): a
# muted text is --pn-muted-text, long titles and words wrap in their panel.
CSS = """
.pn-rituals h1{font-size:27px;margin:0 0 20px}
.pn-rituals h2{font-size:19px;margin:12px 0;overflow-wrap:anywhere}
.pn-rituals p{line-height:1.5;margin:0 0 12px;overflow-wrap:anywhere}
.pn-rituals small{display:block;font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.pn-rituals .pn-page-lead{color:var(--pn-muted-text);margin:-10px 0 24px;line-height:1.6}
.pn-ritual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.pn-ritual-grid>*{min-width:0}
.pn-ritual-card{display:flex;flex-direction:column;padding:24px;margin:0}
.pn-ritual-card p{color:var(--pn-muted-text);font-size:14px;flex:1}
.pn-ritual-card small+small{margin-top:6px}
.pn-rituals .pn-unwired{margin:18px 0 0;font-size:13px;color:var(--pn-muted-text)}
@media (max-width:900px){.pn-ritual-grid{grid-template-columns:minmax(0,1fr)}}
@media (max-width:800px){.pn-rituals h1{font-size:24px}.pn-ritual-card{padding:18px}}
"""
