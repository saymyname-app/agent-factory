"""Which proposal goes where (ADR-0029, 2026-10-07): the one reading of a
``proposal`` bead's class that the inbox (« Ce qui t'attend ») and the
health zone share, so a proposal is never counted twice and never lost
between them.

A proposal carries ``gc.proposal_classe`` from its creation by
``bin/proposal-door`` (ADR-0029 point 1):

* ``decision`` -- changes what Benjamin sees or must do; it is his to
  decide, so it is an Operator Request (ADR-0029 point 3).
* ``maintenance`` -- a defect of the factory the Mayor corrects itself
  under ADR-0029's authorization; it never enters « Ce qui t'attend » and
  is shown in the health zone and in the journal (point 2).

Two kinds of proposal predate the class:

* one created by the door before the class existed (its fields are there,
  the class is not) is still Benjamin's to treat in the Cockpit -- the
  eight proposals open on 2026-10-07 are his; it reads as ``decision``;
* one created before the door (no ``gc.proposal_*`` field at all) is not
  readable as a request: it is a health anomaly « proposition à
  reformuler par la porte » and leaves the inbox (point 4).

Pure functions of a bead dict as ``bd list --json`` returns it; no I/O.
"""

PROPOSAL_LABEL = "proposal"
CLASSE_KEY = "gc.proposal_classe"
STATE_KEY = "gc.proposal_state"

DECISION = "decision"
MAINTENANCE = "maintenance"
SANS_CHAMPS = "sans_champs"
CLASSES = (MAINTENANCE, DECISION)

# States in which nothing waits on anyone any more, or in which the factory
# itself holds the proposal: accepted, rejected, resolved by a merged
# delivery (``resolue``, bin/proposal-door resoudre), taken over as a
# maintenance bead (``prise_en_charge``, ADR-0029 point 2).
CLOSED_STATES = frozenset({"a_planifier", "rejetee", "resolue"})
PRISE_EN_CHARGE = "prise_en_charge"

# The fields the door has always written: a proposal with none of them was
# never written by the door (ADR-0029 point 4).
DOOR_FIELDS = ("gc.proposal_quoi", "gc.proposal_pourquoi", "gc.proposal_que_faire")


def is_proposal(bead):
    return isinstance(bead, dict) and PROPOSAL_LABEL in (bead.get("labels") or [])


def state_of(bead):
    metadata = (bead or {}).get("metadata") or {}
    return metadata.get(STATE_KEY) or "ouverte"


def is_pending(bead):
    """Open, labelled ``proposal``, neither decided by the operator nor
    resolved by a delivery. A maintenance proposal taken over by the
    factory is *not* pending: nothing waits on the operator."""
    if not is_proposal(bead) or bead.get("status") == "closed":
        return False
    state = state_of(bead)
    return state not in CLOSED_STATES and state != PRISE_EN_CHARGE


def classe_of(bead):
    """``decision`` / ``maintenance`` / ``sans_champs`` for a bead labelled
    ``proposal``; ``None`` for any other bead. A proposal with fields but
    no class (door before ADR-0029) reads as ``decision``; an unknown
    class value is read as ``decision`` too -- a producer's mistake must
    reach the operator, never vanish silently (ADR-0029 point 6: in doubt,
    ``decision``)."""
    if not is_proposal(bead):
        return None
    metadata = bead.get("metadata") or {}
    classe = metadata.get(CLASSE_KEY)
    if classe == MAINTENANCE:
        return MAINTENANCE
    if classe == DECISION:
        return DECISION
    if not any(metadata.get(key) for key in DOOR_FIELDS):
        return SANS_CHAMPS
    return DECISION


def is_open_decision(bead):
    """The inbox's condition (ADR-0029 points 2-4): a pending proposal of
    class ``decision``."""
    return is_pending(bead) and classe_of(bead) == DECISION


def maintenance_in_progress(beads):
    """Every open maintenance proposal the factory holds (state
    ``prise_en_charge``, or still ``ouverte`` while its bead is being
    filed): ``[{"id", "since"}]`` for the health zone."""
    out = []
    for bead in beads or ():
        if not is_proposal(bead) or bead.get("status") == "closed":
            continue
        if classe_of(bead) != MAINTENANCE:
            continue
        if state_of(bead) in CLOSED_STATES:
            continue
        metadata = bead.get("metadata") or {}
        out.append({"id": bead.get("id") or "", "since": metadata.get("gc.proposal_horodatage")})
    return out


def sans_champs(beads):
    """Every pending proposal no door wrote (ADR-0029 point 4): to
    reformulate through ``bin/proposal-door create`` or to close."""
    return [
        {"id": bead.get("id") or ""}
        for bead in beads or ()
        if is_pending(bead) and classe_of(bead) == SANS_CHAMPS
    ]
