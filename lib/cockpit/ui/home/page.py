"""The pieces of a request of « Ce qui t'attend » that the overview draws
(spec af-oohx2x §"Accueil", §"Demandes opérateur"; variant D of
origin/prototype/c01-home-screen): its level, since when it waits, and each
prepared option -- the answer itself when the option is one. Since B
(af-4uzgzm) the list and its requests are « Pour moi » of the overview
(:mod:`cockpit.ui.home.pour_moi`). Pure functions of an
:class:`~cockpit.requests.model.OperatorRequest` -- no I/O.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects.demandes import TYPE_LIVRE_NON_ACCEPTE
from cockpit.requests.model import A_FAIRE, TYPE_ESCALATION, URGENT
from cockpit.requests.sources.readability import TYPE_SOURCE_ILLISIBLE

UNKNOWN_TEXT = "Inconnu : illisible depuis %s"
UNKNOWN_TEXT_NO_TIME = "Inconnu : illisible depuis toujours"

LEVEL_CLASS = {URGENT: "urgent", A_FAIRE: "normal"}  # anything else: "info"


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
