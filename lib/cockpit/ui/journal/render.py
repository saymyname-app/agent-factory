"""Renders the journal des demandes résolues (T15, af-icxjc4 — spec
af-oohx2x .18: "quoi, quand, par qui ou quelle voie"). Pure function of a
list of :class:`~cockpit.ui.journal.entries.JournalEntry` — no I/O.

Intent (Benjamin, his words, 2026-10-06): « affiche tel quel ».
Mechanism (agent interpretation): the journal shows a request's and a
resolution's text exactly as its producer wrote it, without the main-text
control (:mod:`cockpit.text.validate`) the inbox applies — it is a record
of what happened, not a request to act on, and that control hid nearly
every entry written before it existed. It does NOT mean the inbox shows
unchecked text. To undo: pass both texts through ``violations`` here.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS

SECTION_TITLE = "Journal des demandes résolues"
EMPTY_TEXT = "Aucune demande résolue pour l'instant."
UNDATED_TEXT = "date inconnue"
NO_REQUEST_TEXT = "Demande sans texte enregistré"

# How each trace reads to Benjamin; the writer's own name stays in details.
VOIE_LABELS = {
    "escalation-door": "réponse à une demande",
    "proposal-door": "décision sur une proposition",
    "cockpit": "action dans le cockpit",
    "clear": "effacée sans réponse",
}

CSS = """
.cockpit-journal-entry{display:grid;gap:4px;padding:12px 14px;border-top:1px solid var(--line);font-size:var(--fs-s)}
.cockpit-journal-entry:first-child{border-top:0}
.cockpit-journal-demande{font-weight:600;overflow-wrap:anywhere}
.cockpit-journal-quoi{color:var(--ink-2);overflow-wrap:anywhere}
"""


def _when(iso_value):
    """"06/10 13:08" in Paris time, or ``None`` when the trace carries no
    readable date."""
    if not iso_value or not isinstance(iso_value, str):
        return None
    text = iso_value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(PARIS).strftime("%d/%m %H:%M")
    except ValueError:
        return None


def render_journal_section(entries):
    title = html.escape(SECTION_TITLE)
    if not entries:
        return (
            '<section class="zone cockpit-journal" data-state="empty">'
            '<div class="zone-h"><h2>%s</h2></div>'
            '<p class="muted cockpit-journal-status">%s</p></section>\n'
        ) % (title, html.escape(EMPTY_TEXT))

    rows = "".join(_render_entry(e) for e in entries)
    return (
        '<section class="zone cockpit-journal" data-state="filled">'
        '<div class="zone-h"><h2>%s</h2><span class="mono muted">%d</span></div>'
        '<div class="panel cockpit-journal-list">%s</div></section>\n'
    ) % (title, len(entries), rows)


def _render_entry(entry):
    when = _when(entry.quand)
    when_html = "<time>%s</time>" % when if when else html.escape(UNDATED_TEXT)
    # An event of the journal answers no request: it shows none.
    demande = entry.demande or (NO_REQUEST_TEXT if entry.voie in VOIE_LABELS else "")
    return (
        '<div class="cockpit-journal-entry" data-bead-id="%s" data-voie="%s">'
        '%s'
        '<div class="cockpit-journal-quoi">%s</div>'
        '<div class="meta cockpit-journal-meta"><span>%s</span>%s<span>%s</span></div>'
        '<details class="more"><summary>Détails</summary><div class="det">'
        '<div class="row"><span>Identifiant</span><code>%s</code></div>'
        '<div class="row"><span>Voie</span><code>%s</code></div>'
        "</div></details>"
        "</div>"
    ) % (
        html.escape(entry.bead_id),
        html.escape(entry.voie),
        '<div class="cockpit-journal-demande">%s</div>' % html.escape(demande) if demande else "",
        html.escape(entry.quoi),
        when_html,
        # A trace that names nobody (a cleared decision) shows no "par".
        "<span>par %s</span>" % html.escape(entry.par) if entry.par else "",
        html.escape(VOIE_LABELS.get(entry.voie, entry.voie)),
        html.escape(entry.bead_id),
        html.escape(entry.voie),
    )


def render_journal_page(section_html, fresh_html=""):
    """The journal's own page: the way back, the freshness headline, the
    section."""
    return (
        '<div class="cockpit-journal-page">'
        '<header class="topbar"><div class="brand"><a class="back" href="/">← Accueil</a>'
        "<h1>Journal</h1></div>%s</header>%s</div>\n"
    ) % (fresh_html, section_html)
