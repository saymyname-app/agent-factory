"""Chantier-level anomalies for the health zone (spec af-oohx2x §"Étapes
d'un chantier": "un convoi fermé avec un enfant non mergé... anomalie en
santé"; §"Suivre les projets" .48: incohérences de roadmap; T20).

Pure functions of already-read beads/roadmap steps -- wiring these into
the running health page (:mod:`cockpit.health`) is out of this ticket's
declared scope (gc.scope_paths: lib/cockpit/projects/**, lib/cockpit/ui/
projects/**), the same precedent T19/T15 set: this module is its own
public interface, exercised directly by tests.
"""
from cockpit.projects.stage import CONVOY_ISSUE_TYPE, GRAPH_DIGEST_KEY, _is_delivery_ticket, _title

STATUT_FAIT = "done"
STATUT_A_FAIRE = "todo"

# Stages that count as "chantier ouvert" for the roadmap-incoherence check
# -- everything short of its last applicable stage (termine on the
# Chantier handles Accepté-masqué/Promu itself; a chantier reaching here
# never termine).
_STAGE_ACTIF_AVEC_TRAVAIL = {"Livraison", "Livré", "Accepté", "Promu"}


def convoy_closed_with_unmerged_child(beads):
    """"Un convoi fermé avec un enfant non mergé" (spec §"Étapes d'un
    chantier")."""
    beads = beads or []
    out = []
    for bead in beads:
        if not isinstance(bead, dict) or bead.get("issue_type") != CONVOY_ISSUE_TYPE:
            continue
        if bead.get("status") != "closed":
            continue
        digest = (bead.get("metadata") or {}).get(GRAPH_DIGEST_KEY)
        if not digest:
            continue
        unmerged = [t for t in beads if _is_delivery_ticket(t, digest) and t.get("status") != "closed"]
        if unmerged:
            out.append(
                {
                    "convoy_id": bead.get("id") or "",
                    "titre": _title(bead),
                    "detail": "convoi fermé avec %d ticket(s) non mergé(s)" % len(unmerged),
                }
            )
    return out


def roadmap_incoherences(chantiers, steps_by_project):
    """"Les incohérences de roadmap (étape « fait » avec un chantier
    ouvert, chantier visant une étape « à faire »)" (spec .48).

    ``chantiers``: :class:`~cockpit.projects.model.Chantier` rows carrying
    a ``planning_run_target`` (set by :mod:`cockpit.projects.stage` from
    the defining bead's metadata) and a ``projet``. ``steps_by_project``:
    ``{project_id: [{"id": ..., "status": ...}, ...]}``, a project's full
    roadmap step list (not just the current one)."""
    out = []
    for chantier in chantiers or []:
        if not chantier.planning_run_target or not chantier.projet:
            continue
        steps = {s.get("id"): s for s in (steps_by_project or {}).get(chantier.projet) or []}
        step = steps.get(chantier.planning_run_target)
        if step is None:
            continue
        status = step.get("status")
        if status == STATUT_FAIT and chantier.stage in _STAGE_ACTIF_AVEC_TRAVAIL and not chantier.termine:
            out.append(
                {
                    "chantier_id": chantier.id,
                    "titre": chantier.titre,
                    "detail": "étape %s marquée faite alors que %s est encore ouvert" % (
                        chantier.planning_run_target, chantier.id,
                    ),
                }
            )
        elif status == STATUT_A_FAIRE and chantier.stage in _STAGE_ACTIF_AVEC_TRAVAIL:
            out.append(
                {
                    "chantier_id": chantier.id,
                    "titre": chantier.titre,
                    "detail": "%s vise l'étape %s encore à faire" % (chantier.id, chantier.planning_run_target),
                }
            )
    return out
