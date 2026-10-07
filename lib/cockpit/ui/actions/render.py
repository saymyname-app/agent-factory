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
FREE_TIME_OPTION = "libre"


def render_actions(request):
    """One action row per request, in the prototype's order: Continuer
    avec un agent -- always offered, never gated on niveau (spec .32
    offers it whenever an agent is "vraiment nécessaire", which the
    cockpit cannot judge) --, Acquitter (Urgent, not already acquitted),
    Reporter; then the fixed sentence saying what the last two do
    (spec .24)."""
    bead_id = html.escape(request.id)
    buttons = [
        '<button type="button" class="btn cockpit-action cockpit-action-tokens" data-action="continuer" '
        'data-bead-id="%s" data-quoi="%s">'
        "Continuer avec un agent <small>utilise un agent (consomme des tokens)</small></button>"
        % (bead_id, html.escape(request.quoi))
    ]
    if request.niveau == URGENT and not request.acquittee:
        buttons.append(
            '<button type="button" class="btn ghost cockpit-action" data-action="acquitter" '
            'data-bead-id="%s">Acquitter</button>' % bead_id
        )

    if not request.reportable:
        # Nothing on a bead could hide this request until later: no
        # Reporter, and no sentence explaining a control that is not there.
        return '<div class="acts cockpit-actions">%s</div>' % "".join(buttons)
    buttons.append(
        '<button type="button" class="btn ghost cockpit-action" data-action="reporter_ouvrir" '
        'data-bead-id="%s">Reporter</button>' % bead_id
    )

    return (
        '<div class="acts cockpit-actions">%s</div>'
        "%s"
        '<p class="hint cockpit-actions-explication">%s</p>'
    ) % ("".join(buttons), _render_report_menu(bead_id), html.escape(FIXED_EXPLANATION))


