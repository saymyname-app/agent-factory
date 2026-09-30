"""The "other" Operator Request sources (T15, af-icxjc4 — Spec af-oohx2x
§"Demandes opérateur : types, niveaux, sortie"): Spec/graphe à approuver,
rituel dû, ticket de carte HITL prêt non lancé, source illisible depuis
plus de 15 min, signal de type inconnu.

Each module here is a pure function from a source's already-read raw
signals (the same shape :mod:`cockpit.requests.builder` takes for beads)
to a list of :class:`~cockpit.requests.model.OperatorRequest`. None of
them touch ``requests/builder.py`` or ``requests/model.py`` (out of this
ticket's declared scope, gc.scope_paths) — merging these lists into the
single sorted "Ce qui t'attend" list, and wiring them to live sources, is
the wiring ticket's job. A caller that wants one combined, sorted list
can concatenate the outputs and sort with
:meth:`~cockpit.requests.model.OperatorRequest.sort_key`, exactly as
``build_requests`` already does for escalations and proposals.
"""
from cockpit.requests.sources.hitl import build_hitl_requests
from cockpit.requests.sources.readability import build_readability_requests
from cockpit.requests.sources.rituals import build_ritual_requests
from cockpit.requests.sources.specs_and_graphs import build_specs_and_graphs_requests
from cockpit.requests.sources.unknown_signal import build_unknown_signal_requests

__all__ = [
    "build_hitl_requests",
    "build_readability_requests",
    "build_ritual_requests",
    "build_specs_and_graphs_requests",
    "build_unknown_signal_requests",
]
