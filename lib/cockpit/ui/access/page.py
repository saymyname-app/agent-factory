"""Renders the "Accès" zone (spec af-oohx2x §"Accès et sécurité", .71,
.96): who may act from this cockpit, and until when the Tailscale key
that makes it reachable from the iPhone is valid. Pure function -- no I/O.
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


def _line(level, text):
    return '<div class="hl"><span class="lvl %s"><i></i></span><span>%s</span></div>' % (level, html.escape(text))


def _date(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%d/%m/%Y")


def render_access_zone(benjamin_login, tailscale_row=None, now=None):
    """``tailscale_row``: the read model's "tailscale" row, or ``None``
    when this cockpit does not read Tailscale at all (the key line is then
    left out rather than guessed)."""
    lines = [
        _line("ok", ACTIONS_TEXT % benjamin_login) if benjamin_login else _line("normal", READ_ONLY_TEXT)
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
    return (
        '<section class="zone cockpit-access" id="acces">'
        '<div class="zone-h"><h2>%s</h2></div>'
        '<div class="health"><div class="hlist">%s</div></div>'
        "</section>\n"
    ) % (html.escape(SECTION_TITLE), "".join(lines))
