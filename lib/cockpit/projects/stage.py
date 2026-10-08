"""Pure computation of a Chantier's stage from Beads (spec af-oohx2x
"Calcul d'étape des chantiers" / "Étapes d'un chantier"; GLOSSARY.md:
Chantier). No I/O -- every function here takes an already-read bead list
(:mod:`cockpit.projects.beads`) and returns
:class:`cockpit.projects.model.Chantier` rows.

Project key resolution (spec .12, T05): a chantier's project is whichever
bead defines its current stage -- the map for Cadrage, the Spec for Spec,
the draft graph bead for Graphe, the convoy for Livraison/Livré/Accepté/
Promu -- reading ``metadata["gc.project_id"]`` directly. ``None`` (no key
at all) is passed through unresolved; the caller
(:mod:`cockpit.projects.builder`) is the one that turns that into "Sans
projet" plus a counted producer defect, because only it holds the shared
:class:`~cockpit.requests.defects.DefectCounter`.

T20 adds: the overlaid état (:mod:`cockpit.projects.etat`) on every
function below; Accepté/Promu and the "dev a N commits d'avance" readiness
check on ``convoy_chantiers`` (git facts injected via ``promotion_results``
-- this module stays I/O-free, :mod:`cockpit.projects.builder` wires
:mod:`cockpit.projects.promotion`'s reads); ``termine``/``abandonne`` for
the historique (spec .46).
"""
from cockpit.projects import etat as etat_mod
from cockpit.projects.model import ACCEPTE, CADRAGE, GRAPHE, LIVRAISON, LIVRE, PROMU, SPEC, Chantier

MAP_LABEL = "wayfinder:map"
DRAFT_GRAPH_LABEL = "ticket-graph-draft"
APPROVED_GRAPH_LABEL = "approved-ticket-graph"
DELIVERY_LABEL = "delivery-plane"
CONVOY_ISSUE_TYPE = "convoy"
PROJECT_KEY = "gc.project_id"
GRAPH_DIGEST_KEY = "gc.graph_digest"
DELIVERY_STATUS_KEY = "gc.delivery_status"
DISPATCH_RIG_KEY = "gc.dispatch_rig"
DELIVERY_STATUS_WAITING = "waiting"
DRAFT_SPEC = "DRAFT_SPEC"
APPROVED_SPEC = "APPROVED_SPEC"

NEEDS_BENJAMIN_KEY = "gc.needs_benjamin"
MAYOR_FIRST_KEY = "gc.mayor_first_since"
ABANDON_REASON_KEY = "gc.chantier_abandon_reason"

# Accepter chantier's trace (cockpit.projects.actions) stamps this on the
# convoy bead -- the cockpit keeps no copy of its own (spec: "aucune copie
# locale de l'état des actions").
ACCEPTED_KEY = "gc.cockpit_chantier_accepted"

# When a delivered chantier asks Benjamin for his acceptance (2026-10-07).
# Intent (Benjamin, his words, 2026-10-07): « on me demande d'accepter un
# truc je n'ai aucune idée de ce que c'est exactement […] Soit on rend
# l'humain vraiment utile en le guidant, soit on le skip » ; then, on the
# proposal to drop the request for chantiers delivered before D01 and to
# send C01 back to its seven-day criteria: « ok fait tout ca ».
# Mechanism (agent interpretation): a closed convoy asks for acceptance
# only when there is something to judge it on --
#   * it carries the new-flow mark (bin/convoy-state: the Delivery Workflow,
#     Spec af-wf4w5r, which hands over an Evidence Pack), or
#   * it carries ACCEPTANCE_NOTE_KEY: one line saying what to look at,
#     shown as the request's « pourquoi ».
# A convoy with neither was delivered by the flow that merged every ticket
# to the protected branch as it went and closed by itself: nothing is left
# to judge and the button changed nothing but a label. It is shown as
# delivered, in the historique, and asks nothing. It does not accept it in
# Benjamin's name (no ACCEPTED_KEY is written) and changes nothing for a
# convoy of the new flow. To undo: treat every closed convoy as before
# (drop the `nothing_to_judge` branch below).
NEW_FLOW_MARK_KEY = "gc.flow.mark"
ACCEPTANCE_NOTE_KEY = "gc.cockpit_acceptance_note"
DETAIL_LIVRE_SANS_ACCEPTATION = "Livré avant le flux d'acceptation : rien à accepter"


