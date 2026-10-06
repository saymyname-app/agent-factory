"""Renders "Ce qui t'attend" as the validated variant D shows it (spec
af-oohx2x §"Accueil", §"Demandes opérateur"; prototype
origin/prototype/c01-home-screen, ``renderD``): a short list on the left,
the selected request's detail beside it on a PC, the detail as a sheet over
the list on an iPhone. Pure function of a list of
:class:`~cockpit.requests.model.OperatorRequest` plus the beads source's
own freshness — no I/O.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects.demandes import TYPE_LIVRE_NON_ACCEPTE
from cockpit.requests.model import A_FAIRE, TYPE_ESCALATION, TYPE_PROPOSAL, URGENT
from cockpit.requests.sources.readability import TYPE_SOURCE_ILLISIBLE
from cockpit.text.fallback import FALLBACK_NO_RECOMMENDATION, incomplete_label
from cockpit.ui.actions.render import render_actions

SECTION_TITLE = "Ce qui t'attend"
# Under the list in every state: where what no longer waits went.
JOURNAL_LINK = (
    '<div class="list-foot"><a href="/journal">Journal des demandes résolues →</a></div>'
)
EMPTY_TEXT = "Rien ne t'attend — vérifié à %s"
UNKNOWN_TEXT = "Inconnu : illisible depuis %s"
UNKNOWN_TEXT_NO_TIME = "Inconnu : illisible depuis toujours"

LEVEL_CLASS = {URGENT: "urgent", A_FAIRE: "normal"}  # anything else: "info"

# Picks the request shown in the detail pane. On a narrow screen the
# detail replaces the list ("sheet") and "Retour à la liste" brings the
# list back; the choice survives a reload through the URL fragment.
INBOX_SCRIPT = """
<script>
(function () {
  var root = document.getElementById('inbox');
  if (!root) { return; }
  function select(id, sheet) {
    var target = document.getElementById('d-' + id);
    if (!target) { return; }
    root.querySelectorAll('.detail').forEach(function (d) { d.classList.toggle('on', d === target); });
    root.querySelectorAll('.li').forEach(function (l) {
      l.setAttribute('aria-current', l.getAttribute('data-id') === id ? 'true' : 'false');
    });
    root.classList.toggle('sheet', sheet);
  }
  root.addEventListener('click', function (event) {
    var item = event.target.closest('.li');
    if (item) {
      event.preventDefault();
      select(item.getAttribute('data-id'), true);
      history.replaceState(null, '', '#d-' + item.getAttribute('data-id'));
      if (window.matchMedia('(max-width: 930px)').matches) { root.scrollIntoView({block: 'start'}); }
      return;
    }
    if (event.target.closest('.back')) {
      event.preventDefault();
      root.classList.remove('sheet');
      history.replaceState(null, '', location.pathname);
    }
  });
  if (location.hash.indexOf('#d-') === 0) { select(location.hash.slice(3), true); }
})();
</script>
"""


def _hhmm(epoch):
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _since(epoch, now):
    """"13:10" today, "hier 18:20" yesterday, "29/09 18:20" before that —
    an hour alone would pass a days-old request off as this morning's."""
    if epoch is None:
        return None
    when = datetime.fromtimestamp(epoch, tz=PARIS)
    hhmm = when.strftime("%H:%M")
    if now is None:
        return hhmm
    days = (datetime.fromtimestamp(now, tz=PARIS).date() - when.date()).days
    if days <= 0:
        return hhmm
    if days == 1:
        return "hier " + hhmm
    return when.strftime("%d/%m ") + hhmm


def _since_html(r, now):
    """When the request started waiting; empty when its kind carries no
    date at all -- "??:??" is kept for a date its producer owed and left
    out (spec .14)."""
    since = _since(r.depuis_quand, now)
    if since is None and "depuis_quand" not in r.missing_fields:
        return ""
    return _time(since)


def _time(text):
    return "<time>%s</time>" % html.escape(text or "??:??")


def _level(niveau, with_label=True):
    return '<span class="lvl %s"><i></i>%s</span>' % (
        LEVEL_CLASS.get(niveau, "info"),
        html.escape(niveau) if with_label else "",
    )