def _render_report_menu(bead_id):
    """"Reporter jusqu'à :" -- takes the action row's place while open
    (prototype variant D). One button per fixed delay (spec .22); "heure
    libre" is a date-and-time field plus its own button."""
    fixed = "".join(
        '<button type="button" class="btn" data-action="reporter" data-bead-id="%s" '
        'data-option="%s">%s</button>' % (bead_id, html.escape(value), html.escape(label))
        for value, label in REPORT_OPTIONS
        if value != FREE_TIME_OPTION
    )
    return (
        '<div class="snoozemenu cockpit-report-menu" data-bead-id="%s" hidden>'
        '<span class="muted">Reporter jusqu\'à :</span>%s'
        '<span class="inline">'
        '<input type="datetime-local" class="field cockpit-report-libre" data-bead-id="%s" '
        'aria-label="Heure libre">'
        '<button type="button" class="btn" data-action="reporter" data-bead-id="%s" '
        'data-option="%s">À cette heure</button></span>'
        '<button type="button" class="btn ghost" data-action="reporter_fermer" '
        'data-bead-id="%s">Annuler</button>'
        "</div>"
    ) % (bead_id, fixed, bead_id, bead_id, FREE_TIME_OPTION, bead_id)


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
TWO_STEP_ACTIONS = (
    "repondre", "accepter_proposition", "rejeter_proposition", "reporter_proposition", "relancer",
    "accepter_chantier",
)

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
  // The report menu takes the action row's place while it is open.
  function showReportMenu(beadId, open) {
    var menu = document.querySelector('.cockpit-report-menu[data-bead-id="' + beadId + '"]');
    if (!menu) { return; }
    menu.hidden = !open;
    if (menu.previousElementSibling) { menu.previousElementSibling.hidden = open; }
  }
  function say(text) {
    var toast = document.createElement('div');
    toast.className = 'cockpit-undo-toast cockpit-repondu-toast';
    toast.setAttribute('role', 'status');
    toast.textContent = text;
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 10000);
  }
  // An action that writes shows at once, before the server answers
  // (2026-10-07, docs/COCKPIT.md: the button and the request stayed for
  // seconds as if nothing had been clicked; the server re-reads its
  // sources before answering). This script is served with the page: it
  // never names the operator. At the
  // click: the request in « Ce qui t'attend », its row in the list and the
  // chantier's row in « Projets » are greyed, their controls switched off
  // and the expected result written on them. When the server answers: a
  // success confirms the text and reloads the page (`rafraichi`: the list
  // was re-read, the reloaded page shows the request gone or in its new
  // state); a refusal or a lost connection puts everything back as it was
  // and says so. Nothing is assumed written before the server said so:
  // the mark reads « … enregistrement » until then.
  function mark(el, beadId, text) {
    var holders = [];
    function add(node) { if (node && holders.indexOf(node) === -1) { holders.push(node); } }
    add(el && el.closest ? el.closest('.cockpit-request') : null);
    add(el && el.closest ? el.closest('.cockpit-chantier') : null);
    if (beadId) {
      add(document.getElementById('d-' + beadId));
      add(document.getElementById('ch-' + beadId));
      add(document.querySelector('.li[data-id="' + beadId + '"]'));
    }
    if (!holders.length && el) { add(el.parentNode || el); }
    var notes = [];
    var hidden = [];
    var switched = [];
    holders.forEach(function (holder) {
      holder.classList.add('cockpit-done');
      holder.setAttribute('data-done', 'pending');
      var controls = holder.querySelectorAll('[data-action]');
      for (var i = 0; i < controls.length; i++) {
        var control = controls[i];
        switched.push({el: control, action: control.getAttribute('data-action'), disabled: control.disabled});
        control.removeAttribute('data-action');
        control.setAttribute('aria-disabled', 'true');
        if ('disabled' in control) { control.disabled = true; }
      }
      // « À toi de jouer » no longer holds once the gesture is made.
      var chips = holder.querySelectorAll('.cockpit-chantier-etat');
      for (var j = 0; j < chips.length; j++) {
        if (!chips[j].hidden) { chips[j].hidden = true; hidden.push(chips[j]); }
      }
      var note = document.createElement('span');
      note.className = 'chip ack cockpit-done-note';
      note.setAttribute('role', 'status');
      note.textContent = text + ' · enregistrement…';
      var anchor = holder.querySelector('.cockpit-request-quoi, .cockpit-chantier-n, .q');
      if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(note, anchor.nextSibling);
      } else {
        holder.appendChild(note);
      }
      notes.push(note);
    });
    return {
      confirm: function (finalText) {
        holders.forEach(function (holder) { holder.setAttribute('data-done', 'true'); });
        notes.forEach(function (note) { note.textContent = finalText; });
      },
      undo: function () {
        holders.forEach(function (holder) {
          holder.classList.remove('cockpit-done');
          holder.removeAttribute('data-done');
        });
        switched.forEach(function (item) {
          item.el.setAttribute('data-action', item.action);
          item.el.removeAttribute('aria-disabled');
          if ('disabled' in item.el) { item.el.disabled = item.disabled; }
        });
        hidden.forEach(function (chip) { chip.hidden = false; });
        notes.forEach(function (note) { note.remove(); });
      }
    };
  }
  // Use as: settle(el, beadId, text, post(action, body)). The mark is put
  // before the answer exists.
  function settle(el, beadId, fallback, request) {
    var text = fallback || 'Fait';
    var marked = mark(el, beadId, text);
    return request.then(function (resp) {
      return resp.json().then(function (data) {
        if (!resp.ok || !data || data.error) {
          marked.undo();
          say('Action refusée : ' + ((data && data.error) || resp.status));
          return data;
        }
        var finalText = data.display || text;
        marked.confirm(finalText);
        say(finalText);
        if (data.rafraichi) { setTimeout(function () { window.location.reload(); }, 600); }
        return data;
      });
    }).catch(function () {
      marked.undo();
      say('Action non envoyée : le cockpit ne répond pas');
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
  var TWO_STEP_ACTIONS = ['repondre', 'accepter_proposition', 'rejeter_proposition', 'reporter_proposition', 'relancer',
                          'accepter_chantier'];
  var TWO_STEP_DONE = {
    accepter_proposition: 'Proposition acceptée, à planifier',
    rejeter_proposition: 'Proposition refusée',
    reporter_proposition: 'Proposition reportée',
    repondre: 'Réponse envoyée',
    relancer: 'Relance demandée',
    accepter_chantier: 'Chantier accepté'
  };
  var CONFIRM_WINDOW_MS = 10000;
  var armed = null; // {el, timer}

  function disarm() {
    if (armed) {
      armed.el.classList.remove('cockpit-armed');
      armed.el.innerHTML = armed.originalHTML;
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
    if (!el) { disarm(); return; }
    var action = el.getAttribute('data-action');

    if (TWO_STEP_ACTIONS.indexOf(action) !== -1) {
      if (armed && armed.el === el) {
        var body = bodyFor(action, el);
        body.confirm = true;
        disarm();
        // répondre's immediate feedback (spec .26: "la demande affiche
        // « répondu b à HH:MM, en cours de traitement par l'usine »"),
        // and the same for every two-step gesture: shown at the click,
        // confirmed or put back when the server answers (see settle).
        settle(el, body.bead_id, TWO_STEP_DONE[action], post(action, body));
        return;
      }
      disarm();
      var originalHTML = el.innerHTML;
      el.classList.add('cockpit-armed');
      if (el.classList.contains('opt')) {
        // An option keeps its text and consequence while armed.
        var note = document.createElement('span');
        note.className = 'cockpit-armed-note';
        note.textContent = 'Clique encore pour confirmer';
        (el.querySelector('.ot') || el).appendChild(note);
      } else {
        el.textContent = 'Confirmer ?';
      }
      armed = {
        el: el,
        originalHTML: originalHTML,
        timer: setTimeout(disarm, CONFIRM_WINDOW_MS)
      };
      return;
    }

    disarm();
    var beadId = el.getAttribute('data-bead-id');
    if (action === 'acquitter') {
      withUndo('Acquitter', function () {
        settle(el, beadId, 'Acquittée, rappels coupés', post('acquitter', {bead_id: beadId}));
      });
    } else if (action === 'reporter_ouvrir' || action === 'reporter_fermer') {
      showReportMenu(beadId, action === 'reporter_ouvrir');
    } else if (action === 'reporter') {
      var body = {bead_id: beadId, option: el.getAttribute('data-option') || '1h'};
      if (body.option === 'libre') {
        // "Heure libre": the field's local date and time, sent as an epoch.
        var input = document.querySelector('.cockpit-report-libre[data-bead-id="' + beadId + '"]');
        var when = input && input.value ? new Date(input.value).getTime() / 1000 : 0;
        if (!when || when <= Date.now() / 1000) {
          if (input) { input.focus(); }
          return;
        }
        body.custom_epoch = when;
      }
      showReportMenu(beadId, false);
      withUndo('Reporter', function () {
        settle(el, beadId, 'Reportée', post('reporter', body));
      });
    } else if (action === 'notifier_test') {
      post('notifier_test', {}).then(function (resp) {
        return resp.json();
      }).then(function (data) {
        var said = document.createElement('div');
        said.className = 'toast';
        said.setAttribute('role', 'status');
        said.textContent = data.display || data.error || 'Notification de test non envoyée';
        document.body.appendChild(said);
        setTimeout(function () { said.remove(); }, 5000);
      });
    } else if (action === 'pas_bon_vers_agent') {
      var titre = el.getAttribute('data-titre') || '';
      withUndo('Copier le prompt', function () {
        post('pas_bon_vers_agent', {bead_id: beadId, titre: titre}).then(function (resp) {
          return resp.json();
        }).then(function (data) {
          if (data.prompt && navigator.clipboard) { navigator.clipboard.writeText(data.prompt); }
        });
      });
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