def _accepted(metadata):
    """Whether Benjamin accepted the chantier. A convoy of the new flow is
    accepted by his recorded answer (bin/owner-answer, T29, Spec af-wf4w5r
    §11), which replaces the cockpit's own key there; any other convoy by
    the trace of the cockpit's click, as before."""
    if metadata.get(NEW_FLOW_MARK_KEY):
        # Deferred import: lib/ is on the path of every cockpit entry point.
        from convoy_state import owner_answer_of

        return (owner_answer_of(metadata) or {}).get("response") == "accepted"
    return str(metadata.get(ACCEPTED_KEY, "")).lower() == "true"


def _project_of(bead):
    return (bead.get("metadata") or {}).get(PROJECT_KEY)


def _title(bead):
    return bead.get("title") or bead.get("id") or ""


def _needs_benjamin(bead):
    value = (bead.get("metadata") or {}).get(NEEDS_BENJAMIN_KEY)
    return bool(value) and value != "none"


def _mayor_first(bead):
    return bool((bead.get("metadata") or {}).get(MAYOR_FIRST_KEY))


def _etat_for(primary_bead, extra_beads=(), a_toi_de_jouer=False, cible=None, bloque_extra=False):
    """Shared état computation (spec "états superposés") for every stage
    builder below: ``primary_bead`` is the bead defining the chantier's
    current stage; ``extra_beads`` are other beads belonging to it (e.g. a
    convoy's tracked tickets) that can also carry a NEEDS BENJAMIN or a
    Mayor-first escalade. ``cible`` is the chantier id the "à toi de
    jouer" state links to; a NEEDS BENJAMIN found on one of the
    ``extra_beads`` links to that bead instead, so "problème remonté"
    always points at the bead actually carrying the question."""
    candidates = [primary_bead] + [b for b in extra_beads if isinstance(b, dict)]
    for bead in candidates:
        if _needs_benjamin(bead):
            return etat_mod.resolve(probleme_remonte=True, probleme_remonte_cible=bead.get("id") or cible)
    if a_toi_de_jouer:
        return etat_mod.resolve(a_toi_de_jouer=True, a_toi_de_jouer_cible=cible)
    bloque = bloque_extra or any(_mayor_first(bead) for bead in candidates)
    if bloque:
        return etat_mod.resolve(bloque=True)
    return etat_mod.resolve()


def cadrage_chantiers(beads, children_by_map_id=None):
    """Étape 1 -- "carte wayfinder:map ouverte (détail : décisions x/y)".
    ``children_by_map_id``: ``{map_id: [decision beads]}``, from
    :func:`cockpit.projects.beads.read_map_children`; a map with no entry
    (read not yet attempted, or it has no children) shows 0/0."""
    children_by_map_id = children_by_map_id or {}
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        labels = bead.get("labels") or []
        if MAP_LABEL not in labels or bead.get("status") == "closed":
            continue
        children = children_by_map_id.get(bead.get("id"), [])
        total = len(children)
        closed = sum(1 for c in children if isinstance(c, dict) and c.get("status") == "closed")
        chantier_etat, chantier_cible = _etat_for(bead, extra_beads=children, cible=bead.get("id"))
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=CADRAGE,
                detail="Cadrage : %d/%d décisions" % (closed, total),
                etat=chantier_etat,
                etat_cible=chantier_cible,
            )
        )
    return out


def spec_chantiers(beads):
    """Étape 2 -- "bead Spec en DRAFT_SPEC"."""
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        metadata = bead.get("metadata") or {}
        if metadata.get("spec_state") != DRAFT_SPEC:
            continue
        chantier_etat, chantier_cible = _etat_for(bead, a_toi_de_jouer=True, cible=bead.get("id"))
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=SPEC,
                detail="Spec prête : à approuver",
                etat=chantier_etat,
                etat_cible=chantier_cible,
                planning_run_target=metadata.get("planning_run_target"),
            )
        )
    return out