def render_requests_section(requests, verified_at=None, source_unknown=False, last_known_at=None):
    """``requests``: sorted list from :func:`cockpit.requests.builder.build_requests`.
    ``source_unknown``: True when the beads source's own Freshness is
    "unknown" (spec .16) — the whole section then shows the illisible
    message instead of any list, stale or not."""
    title = html.escape(SECTION_TITLE)
    notice = ""
    if source_unknown:
        since = _hhmm(last_known_at)
        body = html.escape(UNKNOWN_TEXT % since if since else UNKNOWN_TEXT_NO_TIME)
        # With requests that do not come from Beads still to show, the
        # notice heads the list: what follows is not the whole list.
        notice = '<div style="padding:14px 14px 0"><div class="unknown">%s</div></div>' % body
    if source_unknown and not requests:
        return (
            '<div class="inbox solo cockpit-requests" data-state="unknown">'
            '<div class="list" id="inbox-list"><h2><span>%s</span></h2>'
            '<div style="padding:14px"><div class="unknown">%s</div></div>%s</div></div>\n'
        ) % (title, body, JOURNAL_LINK)

    if not requests:
        when = _hhmm(verified_at) or "??:??"
        body = html.escape(EMPTY_TEXT % when)
        return (
            '<div class="inbox solo cockpit-requests" data-state="empty">'
            '<div class="list" id="inbox-list"><h2><span>%s</span><span class="mono muted">0</span></h2>'
            '<div style="padding:14px"><div class="empty"><span class="dot"></span>%s</div></div>%s</div></div>\n'
        ) % (title, body, JOURNAL_LINK)

    first_id = requests[0].id
    rows = "".join(_render_list_item(r, verified_at, r.id == first_id) for r in requests)
    details = "".join(_render_detail(r, verified_at, r.id == first_id) for r in requests)
    return (
        '<div class="inbox cockpit-requests" data-state="filled">'
        '<div class="list" id="inbox-list"><h2><span>%s</span><span class="mono muted">%d</span></h2>%s%s</div>'
        "%s</div>\n%s"
    ) % (title, len(requests), notice + rows, JOURNAL_LINK, details, INBOX_SCRIPT)


def _render_list_item(r, now, selected):
    incomplete = ' · <span class="incomplete">incomplète</span>' if r.incomplete else ""
    return (
        '<a class="li" href="#d-%s" data-id="%s" aria-current="%s" data-reportee="%s">'
        '%s<span><div class="q">%s</div><div class="p">%s%s</div></span>%s</a>'
    ) % (
        html.escape(r.id),
        html.escape(r.id),
        "true" if selected else "false",
        "true" if r.reportee else "false",
        _level(r.niveau, with_label=False),
        html.escape(r.quoi),
        html.escape(r.projet),
        incomplete,
        _since_html(r, now),
    )


def _render_detail(r, now, selected):
    # "quoi" missing already reads "incomplète : champ quoi manquant" as the
    # title itself; name the next missing field rather than say it twice.
    other_missing = [f for f in r.missing_fields if f != "quoi"]
    incomplete_badge = ""
    if r.incomplete and other_missing:
        incomplete_badge = ' <span class="incomplete cockpit-request-incomplete">%s</span>' % html.escape(
            incomplete_label(other_missing[0])
        )

    options_html = "".join(_render_option(r, o) for o in r.que_faire)
    if r.recommande_absent:
        options_html += '<span class="oc cockpit-request-no-recommendation">%s</span>' % html.escape(
            FALLBACK_NO_RECOMMENDATION
        )

    acquittee = '<span class="chip ack">Acquittée · rappels coupés</span>' if r.acquittee else ""
    since_html = _since_html(r, now)
    meta = '<div class="meta cockpit-request-meta"><b>%s</b>%s<span>vérifié %s</span>%s</div>' % (
        html.escape(r.projet),
        "<span>depuis %s</span>" % since_html if since_html else "",
        _time(_hhmm(r.verifie_a)),
        acquittee,
    )

    details = (
        '<details class="more cockpit-request-details"><summary>Détails</summary><div class="det">'
        '<div class="row"><span>Identifiant</span><code>%s</code></div>'
        '<div class="row"><span>Type</span><code>%s</code></div>'
        "</div></details>"
    ) % (html.escape(r.id), html.escape(r.type))

    return (
        '<article class="detail zone-body cockpit-request%s" id="d-%s" data-level="%s" '
        'data-incomplete="%s" data-reportee="%s">'
        '<a class="btn ghost back" href="#inbox-list">← Retour à la liste</a>'
        "%s"
        '<div class="quoi cockpit-request-quoi">%s</div>'
        '<div class="sec"><span class="lbl">Pourquoi ça t\'attend</span>'
        '<div class="why cockpit-request-pourquoi">%s%s</div></div>'
        '<div class="sec"><span class="lbl">Que faire</span>'
        '<div class="opts cockpit-request-que-faire">%s</div></div>'
        "%s%s%s%s"
        "</article>"
    ) % (
        " on" if selected else "",
        html.escape(r.id),
        LEVEL_CLASS.get(r.niveau, "info"),
        "true" if r.incomplete else "false",
        "true" if r.reportee else "false",
        _level(r.niveau),
        html.escape(r.quoi),
        html.escape(r.pourquoi),
        incomplete_badge,
        options_html,
        _render_proposal_actions(r),
        render_actions(r),
        meta,
        details,
    )


