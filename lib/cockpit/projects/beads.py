"""The extra Beads reads a Chantier's stage needs beyond the cockpit's
normal open-beads-only source (spec af-oohx2x "Calcul d'étape des
chantiers"; CONTEXT.md: Chantier).

``cockpit.core.beads_source.read_operator_beads`` only ever returns open
beads (plus anything still carrying ``gc.needs_benjamin``) -- a closed
convoy (Livré) or a closed ticket already merged under a still-open convoy
(Livraison's "mergés x/y") would never appear in it. Both a convoy and every
ticket it tracks carry ``gc.graph_digest`` (``bin/ticket-graph-publish``)
whatever their status, so one extra targeted read -- the same
``--has-metadata-key`` shape ``read_operator_beads`` already uses for
``gc.needs_benjamin`` -- is enough to see every bead a chantier's Livraison
and Livré stages need, open or closed.

A Planning Map's decision children (Cadrage's "x/y décisions") are not
reachable this way -- they carry no shared metadata key, only a native
``parent`` link ``bd children`` resolves server-side
(``bin/planning-map``'s own ``bd_children``) -- so that is a second, plain
``bd children <map_id>`` read.
"""
from cockpit.core.beads_source import read_beads_json

GRAPH_DIGEST_KEY = "gc.graph_digest"


def read_convoy_beads(bd_bin="bd", timeout=10):
    """Every bead -- open or closed -- carrying ``gc.graph_digest``: every
    convoy and every ticket it tracks."""
    return read_beads_json(
        ["list", "--all", "--limit", "0", "--has-metadata-key", GRAPH_DIGEST_KEY],
        bd_bin=bd_bin,
        timeout=timeout,
    )


def read_map_children(map_id, bd_bin="bd", timeout=10):
    """A Planning Map Bead's decision children, for Cadrage's "x/y
    décisions" (``bin/planning-map create-ticket`` shapes each one)."""
    return read_beads_json(["children", map_id], bd_bin=bd_bin, timeout=timeout)
