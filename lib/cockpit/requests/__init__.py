"""The Operator Request engine (spec af-oohx2x, "Moteur des Demandes
opérateur"; CONTEXT.md "Operator Request", "Ce qui t'attend").

Turns the beads read model already carries (NEEDS BENJAMIN escalations,
open proposals) into typed :class:`~cockpit.requests.model.OperatorRequest`
objects. The cockpit infers no field: it only validates presence and
applies the fixed repli (:mod:`cockpit.text.fallback`) when a producer left
one out.
"""
