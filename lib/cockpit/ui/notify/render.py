"""Renders the notify journal and the "envoyer une notification de test"
button (spec af-oohx2x §"Notifications": .60). Pure functions over
:meth:`~cockpit.notify.engine.NotificationEngine.journal_entries` -- no
I/O; the POST itself happens client-side (:data:`SCRIPT`), same pattern as
``cockpit.ui.actions.render``. Wiring the button's action handler and this
page fragment into the server is a later ticket's job (the T18 heartbeat
emitter is the precedent for "built but not wired").
"""
import html

_KIND_LABELS = {
    "initial": "premier envoi",
    "escalade": "montée de niveau",
    "echeance": "échéance du report",
    "rappel": "rappel",
    "resolu": "résolue",
    "groupe": "regroupé",
    "test": "test",
}


def render_journal(entries):
    """"Journal des envois" (spec .60): demande, niveau (via la priorité),
    heure, accepté ou échec."""
    if not entries:
        return '<p class="cockpit-notify-empty">Aucun envoi pour le moment.</p>'
    rows = []
    for entry in entries:
        kind_label = _KIND_LABELS.get(entry.get("kind"), entry.get("kind") or "")
        status = "accepté" if entry.get("ok") else "échec"
        rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (
                html.escape(str(entry.get("req_id") or "—")),
                html.escape(kind_label),
                html.escape(str(entry.get("priority", ""))),
                html.escape(status),
            )
        )
    return (
        '<table class="cockpit-notify-journal">'
        "<thead><tr><th>Demande</th><th>Type</th><th>Priorité</th><th>Statut</th></tr></thead>"
        "<tbody>%s</tbody></table>" % "".join(rows)
    )


TEST_BUTTON_HTML = (
    '<button type="button" class="cockpit-action" data-action="notifier_test">'
    "Envoyer une notification de test</button>"
)

SCRIPT = """
<script>
(function () {
  document.addEventListener('click', function (event) {
    var el = event.target.closest('[data-action="notifier_test"]');
    if (!el) { return; }
    fetch('/api/actions/notifier_test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: '{}'
    });
  });
})();
</script>
"""
