"""Renders the journal des envois and the "envoyer une notification de
test" button (spec af-oohx2x §"Notifications", .60: "demande, niveau,
heure, accepté ou échec"). Pure functions over
:meth:`cockpit.notify.service.NotifyService.journal_entries` -- no I/O.
The button's click is handled by the page's one action script
(:data:`cockpit.ui.actions.render.SCRIPT`).
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS

SECTION_TITLE = "Journal des envois"
EMPTY_TEXT = "Aucun envoi pour le moment."
INACTIVE_TEXT = "Notifications inactives : rien n'est envoyé tant que le fichier de secrets est absent."

_KIND_LABELS = {
    "initial": "premier envoi",
    "escalade": "montée de niveau",
    "echeance": "échéance du report",
    "rappel": "rappel",
    "resolu": "résolue",
    "groupe": "regroupé",
    "test": "test",
}
_PRIORITY_LABELS = {1: "Urgent", 0: "À faire"}
_NO_REQUEST_LABELS = {"test": "Notification de test", "groupe": "Plusieurs demandes regroupées", "resolu": "Demande urgente résolue"}

TEST_BUTTON_HTML = (
    '<button type="button" class="btn cockpit-action" data-action="notifier_test">'
    "Envoyer une notification de test</button>"
)


def _when(epoch):
    if epoch is None:
        return ""
    return "<time>%s</time>" % datetime.fromtimestamp(epoch, tz=PARIS).strftime("%d/%m %H:%M")


def render_journal(entries):
    """One row per send, newest first as given."""
    if not entries:
        return '<p class="muted cockpit-notify-empty">%s</p>' % html.escape(EMPTY_TEXT)
    rows = []
    for entry in entries:
        kind = entry.get("kind") or ""
        ok = bool(entry.get("ok"))
        what = entry.get("quoi") or _NO_REQUEST_LABELS.get(kind) or "Demande"
        rows.append(
            '<div class="cockpit-journal-entry cockpit-notify-entry" data-req-id="%s" data-ok="%s">'
            '<div class="cockpit-journal-demande">%s</div>'
            '<div class="meta"><span>%s</span><span>%s</span><span>%s</span>'
            '<span class="chip %s">%s</span></div>'
            "</div>"
            % (
                html.escape(str(entry.get("req_id") or "")),
                "true" if ok else "false",
                html.escape(what),
                _when(entry.get("quand")),
                html.escape(_PRIORITY_LABELS.get(entry.get("priority"), "")),
                html.escape(_KIND_LABELS.get(kind, kind)),
                "ack" if ok else "bloque",
                "accepté" if ok else "échec",
            )
        )
    return '<div class="panel cockpit-notify-journal">%s</div>' % "".join(rows)


def render_envois_section(entries, configured):
    """The section of the journal page: the test button (spec .60), then
    every send. ``configured``: false without the secrets file -- the
    section then says nothing can be sent rather than offer a button that
    would only fail."""
    head = TEST_BUTTON_HTML if configured else ""
    note = "" if configured else '<p class="muted cockpit-notify-inactive">%s</p>' % html.escape(INACTIVE_TEXT)
    return (
        '<section class="zone cockpit-notify" data-configured="%s">'
        '<div class="zone-h"><h2>%s</h2>%s</div>%s%s</section>\n'
    ) % ("true" if configured else "false", html.escape(SECTION_TITLE), head, note, render_journal(entries))
