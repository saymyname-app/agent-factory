"""Usine muette -> Urgent (B, af-4uzgzm; Spec af-fgcw0d, user story 6: « je
veux qu'une usine muette soit Urgent, afin d'être prévenu quand plus rien ne
tourne »).

The heartbeat of the cockpit goes out only while its main sources -- the
supervisor and the tracker -- read fresh (:mod:`cockpit.heartbeat.emitter`):
once one of them stops answering, nothing tells the outside the Factory is
alive. When that silence lasts longer than the threshold (15 min, the
alert delay of the heartbeat), the cockpit says it itself, as an Urgent
request: « Usine muette ». It leaves as soon as both read fresh again.

Pure: ``snapshot`` is the read model's snapshot, ``now`` its clock.
"""
from datetime import datetime

from cockpit.core.freshness import FRESH
from cockpit.core.readmodel import PARIS
from cockpit.requests.model import URGENT, OperatorRequest

TYPE_USINE_MUETTE = "usine_muette"
REQUEST_ID = "usine-muette"
SILENCE_ALERT_SECONDS = 15 * 60
# The main sources: those the heartbeat waits on.
MAIN_SOURCES = ("gc", "beads")
FACTORY = "Usine"


def silent_since(snapshot):
    """Since when a main source has not answered: the last good reading of
    the first one to fall silent (when it was registered, if it never
    answered), or ``None`` while they all read fresh."""
    since = []
    for name in MAIN_SOURCES:
        row = snapshot.get(name)
        if row is None or row["freshness"] == FRESH:
            continue
        last = row["read_at"] if row["read_at"] is not None else row.get("registered_at")
        if last is not None:
            since.append(last)
    return min(since) if since else None


def build_silence_request(snapshot, now, threshold_seconds=SILENCE_ALERT_SECONDS):
    """The request « Usine muette » when the silence lasted longer than
    ``threshold_seconds``, else ``None``."""
    since = silent_since(snapshot)
    if since is None or now - since <= threshold_seconds:
        return None
    silent = [snapshot[name]["display_name"] or name for name in MAIN_SOURCES
              if snapshot.get(name) is not None and snapshot[name]["freshness"] != FRESH]
    hhmm = datetime.fromtimestamp(since, tz=PARIS).strftime("%H:%M")
    return OperatorRequest(
        id=REQUEST_ID,
        type=TYPE_USINE_MUETTE,
        niveau=URGENT,
        quoi="Usine muette",
        pourquoi="Plus rien ne répond depuis %s (Paris) : %s. Le signal de vie de l’usine ne part plus."
                 % (hhmm, ", ".join(silent)),
        que_faire=[{
            "lettre": "a",
            "option": "Vérifier l’usine",
            "consequence": "La page Usine dit quelle connexion ne répond plus et depuis quand.",
            "recommande": True,
            "raison": "Une machine arrêtée ou une source coupée se voit d’abord là.",
        }],
        projet=FACTORY,
        depuis_quand=since,
        verifie_a=now,
        lien="/usine",
        precisions="Sources muettes : %s. Dernière lecture : %s (Paris)." % (", ".join(silent), hhmm),
        reportable=False,
    )