def _option_control(r, lettre):
    """The attributes that make one option the control itself, or ``None``
    when the option is read-only: the answer to a NEEDS BENJAMIN whose
    options came from its producer (two-step, spec .34), « Accepter » /
    « Pas bon → agent » on a delivered chantier (spec .30, .31). Approving
    a Spec or a graph never gets one (spec .37)."""
    bead_id = html.escape(r.id)
    if r.type == TYPE_ESCALATION and "que_faire" not in r.missing_fields and lettre:
        return 'data-action="repondre" data-bead-id="%s" data-lettre="%s"' % (bead_id, html.escape(lettre))
    if r.type == TYPE_LIVRE_NON_ACCEPTE and lettre == "a":
        return 'data-action="accepter_chantier" data-bead-id="%s"' % bead_id
    if r.type == TYPE_LIVRE_NON_ACCEPTE and lettre == "b":
        return 'data-action="pas_bon_vers_agent" data-bead-id="%s" data-titre="%s"' % (
            bead_id, html.escape(r.titre),
        )
    return None


def _render_option(r, option):
    """One prepared option with its consequence (spec .12, .13)."""
    lettre = option.get("lettre") or ""
    recommande = ""
    raison = ""
    if option.get("recommande"):
        recommande = ' <span class="chip atoi cockpit-option-recommande">Recommandé</span>'
        if option.get("raison"):
            raison = '<span class="oc"><b>Pourquoi recommandé :</b> %s</span>' % html.escape(option["raison"])
    inner = (
        '<span class="k">%s</span><span class="ot"><span>%s</span>%s'
        '<span class="oc">%s</span>%s</span>'
    ) % (
        html.escape(lettre),
        html.escape(option.get("option") or ""),
        recommande,
        html.escape(option.get("consequence") or ""),
        raison,
    )
    control = _option_control(r, lettre)
    if control:
        return '<button type="button" class="btn opt cockpit-option" %s>%s</button>' % (control, inner)
    if r.type == TYPE_SOURCE_ILLISIBLE:
        # "Revérifier maintenant" is the page's own recheck (spec .65).
        return (
            '<form method="post" action="/api/health/recheck" style="margin:0">'
            '<button type="submit" class="btn opt cockpit-option">%s</button></form>'
        ) % inner
    return '<div class="btn opt cockpit-option">%s</div>' % inner


def _render_proposal_actions(r):
    """Accepter / Refuser avec une raison (spec .27, .28), both two-step."""
    if r.type != TYPE_PROPOSAL:
        return ""
    bead_id = html.escape(r.id)
    return (
        '<div class="acts cockpit-proposal-actions">'
        '<button type="button" class="btn primary" data-action="accepter_proposition" '
        'data-bead-id="%s">Accepter</button>'
        '<span class="inline">'
        '<input type="text" class="field cockpit-rejeter-raison" data-bead-id="%s" '
        'placeholder="Raison du refus" aria-label="Raison du refus">'
        '<button type="button" class="btn" data-action="rejeter_proposition" '
        'data-bead-id="%s">Refuser</button>'
        "</span></div>"
    ) % (bead_id, bead_id, bead_id)
