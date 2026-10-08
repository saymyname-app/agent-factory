"""Whether an accepted chantier is Promu (spec af-oohx2x §"Calcul d'étape
des chantiers", row 7: "tous les commits de merge du convoi atteignables
depuis la branche de promotion ; masqué si la branche protégée est déjà
celle de promotion").

T20 built the git question (:func:`cockpit.projects.promotion.compute_promu`)
and the stage computation that takes its answers
(:func:`cockpit.projects.stage.convoy_chantiers`, ``promotion_results``);
nothing asked the question for the real convoys. This module does: for
each accepted convoy, the merge commits its tickets recorded
(``gc.merge_commit``), checked against the promotion branch of the rig
each ticket was dispatched to, in the clones
:mod:`cockpit.projects.depots` keeps fetched.

It never fetches and never clones: a clone that is not there yet, a commit
the clone does not know, a ticket rig with no recorded merge commit all
give ``None`` -- "promotion inconnue", never a guessed "not promoted".
"""
import os

from cockpit.projects import promotion
from cockpit.projects.depots import clone_path
from cockpit.projects.stage import (
    _accepted,
    CONVOY_ISSUE_TYPE,
    DISPATCH_RIG_KEY,
    GRAPH_DIGEST_KEY,
    _is_delivery_ticket,
    _project_of,
)

MERGE_COMMIT_KEY = "gc.merge_commit"


def _rig_verdict(rig, commits, to_branch, rig_repos, clones_dir, git_bin):
    repo = (rig_repos or {}).get(rig)
    if not clones_dir or not repo or not commits:
        return None
    clone = clone_path(clones_dir, repo)
    if not os.path.isdir(os.path.join(clone, ".git")):
        return None
    return promotion.compute_promu(clone, commits, "origin/%s" % to_branch, git_bin=git_bin)


def read_promotion_results(descriptors, beads, rig_repos, clones_dir, git_bin="git"):
    """``{convoy_id: {"masque": False, "promu": True|False|None}}`` for
    every accepted convoy that a promotion branch concerns. A convoy with
    no entry is one Promu does not apply to (spec .41): none of its
    tickets went to a rig that declares a promotion branch."""
    to_by_rig = {}
    promoting_projects = set()
    for descriptor in descriptors or []:
        branches = descriptor.get("promotion_branch") or {}
        if branches:
            promoting_projects.add(descriptor.get("project_id"))
        for rig, branch in branches.items():
            if isinstance(branch, dict) and branch.get("to"):
                to_by_rig[rig] = branch["to"]

    out = {}
    for bead in beads or []:
        if not isinstance(bead, dict) or bead.get("issue_type") != CONVOY_ISSUE_TYPE:
            continue
        metadata = bead.get("metadata") or {}
        digest = metadata.get(GRAPH_DIGEST_KEY)
        if not digest or bead.get("status") != "closed":
            continue
        if not _accepted(metadata):
            continue
        commits_by_rig = {}
        for ticket in beads:
            if not _is_delivery_ticket(ticket, digest):
                continue
            ticket_metadata = ticket.get("metadata") or {}
            rig = ticket_metadata.get(DISPATCH_RIG_KEY)
            if rig not in to_by_rig:
                continue
            commits = commits_by_rig.setdefault(rig, [])
            # A ticket closed without a merge (nothing to change) has no
            # commit to promote.
            if ticket_metadata.get(MERGE_COMMIT_KEY):
                commits.append(str(ticket_metadata[MERGE_COMMIT_KEY]))
        if not commits_by_rig:
            if _project_of(bead) in promoting_projects:
                # Its project promotes, yet no ticket says to which rig it
                # went: the cockpit cannot tell.
                out[bead.get("id")] = {"masque": False, "promu": None}
            continue
        verdicts = [
            _rig_verdict(rig, commits, to_by_rig[rig], rig_repos, clones_dir, git_bin)
            for rig, commits in sorted(commits_by_rig.items())
        ]
        if any(v is False for v in verdicts):
            promu = False
        elif any(v is None for v in verdicts):
            promu = None
        else:
            promu = True
        out[bead.get("id")] = {"masque": False, "promu": promu}
    return out