def graphe_chantiers(beads):
    """Étape 3 -- "Spec APPROVED_SPEC, convoi pas encore publié": a draft
    graph bead (``ticket-graph-draft`` label, no ``approved-ticket-graph``
    label yet) whose source Spec is already approved."""
    by_id = {b.get("id"): b for b in beads or [] if isinstance(b, dict) and b.get("id")}
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        labels = bead.get("labels") or []
        if DRAFT_GRAPH_LABEL not in labels or APPROVED_GRAPH_LABEL in labels:
            continue
        metadata = bead.get("metadata") or {}
        spec_id = metadata.get("spec_id")
        spec_bead = by_id.get(spec_id) if spec_id else None
        if spec_bead is None or (spec_bead.get("metadata") or {}).get("spec_state") != APPROVED_SPEC:
            continue
        chantier_etat, chantier_cible = _etat_for(bead, a_toi_de_jouer=True, cible=bead.get("id"))
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=GRAPHE,
                detail="Graphe de tickets : à approuver",
                etat=chantier_etat,
                etat_cible=chantier_cible,
                planning_run_target=metadata.get("planning_run_target"),
            )
        )
    return out


def _is_delivery_ticket(bead, digest):
    if not isinstance(bead, dict):
        return False
    if bead.get("issue_type") == CONVOY_ISSUE_TYPE:
        return False
    if DELIVERY_LABEL not in (bead.get("labels") or []):
        return False
    return (bead.get("metadata") or {}).get(GRAPH_DIGEST_KEY) == digest


def _convoy_chantiers_all(beads, promotion_results=None):
    """Étapes 4 à 7 -- Livraison, Livré, Accepté, Promu. ``beads`` must
    include closed beads (:func:`cockpit.projects.beads.read_convoy_beads`)
    or a Livré convoy and any already-merged ticket under an open one are
    invisible. ``promotion_results``: ``{convoy_id: {"masque": bool,
    "promu": True|False|None}}`` -- git facts :mod:`cockpit.projects.
    builder` reads via :mod:`cockpit.projects.promotion` for every accepted
    convoy; a convoy with no entry is treated as ``masque: True`` (a
    project's rig declaring no promotion branch at all is the common case,
    spec .41, and the safe default when a read was never attempted).

    Returns every convoy chantier regardless of ``termine`` -- callers
    (:func:`convoy_chantiers`, :func:`convoy_chantiers_historique`)
    partition on that flag."""
    promotion_results = promotion_results or {}
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict) or bead.get("issue_type") != CONVOY_ISSUE_TYPE:
            continue
        bead_id = bead.get("id") or ""
        digest = (bead.get("metadata") or {}).get(GRAPH_DIGEST_KEY)
        if not digest:
            # gc's own "input convoy" beads are convoys too; a chantier's
            # convoy is one a published ticket graph created.
            continue
        tickets = [b for b in beads if _is_delivery_ticket(b, digest)]
        rigs = {(t.get("metadata") or {}).get(DISPATCH_RIG_KEY) for t in tickets} - {None, ""}
        total = len(tickets)
        merged = sum(1 for t in tickets if t.get("status") == "closed")
        en_pr = sum(
            1
            for t in tickets
            if t.get("status") == "in_progress"
            and (t.get("metadata") or {}).get(DELIVERY_STATUS_KEY) == DELIVERY_STATUS_WAITING
        )
        en_cours = sum(1 for t in tickets if t.get("status") == "in_progress") - en_pr
        pret = sum(1 for t in tickets if t.get("status") == "open")

        promu_masque = False
        promu_inconnu = False
        termine = False
        a_regarder = ""
        if bead.get("status") != "closed":
            detail = "%d/%d tickets mergés · %d en cours · %d en PR" % (merged, total, en_cours, en_pr)
            stage = LIVRAISON
            # spec .44: "convoi ouvert sans ticket prêt, en cours ni en
            # PR" -- the silence-is-not-a-blocage carve-out means an empty
            # convoy or one where every ticket is already closed (merged)
            # is bloqué, never a convoy that simply has one ticket moving.
            etat_val, cible = _etat_for(bead, extra_beads=tickets, bloque_extra=(pret + en_cours + en_pr == 0))
        else:
            metadata = bead.get("metadata") or {}
            accepted = _accepted(metadata)
            note = metadata.get(ACCEPTANCE_NOTE_KEY)
            a_regarder = note.strip() if isinstance(note, str) else ""
            nothing_to_judge = not accepted and not a_regarder and not metadata.get(NEW_FLOW_MARK_KEY)
            if nothing_to_judge:
                stage = LIVRE
                detail = DETAIL_LIVRE_SANS_ACCEPTATION
                termine = True
                etat_val, cible = _etat_for(bead, extra_beads=tickets)
            elif not accepted:
                detail = "Livré : %d/%d tickets mergés" % (merged, total)
                stage = LIVRE
                etat_val, cible = _etat_for(bead, extra_beads=tickets, a_toi_de_jouer=True, cible=bead_id)
            else:
                promo = promotion_results.get(bead_id) or {}
                promu_masque = bool(promo.get("masque", True))
                promu_val = promo.get("promu")
                if promu_masque:
                    # Accepté is this chantier's last applicable stage
                    # (spec .41) -- nothing left waiting on Benjamin.
                    stage = ACCEPTE
                    detail = "Accepté"
                    termine = True
                    etat_val, cible = _etat_for(bead, extra_beads=tickets)
                elif promu_val is True:
                    stage = PROMU
                    detail = "Promu"
                    termine = True
                    etat_val, cible = _etat_for(bead, extra_beads=tickets)
                elif promu_val is None:
                    # Unknown is not "not promoted" (spec .62): nothing is
                    # asked of Benjamin on a fact the cockpit could not read.
                    stage = ACCEPTE
                    detail = "Accepté : promotion inconnue"
                    promu_inconnu = True
                    etat_val, cible = _etat_for(bead, extra_beads=tickets)
                else:
                    stage = ACCEPTE
                    detail = "Accepté : en attente de promotion"
                    etat_val, cible = _etat_for(bead, extra_beads=tickets, a_toi_de_jouer=True, cible=bead_id)

        out.append(
            Chantier(
                id=bead_id,
                titre=_title(bead),
                projet=_project_of(bead),
                stage=stage,
                detail=detail,
                etat=etat_val,
                etat_cible=cible,
                promu_masque=promu_masque,
                promu_inconnu=promu_inconnu,
                termine=termine,
                a_regarder=a_regarder,
                planning_run_target=(bead.get("metadata") or {}).get("planning_run_target"),
                rig=rigs.pop() if len(rigs) == 1 else None,
            )
        )
    return out


