"""Operator Actions on a chantier (spec af-oohx2x §"Actions opérateur":
"accepter un chantier Livré par un clic", "« Pas bon -> agent »"; T20).

Lives in :mod:`cockpit.projects`, not :mod:`cockpit.actions` (out of this
ticket's declared scope, gc.scope_paths: lib/cockpit/projects/**,
lib/cockpit/ui/projects/**) -- it reuses that package's existing
trace/prompt helpers unchanged, which is importing them, not touching
them.

Accepter writes the same two-step-confirmed trace every other Operator
Action writes (:mod:`cockpit.actions.trace`), stamping
:data:`ACCEPTED_KEY` on the convoy bead so the very next stage computation
(:mod:`cockpit.projects.stage`) reads Accepté straight off the bead -- no
cockpit-side copy of its own (spec: "aucune copie locale").
"""
import json
import subprocess

from cockpit.actions import trace
from cockpit.actions.continuer import build_prompt

ACCEPTED_KEY = "gc.cockpit_chantier_accepted"
ACCEPTED_AT_KEY = "gc.cockpit_chantier_accepted_at"
# A convoy of the Delivery Workflow (Spec af-wf4w5r §11, T29): its
# acceptance is Benjamin's answer recorded by bin/owner-answer with his
# words, the commit and the fingerprint of the dossier -- never this click,
# which knows none of the three.
NEW_FLOW_MARK_KEY = "gc.flow.mark"
REFUS_NOUVEAU_FLUX = (
    "Ce chantier est livré par le nouveau flux : son acceptation s'enregistre à l'Acceptance Session, avec tes mots, "
    "le commit et l'empreinte du dossier (bin/owner-answer), pas par ce bouton. Rien n'est écrit."
)


class AccepterError(Exception):
    pass


def accepter_chantier(bd_bin, convoy_id, clock, acteur="benjamin", confirm=False):
    """Deux temps (spec .34): a call with ``confirm=False`` (the first
    tap) is refused before anything is touched -- no subprocess call, no
    trace -- the same contract :mod:`cockpit.actions.registry` enforces
    for répondre/accepter-proposition/relancer."""
    if not confirm:
        raise AccepterError("confirmation requise")
    if _carries_new_flow_mark(bd_bin, convoy_id):
        raise AccepterError(REFUS_NOUVEAU_FLUX)
    quand = trace.now_iso(clock)
    try:
        trace.write_trace(
            bd_bin,
            convoy_id,
            quoi="accepter_chantier",
            sur_quoi=convoy_id,
            option_ou_raison="",
            quand_iso=quand,
            acteur=acteur,
            extra_metadata={ACCEPTED_KEY: "true", ACCEPTED_AT_KEY: quand},
        )
    except trace.TraceError as exc:
        raise AccepterError(str(exc))
    return {"ok": True, "bead_id": convoy_id, "quand": quand}


def _carries_new_flow_mark(bd_bin, convoy_id, timeout=10):
    """Whether the convoy carries the new-flow mark. A convoy that cannot be
    read is not accepted on a guess."""
    try:
        completed = subprocess.run([bd_bin, "show", convoy_id, "--json"], capture_output=True, text=True, timeout=timeout)
        beads = json.loads(completed.stdout) if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        beads = None
    bead = beads[0] if isinstance(beads, list) and beads else beads
    if not isinstance(bead, dict):
        raise AccepterError("chantier %s illisible : rien n'est écrit" % convoy_id)
    return bool((bead.get("metadata") or {}).get(NEW_FLOW_MARK_KEY))


def pas_bon_vers_agent(convoy_id, titre, dossier=None):
    """"Pas bon -> agent" (spec .31): a ready prompt copied without
    reopening the frozen graph. Pure text, like
    :func:`cockpit.actions.continuer.build_prompt`, which it wraps with a
    chantier-shaped "quoi" -- the cockpit never executes it itself."""
    quoi = "Le chantier %s (%s) livré n'est pas bon : corriger sans rouvrir le graphe." % (
        convoy_id,
        titre or convoy_id,
    )
    return build_prompt(convoy_id, quoi, dossier=dossier)
