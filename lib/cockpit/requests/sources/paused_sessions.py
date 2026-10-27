"""A session the Factory paused -> À faire (B, af-4uzgzm; Spec af-fgcw0d,
user story 29: « relancer une session ou un order que l'usine a mis en
pause, afin de reprendre le travail sans agent »).

The session loop guard of the Factory (``bin/factory-session-loop-guard``)
suspends a session that wakes and stops in a loop, and files one open bead
for it: titled ``[session-loop] <session>``, carrying ``gc.session_id`` and
``gc.source=factory-session-loop-guard``. Its own ``resume`` wakes the
session and closes that bead. While the bead is open, the session waits on
the operator: a request « Une session de l’usine est en pause », whose
gesture is « Relancer » (:mod:`cockpit.actions.relancer`).

An order the Factory paused is read beside it
(:mod:`cockpit.requests.sources.paused_orders`).

Pure: a list of beads as ``bd list --json`` returns them.
"""
from cockpit.requests.builder import _parse_iso
from cockpit.requests.model import A_FAIRE, OperatorRequest

TYPE_SESSION_EN_PAUSE = "session_en_pause"
LOOP_GUARD = "factory-session-loop-guard"
FACTORY = "Usine"


def paused_session_of(bead):
    """The session a bead of the loop guard says it paused, or ``None``."""
    if not isinstance(bead, dict) or bead.get("status") == "closed":
        return None
    metadata = bead.get("metadata") or {}
    if metadata.get("gc.source") != LOOP_GUARD:
        return None
    return metadata.get("gc.session_id") or None


def build_paused_session_requests(beads, verifie_a=None):
    requests = []
    for bead in beads or ():
        session = paused_session_of(bead)
        if session is None:
            continue
        metadata = bead.get("metadata") or {}
        since = _parse_iso(metadata.get("gc.escalation_mayor_paged_at")) or _parse_iso(bead.get("created_at"))
        requests.append(OperatorRequest(
            id=bead.get("id") or "",
            type=TYPE_SESSION_EN_PAUSE,
            niveau=A_FAIRE,
            quoi="Une session de l’usine est en pause",
            pourquoi="Elle se réveillait et s’arrêtait en boucle : l’usine l’a suspendue.",
            que_faire=[{
                "lettre": "a",
                "option": "Relancer la session",
                "consequence": "Elle reprend son travail ; l’usine la remet en pause si la boucle revient.",
                "recommande": True,
                "raison": "La pause attend un geste, rien ne la lève seul.",
            }],
            projet=FACTORY,
            depuis_quand=since,
            verifie_a=verifie_a,
            lien=bead.get("id") or "",
            texte_origine={"quoi": bead.get("title") or "", "pourquoi": bead.get("description") or ""},
            precisions="Session suspendue : %s" % session,
            titre=session,
        ))
    return requests
