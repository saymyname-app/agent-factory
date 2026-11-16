"""Renders the "Accès" zone (spec af-oohx2x §"Accès et sécurité", .71,
.96): who may act from this cockpit, and until when the Tailscale key
that makes it reachable from the iPhone is valid; the HTTPS address it is
opened at from the PC and the iPhone, and the procedure of the settings
that ask the operator's hand on the VM (I, af-cp4fzd; Spec af-fgcw0d,
user stories 61 and 93). Pure function -- no I/O.
"""
import html
from datetime import datetime, timezone

from cockpit.access.tailscale import WARNING_WINDOW_SECONDS

SECTION_TITLE = "Accès"
READ_ONLY_TEXT = "Lecture seule : aucune identité n'est configurée, aucune action n'est possible d'ici."
ACTIONS_TEXT = "Les actions sont réservées à %s, reconnu par Tailscale."
KEY_UNKNOWN_TEXT = "Date d'expiration de la clé Tailscale inconnue — Tailscale ne répond pas."
KEY_NEVER_TEXT = "La clé Tailscale n'expire pas."
KEY_VALID_TEXT = "Clé Tailscale valable jusqu'au %s."
KEY_SOON_TEXT = "La clé Tailscale expire le %s : à renouveler."
KEY_EXPIRED_TEXT = "La clé Tailscale a expiré le %s."
ADDRESS_TEXT = "Adresse du cockpit, depuis le PC et l’iPhone : "
NO_ADDRESS_TEXT = "Adresse HTTPS non configurée : le cockpit ne s’ouvre que sur la VM."
# The page of the procedure (cockpit.ui.access.procedure).
PROCEDURE_PATH = "/usine/procedure"
PROCEDURE_LINK_TEXT = "Procédure des réglages sur la VM"
PROCEDURE_HINT = " : Pushover, signal de vie et accès."


def _line(level, text):
    return '<div class="hl"><span class="lvl %s"><i></i></span><span>%s</span></div>' % (level, html.escape(text))


def _date(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%d/%m/%Y")


def _address_line(public_url):
    """The HTTPS address the cockpit is opened at, as a link; said not
    configured when it has none (a local address is not one to give)."""
    if not public_url or not public_url.startswith("https://"):
        return _line("info", NO_ADDRESS_TEXT)
    url = html.escape(public_url, quote=True)
    return '<div class="hl"><span class="lvl ok"><i></i></span><span>%s<a href="%s">%s</a></span></div>' % (
        html.escape(ADDRESS_TEXT), url, url)


def _procedure_line():
    return '<div class="hl"><span class="lvl info"><i></i></span><span><a href="%s">%s</a>%s</span></div>' % (
        PROCEDURE_PATH, html.escape(PROCEDURE_LINK_TEXT), html.escape(PROCEDURE_HINT))


def render_access_zone(benjamin_login, tailscale_row=None, now=None, public_url=""):
    """``tailscale_row``: the read model's "tailscale" row, or ``None``
    when this cockpit does not read Tailscale at all (the key line is then
    left out rather than guessed). ``public_url``: the address the operator
    opens the cockpit at (COCKPIT_PUBLIC_URL)."""
    lines = [
        _line("ok", ACTIONS_TEXT % benjamin_login) if benjamin_login else _line("normal", READ_ONLY_TEXT),
        _address_line(public_url),
    ]
    if tailscale_row is not None:
        value = tailscale_row.get("value")
        if value is None or tailscale_row.get("freshness") == "unknown":
            lines.append(_line("info", KEY_UNKNOWN_TEXT))
        else:
            expiry = value.get("key_expiry")
            if expiry is None:
                lines.append(_line("ok", KEY_NEVER_TEXT))
            elif now is not None and expiry <= now:
                lines.append(_line("urgent", KEY_EXPIRED_TEXT % _date(expiry)))
            elif now is not None and expiry - now <= WARNING_WINDOW_SECONDS:
                lines.append(_line("normal", KEY_SOON_TEXT % _date(expiry)))
            else:
                lines.append(_line("ok", KEY_VALID_TEXT % _date(expiry)))
    lines.append(_procedure_line())
    return (
        '<section class="zone cockpit-access" id="acces">'
        '<div class="zone-h"><h2>%s</h2></div>'
        '<div class="health"><div class="hlist">%s</div></div>'
        "</section>\n"
    ) % (html.escape(SECTION_TITLE), "\n".join(lines))
