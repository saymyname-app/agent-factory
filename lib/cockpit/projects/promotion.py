"""Reads promotion-branch git facts for a project's rigs (spec af-oohx2x
§"Suivre les projets" .41, .42; §"Calcul d'étape des chantiers", Promu
row; T20).

Same shape as :mod:`cockpit.projects.roadmap`: the cockpit's own
fetch-only clone, read straight out of the object store -- no working-tree
checkout, ever (AC5-equivalent to T19's roadmap read).
"""
import subprocess

from cockpit.projects.roadmap import RoadmapReadError


def _run(args, timeout):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoadmapReadError(str(exc)) from exc
    if completed.returncode != 0:
        raise RoadmapReadError(completed.stderr.strip() or "git command failed: %s" % " ".join(args))
    return completed.stdout


def fetch(clone_dir, remote="origin", git_bin="git", timeout=10):
    _run([git_bin, "-C", str(clone_dir), "fetch", "--quiet", remote], timeout)


def is_ancestor(clone_dir, commit, branch_ref, git_bin="git", timeout=10):
    """True when ``commit`` is reachable from ``branch_ref`` (e.g.
    ``origin/main``); False when the clone can positively tell it is not.
    Raises :class:`RoadmapReadError` only when the clone cannot answer at
    all (unknown commit, missing ref) -- the caller turns that into
    "inconnu", never a silent False (spec .62: never confuse unknown with
    a real negative)."""
    completed = subprocess.run(
        [git_bin, "-C", str(clone_dir), "merge-base", "--is-ancestor", commit, branch_ref],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise RoadmapReadError(completed.stderr.strip() or "merge-base --is-ancestor failed for %s" % commit)


def commits_ahead(clone_dir, from_ref, to_ref, git_bin="git", timeout=10):
    """"dev a N commits d'avance" (spec .42): commits reachable from
    ``from_ref`` (e.g. ``origin/dev``) not reachable from ``to_ref``
    (e.g. ``origin/main``)."""
    out = _run(
        [git_bin, "-C", str(clone_dir), "rev-list", "--count", "%s..%s" % (to_ref, from_ref)],
        timeout,
    )
    return int(out.strip())


def compute_promu(clone_dir, merge_commits, branch_ref, git_bin="git", timeout=10):
    """True when every commit in ``merge_commits`` is an ancestor of
    ``branch_ref``; ``None`` (inconnu) the moment any single check cannot
    be answered -- never guesses "false" from a read failure. An empty
    ``merge_commits`` list is vacuously True (nothing left unpromoted)."""
    for commit in merge_commits:
        try:
            if not is_ancestor(clone_dir, commit, branch_ref, git_bin=git_bin, timeout=timeout):
                return False
        except RoadmapReadError:
            return None
    return True
