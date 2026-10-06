"""The one "Ce qui t'attend" list (spec af-oohx2x §"Demandes opérateur :
types, niveaux, sortie"): every kind of Operator Request the cockpit can
read today, merged and sorted Urgent first, then oldest first.

:mod:`cockpit.requests.builder` turns NEEDS BENJAMIN escalations and open
proposals into requests. T15 and T20 built the other kinds as pure
functions nothing called; this is their caller:

- a Spec or a ticket graph to approve, a ready HITL card ticket
  (:mod:`cockpit.requests.sources`), from the same beads;
- a delivered chantier not yet accepted, an accepted one not yet promoted
  (:mod:`cockpit.projects.demandes`), from the read model's "projets";
- a source unreadable for more than 15 min
  (:mod:`cockpit.requests.sources.readability`), from the read model's own
  read times — so it still shows when Beads itself is the dead source.

Pure: every input is a value the read model already holds.
"""
from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.projects.demandes import chantier_demandes
from cockpit.projects.source import from_value as projects_from_value
from cockpit.requests.builder import build_requests, parse_ack_and_defer
from cockpit.requests.sources.hitl import build_hitl_requests
from cockpit.requests.sources.readability import ILLISIBLE_THRESHOLD_SECONDS, build_readability_requests
from cockpit.requests.sources.specs_and_graphs import build_specs_and_graphs_requests


def assemble_requests(
    beads,
    verifie_a=None,
    defects=None,
    projets_value=None,
    sources=(),
    now=None,
    illisible_after_seconds=ILLISIBLE_THRESHOLD_SECONDS,
    extra_requests=(),
):
    """``beads``: the beads source's last value, or ``None`` when it is
    unknown — bead-derived requests are then absent, never guessed.
    ``projets_value``: the "projets" source's value, or ``None``.
    ``sources``: ``[{"name", "display_name", "last_good_read_at"}]`` for
    every read-model source. ``now``: the read model's clock."""
    requests = []
    if beads is not None:
        requests = build_requests(beads, verifie_a=verifie_a, defects=defects)
        by_id = {b["id"]: b for b in beads if isinstance(b, dict) and b.get("id")}
        for request in build_specs_and_graphs_requests(beads, verifie_a) + build_hitl_requests(beads, verifie_a):
            # Reporter hides these exactly as it hides an À faire escalation
            # (spec .22): the same trace on the same bead.
            _, defer_until = parse_ack_and_defer(by_id.get(request.id) or {})
            if defer_until is not None and verifie_a is not None and defer_until > verifie_a:
                continue
            requests.append(request)

    names = {}
    if projets_value:
        projects, sans_projet = projects_from_value(projets_value)
        names = {p.project_id: p.display_name for p in projects}
        chantiers = [c for p in projects for c in p.chantiers] + sans_projet
        requests.extend(chantier_demandes(chantiers, verifie_a=verifie_a))

    if now is not None:
        for request in build_readability_requests(
            sources, now, verifie_a=now, threshold_seconds=illisible_after_seconds
        ):
            # Nothing on a bead could hide it: it leaves when the source reads again.
            request.reportable = False
            requests.append(request)

    # Raised by the cockpit's own parts, already built (the stop driver's
    # « l'arrêt n'avance plus », the Tailscale key at J-14): no bead could
    # hide them, they leave when their cause does.
    for request in extra_requests:
        request.reportable = False
        requests.append(request)

    # One request per source object: a Spec that also carries a NEEDS
    # BENJAMIN is that question, not a second row.
    unique, seen = [], set()
    for request in requests:
        if request.id in seen:
            continue
        seen.add(request.id)
        unique.append(request)

    # The project's displayed name, not its key (spec .73); "usine" when
    # the source named none is the factory project's own name when declared.
    by_lowered_name = {name.lower(): name for name in names.values()}
    for request in unique:
        request.projet = names.get(request.projet) or by_lowered_name.get(
            (request.projet or "").lower(), request.projet
        )

    unique.sort(key=lambda r: r.sort_key())
    return unique


def assemble_from_snapshot(
    snapshot, now, defects=None, illisible_after_seconds=ILLISIBLE_THRESHOLD_SECONDS, extra_requests=()
):
    """The list as the read model holds it right now. Returns ``(requests,
    beads_row, beads_known)``; with Beads unknown the list holds only what
    does not come from Beads, and the caller says the list is incomplete."""
    beads_row = snapshot.get("beads")
    beads_known = beads_row is not None and beads_row["freshness"] != UNKNOWN
    projets_row = snapshot.get("projets")
    projets_known = projets_row is not None and projets_row["freshness"] != UNKNOWN
    requests = assemble_requests(
        beads_row["value"] if beads_known else None,
        verifie_a=beads_row["read_at"] if beads_known else now,
        defects=defects,
        projets_value=projets_row["value"] if projets_known else None,
        sources=[
            {
                "name": name,
                "display_name": row["display_name"],
                "last_good_read_at": row["read_at"] if row["read_at"] is not None else row["registered_at"],
            }
            for name, row in snapshot.items()
            if row["freshness"] != FRESH
        ],
        now=now,
        illisible_after_seconds=illisible_after_seconds,
        extra_requests=extra_requests,
    )
    return requests, beads_row, beads_known
