"""Fixed French phrases for Pushover push content (spec af-oohx2x
§"Notifications": "Contenu : phrase fixe du type + projet + lien cockpit
+ « quoi » tronqué [...] Jamais de donnée de personne réelle, de secret,
de corps de bead ni de donnée produit.").

Pure string composition -- no I/O. The only producer-written text ever
placed in a push is :attr:`~cockpit.requests.model.OperatorRequest.quoi`,
already passed through the main-text control (``cockpit.text.validate``)
before the request was built (``requests/builder.py``); ``pourquoi`` and
``que_faire`` (which can carry more detail) are never read here. Even the
truncated ``quoi`` is included only when ``include_quoi`` is true -- the
channel must be end-to-end encrypted first (spec: "autorisé parce que le
canal est E2E ; sans E2E, pas de « quoi »").
"""
from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, TYPE_ESCALATION, TYPE_PROPOSAL, URGENT

QUOI_TRUNCATE_LENGTH = 120

_PHRASES = {
    (TYPE_ESCALATION, URGENT): "Une décision bloque une livraison en cours",
    (TYPE_ESCALATION, A_FAIRE): "Une décision t'attend",
    (TYPE_PROPOSAL, URGENT): "Une proposition attend ta décision",
    (TYPE_PROPOSAL, A_FAIRE): "Une proposition attend ta décision",
}
_DEFAULT_PHRASE = "Une demande opérateur t'attend"

REMINDER_SUFFIX = " (rappel)"
RESOLVED_TITLE = "Urgent résolue"
TEST_TITLE = "Notification de test"
TEST_BODY = "Le canal Pushover fonctionne."
GROUPED_SUFFIX = "autres demandes — voir le cockpit"


def phrase_for(request):
    return _PHRASES.get((request.type, request.niveau), _DEFAULT_PHRASE)


def truncate_quoi(quoi):
    if not quoi:
        return ""
    if len(quoi) <= QUOI_TRUNCATE_LENGTH:
        return quoi
    return quoi[: QUOI_TRUNCATE_LENGTH - 1].rstrip() + "…"


def build_message(request, include_quoi, cockpit_url, is_reminder=False):
    """Returns ``(title, body)`` for a request's push. ``cockpit_url`` is
    already the full link for this request -- this module owns no URL
    scheme of its own."""
    title = phrase_for(request)
    if is_reminder:
        title += REMINDER_SUFFIX
    parts = [request.projet or DEFAULT_PROJECT]
    if include_quoi and request.quoi:
        parts.append(truncate_quoi(request.quoi))
    parts.append(cockpit_url)
    return title, " — ".join(parts)


def build_resolved_message(projet, cockpit_url):
    """Spec .55: "un push de fin pour une Urgent résolue"."""
    return RESOLVED_TITLE, "%s — %s" % (projet or DEFAULT_PROJECT, cockpit_url)


def build_grouped_message(count, cockpit_url):
    """Spec .58's fixed literal phrase: "N autres demandes — voir le
    cockpit"."""
    return "%d %s" % (count, GROUPED_SUFFIX), cockpit_url


def build_test_message():
    return TEST_TITLE, TEST_BODY
