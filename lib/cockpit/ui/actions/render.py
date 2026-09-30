"""Renders the Operator Action controls on a request, and the one inline
script that drives them (spec af-oohx2x §"Actions opérateur"; T13 AC3,
AC4). Pure functions of an :class:`~cockpit.requests.model.OperatorRequest`
-- no I/O; the POST itself happens client-side, in :data:`SCRIPT`.
"""
import html

from cockpit.requests.model import URGENT

FIXED_EXPLANATION = (
    "Acquitter : plus aucun rappel, la demande reste ici. "
    "Reporter : cachée jusqu'à l'heure choisie, puis elle revient. "
    "Aucun des deux ne change rien dans l'usine."
)

REPORT_OPTIONS = (
    ("1h", "Dans 1 h"),
    ("4h", "Dans 4 h"),
    ("demain_09h", "Demain 09:00"),
    ("libre", "Heure libre"),
)


def render_actions(request):
    """One action block per request: Acquitter (Urgent, not already
    acquitted), Reporter (Urgent and À faire), and Continuer avec un
    agent -- always offered, never gated on niveau (spec .32 offers it
    whenever an agent is "vraiment nécessaire", which the cockpit cannot
    judge)."""
    buttons = []
    if request.niveau == URGENT and not request.acquittee:
        buttons.append(
            '<button type="button" class="cockpit-action" data-action="acquitter" '
            'data-bead-id="%s">Acquitter</button>' % html.escape(request.id)
        )

    report_options_html = "".join(
        '<option value="%s">%s</option>' % (html.escape(value), html.escape(label))
        for value, label in REPORT_OPTIONS
    )
    buttons.append(
        '<span class="cockpit-action-report">'
        '<select class="cockpit-report-option" data-bead-id="%s">%s</select>'
        '<button type="button" class="cockpit-action" data-action="reporter" '
        'data-bead-id="%s">Reporter</button>'
        "</span>" % (html.escape(request.id), report_options_html, html.escape(request.id))
    )

    buttons.append(
        '<button type="button" class="cockpit-action cockpit-action-tokens" data-action="continuer" '
        'data-bead-id="%s" data-quoi="%s">'
        "Continuer avec un agent (utilise un agent — consomme des tokens)</button>"
        % (html.escape(request.id), html.escape(request.quoi))
    )

    return (
        '<div class="cockpit-actions">%s'
        '<p class="cockpit-actions-explication">%s</p>'
        "</div>"
    ) % ("".join(buttons), html.escape(FIXED_EXPLANATION))


# One tap, then an "Annuler" window of 10 s before the POST actually goes
# out (spec .33) -- Copier avec un agent copies to the clipboard in the
# same pattern instead of writing anything.
#
# répondre, accepter/rejeter/reporter une proposition, and relancer (T14,
# af-peh3yy) use a different, stricter pattern instead: "deux temps"
# (spec: every one of those five gestures needs a two-step confirmation).
# A first click on one of these controls only arms it (toggles a
# "Confirmer ?" state, no network call at all); a second click on the
# same control within the confirm window sends the POST with
# `confirm: true`. Clicking anything else, or waiting past the window,
# disarms it -- so a single tap never writes anything
# (cockpit.actions.registry also refuses a POST missing `confirm: true`
# server-side, so this is a defence in depth, not the only guard).
TWO_STEP_ACTIONS = ("repondre", "accepter_proposition", "rejeter_proposition", "reporter_proposition", "relancer")