def convoy_chantiers(beads, promotion_results=None):
    """The active convoy chantiers (not yet at their last applicable
    stage) -- what the "Projets" section shows (spec .46: "l'accueil ne
    montre que l'actif")."""
    return [c for c in _convoy_chantiers_all(beads, promotion_results) if not c.termine]


def convoy_chantiers_historique(beads, promotion_results=None):
    """Terminé convoy chantiers (spec .46) -- Accepté with Promu masked,
    or Promu itself."""
    return [c for c in _convoy_chantiers_all(beads, promotion_results) if c.termine]


def abandoned_chantiers(beads):
    """Abandonné (spec .46): "carte ou Spec fermée sans successeur". A
    chantier-defining bead (map, Spec, draft graph) closed while carrying
    :data:`ABANDON_REASON_KEY` is read as abandoned with that reason --
    this ticket's own convention for recording the "sans successeur" case,
    since no other producer sets this key yet (closing a map/Spec with a
    real successor, e.g. spec-approve closing the map it approved from,
    never sets it)."""
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict) or bead.get("status") != "closed":
            continue
        metadata = bead.get("metadata") or {}
        raison = metadata.get(ABANDON_REASON_KEY)
        if not raison:
            continue
        labels = bead.get("labels") or []
        if MAP_LABEL in labels:
            stage = CADRAGE
        elif "spec_state" in metadata:
            stage = SPEC
        elif DRAFT_GRAPH_LABEL in labels:
            stage = GRAPHE
        else:
            continue
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=stage,
                detail="Abandonné : %s" % raison,
                etat=etat_mod.NORMAL,
                abandonne=True,
                raison_abandon=raison,
            )
        )
    return out


def build_chantiers(beads, children_by_map_id=None, promotion_results=None):
    """Every active chantier (Cadrage à Promu, excluding historique), in
    no particular order -- :mod:`cockpit.projects.builder` groups and
    sorts them per project."""
    return (
        cadrage_chantiers(beads, children_by_map_id)
        + spec_chantiers(beads)
        + graphe_chantiers(beads)
        + convoy_chantiers(beads, promotion_results)
    )


def build_historique(beads, promotion_results=None):
    """Every historique chantier (spec .46): terminé convoy chantiers plus
    abandonné cadrage/spec/graphe ones."""
    return convoy_chantiers_historique(beads, promotion_results) + abandoned_chantiers(beads)
