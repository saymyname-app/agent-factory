"""Renders the journal des demandes résolues (T15, af-icxjc4 — spec
af-oohx2x .18). Pure function of a list of
:class:`~cockpit.ui.journal.entries.JournalEntry` — no I/O, same shape as
``ui/home/page.py``'s ``render_requests_section``.
"""
import html

SECTION_TITLE = "Journal des demandes résolues"
EMPTY_TEXT = "Aucune demande résolue pour l'instant."


def render_journal_section(entries):
    if not entries:
        return (
            '<section class="cockpit-journal" data-state="empty">'
            "<h2>%s</h2><p class=\"cockpit-journal-status\">%s</p></section>\n"
        ) % (html.escape(SECTION_TITLE), html.escape(EMPTY_TEXT))

    rows = "".join(_render_entry(e) for e in entries)
    return (
        '<section class="cockpit-journal" data-state="filled">'
        "<h2>%s</h2><ul class=\"cockpit-journal-list\">%s</ul></section>\n"
    ) % (html.escape(SECTION_TITLE), rows)


def _render_entry(entry):
    return (
        '<li class="cockpit-journal-entry" data-bead-id="%s" data-voie="%s">'
        "<p class=\"cockpit-journal-quoi\">%s</p>"
        "<p class=\"cockpit-journal-meta\">%s · %s · %s</p>"
        "</li>"
    ) % (
        html.escape(entry.bead_id),
        html.escape(entry.voie),
        html.escape(entry.quoi),
        html.escape(entry.quand or "??:??"),
        html.escape(entry.par or "?"),
        html.escape(entry.voie),
    )