SCRIPT = """
<script>
(function () {
  function post(action, body) {
    return fetch('/api/actions/' + action, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify(body)
    });
  }
  function withUndo(label, run) {
    var cancelled = false;
    var toast = document.createElement('div');
    toast.className = 'cockpit-undo-toast';
    toast.textContent = label + '… ';
    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.textContent = 'Annuler';
    cancelBtn.onclick = function () { cancelled = true; toast.remove(); };
    toast.appendChild(cancelBtn);
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.remove();
      if (!cancelled) { run(); }
    }, 10000);
  }
  // "Deux temps" (T14, af-peh3yy): répondre, accepter/rejeter/reporter
  // une proposition, and relancer never send confirm:true on a first
  // click -- they only arm the control (CSS class + label change). A
  // second click on the SAME armed control within CONFIRM_WINDOW_MS
  // sends confirm:true; any other click disarms it first.
  var TWO_STEP_ACTIONS = ['repondre', 'accepter_proposition', 'rejeter_proposition', 'reporter_proposition', 'relancer'];
  var CONFIRM_WINDOW_MS = 10000;
  var armed = null; // {el, timer}

  function disarm() {
    if (armed) {
      armed.el.classList.remove('cockpit-armed');
      armed.el.textContent = armed.originalLabel;
      clearTimeout(armed.timer);
      armed = null;
    }
  }

  function bodyFor(action, el) {
    var beadId = el.getAttribute('data-bead-id');
    if (action === 'repondre') {
      return {bead_id: beadId, lettre: el.getAttribute('data-lettre') || ''};
    }
    if (action === 'accepter_proposition') {
      return {bead_id: beadId};
    }
    if (action === 'rejeter_proposition') {
      var raisonEl = document.querySelector('.cockpit-rejeter-raison[data-bead-id="' + beadId + '"]');
      return {bead_id: beadId, raison: raisonEl ? raisonEl.value : ''};
    }
    if (action === 'reporter_proposition') {
      var heureEl = document.querySelector('.cockpit-reporter-heure[data-bead-id="' + beadId + '"]');
      return {bead_id: beadId, heure: heureEl ? heureEl.value : ''};
    }
    if (action === 'relancer') {
      return {
        bead_id: beadId,
        target_type: el.getAttribute('data-target-type') || '',
        session_id: el.getAttribute('data-session-id') || undefined,
        order_name: el.getAttribute('data-order-name') || undefined
      };
    }
    return {bead_id: beadId};
  }

  document.addEventListener('click', function (event) {
    var el = event.target.closest('[data-action]');
    if (!el) { return; }
    var action = el.getAttribute('data-action');

    if (TWO_STEP_ACTIONS.indexOf(action) !== -1) {
      if (armed && armed.el === el) {
        var body = bodyFor(action, el);
        body.confirm = true;
        disarm();
        post(action, body).then(function (resp) {
          return resp.json();
        }).then(function (data) {
          // répondre's immediate feedback (spec .26: "la demande affiche
          // « répondu b à HH:MM, en cours de traitement par l'usine »")
          // -- a transient toast at the moment of the action, since the
          // request itself exits the list once gc.needs_benjamin clears
          // (builder.py: "Exit is at-source only").
          if (data && data.display) {
            var toast = document.createElement('div');
            toast.className = 'cockpit-undo-toast cockpit-repondu-toast';
            toast.textContent = data.display;
            document.body.appendChild(toast);
            setTimeout(function () { toast.remove(); }, 10000);
          }
        });
        return;
      }
      disarm();
      var originalLabel = el.textContent;
      el.classList.add('cockpit-armed');
      el.textContent = 'Confirmer ?';
      armed = {
        el: el,
        originalLabel: originalLabel,
        timer: setTimeout(disarm, CONFIRM_WINDOW_MS)
      };
      return;
    }

    disarm();
    var beadId = el.getAttribute('data-bead-id');
    if (action === 'acquitter') {
      withUndo('Acquitter', function () { post('acquitter', {bead_id: beadId}); });
    } else if (action === 'reporter') {
      var select = document.querySelector('.cockpit-report-option[data-bead-id="' + beadId + '"]');
      var option = select ? select.value : '1h';
      withUndo('Reporter', function () { post('reporter', {bead_id: beadId, option: option}); });
    } else if (action === 'continuer') {
      var quoi = el.getAttribute('data-quoi') || '';
      withUndo('Copier le prompt', function () {
        post('continuer', {bead_id: beadId, quoi: quoi}).then(function (resp) {
          return resp.json();
        }).then(function (data) {
          if (data.prompt && navigator.clipboard) { navigator.clipboard.writeText(data.prompt); }
        });
      });
    }
  });
})();
</script>
"""
