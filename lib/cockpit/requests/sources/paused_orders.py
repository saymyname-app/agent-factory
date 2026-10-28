"""An order the Factory paused -> À faire (BR, af-eyc5ah; Spec af-fgcw0d,
user story 29: « relancer une session ou un order que l'usine a mis en
pause, afin de reprendre le travail sans agent »).

The door of pause and resume of an order (``bin/order-pause``,
af-npz9v1.15) records a pause as one open bead of the tracker, carrying
the order it holds (``gc.order_pause``), who paused it, when and in what
words (``gc.order_pause_by``, ``_at``, ``_words``, ``_reason``). Its own
``resume`` closes that bead. While the bead is open, the order waits on the
operator: a request « Un ordre de l’usine est en pause », whose gesture is
« Relancer » (:mod:`cockpit.actions.relancer`).

Pure: a list of beads as ``bd list --json`` returns them.
"""
from cockpit.requests.builder import _parse_iso
from cockpit.requests.model import A_FAIRE, OperatorRequest

TYPE_ORDRE_EN_PAUSE = "ordre_en_pause"
PAUSE_KEY = "gc.order_pause"
FACTORY = "Usine"


def paused_order_of(bead):
    """The order an open pause record holds, or ``None``."""
    if not isinstance(bead, dict) or bead.get("status") == "closed":
        return None
    order = (bead.get("metadata") or {}).get(PAUSE_KEY)
    return order if isinstance(order, str) and order else None


def build_paused_order_requests(beads, verifie_a=None):
    requests = []
    for bead in beads or ():
        order = paused_order_of(bead)
        if order is None:
            continue
        metadata = bead.get("metadata") or {}
        since = _parse_iso(metadata.get("gc.order_pause_at")) or _parse_iso(bead.get("created_at"))
        precisions = "Ordre en pause : %s ; posée par %s (« %s »)" % (
            order, metadata.get("gc.order_pause_by") or "?", metadata.get("gc.order_pause_words") or "")
        if metadata.get("gc.order_pause_reason"):
            precisions += " ; raison : %s" % metadata["gc.order_pause_reason"]
        requests.append(OperatorRequest(
            id=bead.get("id") or "",
            type=TYPE_ORDRE_EN_PAUSE,
            niveau=A_FAIRE,
            quoi="Un ordre de l’usine est en pause",
            pourquoi="L’usine ne le lance plus tant que la pause dure.",
            que_faire=[{
                "lettre": "a",
                "option": "Relancer l’ordre",
                "consequence": "Sa prochaine échéance le lance de nouveau.",
                "recommande": True,
                "raison": "La pause attend un geste, rien ne la lève seul.",
            }],
            projet=FACTORY,
            depuis_quand=since,
            verifie_a=verifie_a,
            lien=bead.get("id") or "",
            texte_origine={"quoi": bead.get("title") or "", "pourquoi": bead.get("description") or ""},
            precisions=precisions,
            titre=order,
        ))
    return requests
