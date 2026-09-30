"""Source illisible depuis plus de 15 min -> À faire (T15, af-icxjc4 —
Spec af-oohx2x §"Demandes opérateur" and .17: "qu'une source illisible
depuis plus de 15 min devienne elle-même une demande À faire, afin
qu'une panne de lecture ne passe pas inaperçue").

This is a fixed generic threshold (15 min), independent of any one
source's own Validity window (``cockpit.core.freshness``: SSE gc 2 min,
Beads 5 min, GitHub 10 min, rituals 1 h) — a source can be legitimately
STALE-but-not-UNKNOWN by its own window and still need this request: the
15-minute clock here is about how long reading has been *failing*, not
about how old the last good value is allowed to look on screen.

Input: ``sources``, one dict per tracked source —
``{"name": str, "display_name": str or None, "last_good_read_at": epoch
or None}``. ``last_good_read_at`` is the timestamp of the last
successful, complete read (``cockpit.core.readmodel.ReadModel`` already
tracks this as ``read_at``); ``None`` means never read even once, in
which case the caller passes the time the cockpit started watching it
(the read model's own registration time) so the request still carries a
meaningful "depuis quand" instead of "since forever". A source exits
this list the instant a read succeeds again — exit at-source (spec .15).
"""
from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, OperatorRequest

TYPE_SOURCE_ILLISIBLE = "source_illisible"

ILLISIBLE_THRESHOLD_SECONDS = 15 * 60


def build_readability_requests(sources, now, verifie_a=None, threshold_seconds=ILLISIBLE_THRESHOLD_SECONDS):
    verifie_a = now if verifie_a is None else verifie_a
    requests = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        since = source.get("last_good_read_at")
        if since is None:
            continue
        if now - since <= threshold_seconds:
            continue
        name = source.get("name") or ""
        display_name = source.get("display_name") or name
        requests.append(
            OperatorRequest(
                id="source:%s" % name,
                type=TYPE_SOURCE_ILLISIBLE,
                niveau=A_FAIRE,
                quoi="Une source ne répond plus : %s" % display_name,
                pourquoi="Cette source est illisible depuis plus de 15 min — une panne de lecture pourrait passer inaperçue.",
                que_faire=[
                    {
                        "lettre": "a",
                        "option": "Revérifier maintenant",
                        "consequence": "Force une nouvelle lecture de cette source.",
                        "recommande": True,
                        "raison": "La cause la plus fréquente est une panne temporaire.",
                    }
                ],
                projet=DEFAULT_PROJECT,
                depuis_quand=since,
                verifie_a=verifie_a,
                lien="",
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    return requests
