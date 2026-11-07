"""Whether a piece of the evidence store is still what the tracker
fingerprints (C2b, af-ofz29f; Spec af-fgcw0d, user stories 140 and 144).

    pieces = EvidencePieces(store)
    pieces.state(spec, ticket, piece, digest)   # PRESENT, ABSENT or CHANGED

bin/evidence-capture files each piece at ``<store>/<spec>/<ticket>/<piece>.json``
and its fingerprint (``sha256:`` of those bytes) on the ticket
(``gc.flow.evidence.<piece>``); the promotion of an accepted Outcome purges
the folder of its Spec and leaves the fingerprints (docs/EVIDENCE_STORE.md).
A piece is present when its file holds the bytes fingerprinted, absent when
no file is there -- purged, or never on this host --, changed otherwise.
Nothing is written; no file is read but the piece named.
"""
import hashlib
import os

from account_home import account_home

PRESENT, ABSENT, CHANGED = "présente", "absente", "modifiée"


def store_dir(env=None):
    """The evidence store, as bin/evidence-capture finds it."""
    configured = (os.environ if env is None else env).get("EVIDENCE_STORE_DIR")
    return configured or str(account_home() / ".local" / "state" / "agent-factory-evidence")


class EvidencePieces:
    def __init__(self, store):
        self.store = store

    def state(self, spec, ticket, piece, digest):
        if not (spec and ticket and piece) or os.sep in piece or piece.startswith("."):
            return ABSENT
        path = os.path.join(self.store, spec, ticket, piece + ".json")
        try:
            with open(path, "rb") as filed:
                data = filed.read()
        except OSError:
            return ABSENT
        return PRESENT if "sha256:" + hashlib.sha256(data).hexdigest() == digest else CHANGED
