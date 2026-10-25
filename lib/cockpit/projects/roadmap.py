"""Reads a project's current Roadmap Step from its structured roadmap
(spec af-oohx2x .12, .39: "l'étape de roadmap en cours (lue sur origin via
un clone que le cockpit possède, en lecture seule, avec l'âge de lecture
affiché)"; GLOSSARY.md: Roadmap Step; ``bin/project-roadmap`` validates the
same file shape).

The clone this reads is one the cockpit owns for this purpose alone -- never
the live root, never a project's own working copy (AGENTS.md: never edited
in the live root; AC5 here). Reading never checks out or writes to the
clone's working tree: after an ordinary ``fetch``, the roadmap file is read
straight out of the object store with ``git show <ref>:<path>``, so the
clone's own working tree state never matters and is never touched.
"""
import subprocess
import tomllib

DEFAULT_STATUSES_BY_PRIORITY = ("in_progress", "todo")


class RoadmapReadError(RuntimeError):
    """The clone or the roadmap file inside it could not be read."""


def _run(args, timeout):
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoadmapReadError(str(exc)) from exc
    if completed.returncode != 0:
        raise RoadmapReadError(completed.stderr.strip() or "git command failed: %s" % " ".join(args))
    return completed.stdout


def default_branch(clone_dir, remote="origin", git_bin="git", timeout=10):
    """The remote's default branch (``origin/HEAD``), falling back to
    "main" when the clone has none set -- a bare fetch does not always
    populate it."""
    try:
        out = _run(
            [git_bin, "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/%s/HEAD" % remote],
            timeout,
        )
    except RoadmapReadError:
        return "main"
    branch = out.strip().split("/")[-1]
    return branch or "main"


def pick_current_step(steps):
    """The current step (spec .39): the lowest-``order`` step still
    ``in_progress``; if none, the lowest-``order`` ``todo``; if every step
    is ``done``, the highest-``order`` one (the roadmap is complete).
    ``steps``: parsed ``[[step]]`` tables (``bin/project-roadmap``'s own
    shape)."""
    if not steps:
        return None
    ordered = sorted(steps, key=lambda s: s.get("order", 0))
    for status in DEFAULT_STATUSES_BY_PRIORITY:
        for step in ordered:
            if step.get("status") == status:
                return step
    return ordered[-1]


def read_steps(clone_dir, roadmap_path, remote="origin", git_bin="git", timeout=30):
    """Fetch ``remote``, then return every ``[[step]]`` of ``roadmap_path``
    as it exists on the remote's default branch -- never the clone's own
    working tree. Raises :class:`RoadmapReadError` on any failure
    (network, missing branch or file, unparsable TOML)."""
    _run([git_bin, "-C", str(clone_dir), "fetch", "--quiet", remote], timeout)
    branch = default_branch(clone_dir, remote=remote, git_bin=git_bin, timeout=timeout)
    raw = _run(
        [git_bin, "-C", str(clone_dir), "show", "%s/%s:%s" % (remote, branch, roadmap_path)],
        timeout,
    )
    return parse_steps(raw, roadmap_path)


def parse_steps(raw, roadmap_path):
    """Every ``[[step]]`` of the roadmap text ``raw`` read at
    ``roadmap_path``. Raises :class:`RoadmapReadError` when it is not valid
    TOML or declares no step."""
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise RoadmapReadError("%s is not valid TOML: %s" % (roadmap_path, exc)) from exc
    steps = data.get("step")
    if not isinstance(steps, list) or not steps:
        raise RoadmapReadError("%s declares no [[step]]" % roadmap_path)
    return steps


def read_at_default_branch(clone_dir, path, remote="origin", git_bin="git", timeout=30):
    """``(text, changed_at)`` of ``path`` as the remote's default branch
    holds it, with the ISO date of the last commit that changed it; ``(None,
    None)`` when that branch has no such file. Reads only what the last
    ``fetch`` brought (:func:`read_steps` fetches). Raises
    :class:`RoadmapReadError` on any other failure."""
    branch = default_branch(clone_dir, remote=remote, git_bin=git_bin, timeout=timeout)
    ref = "%s/%s" % (remote, branch)
    try:
        completed = subprocess.run(
            [git_bin, "-C", str(clone_dir), "cat-file", "-e", "%s:%s" % (ref, path)],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoadmapReadError(str(exc)) from exc
    if completed.returncode != 0:
        return None, None
    text = _run([git_bin, "-C", str(clone_dir), "show", "%s:%s" % (ref, path)], timeout)
    changed_at = _run([git_bin, "-C", str(clone_dir), "log", "-1", "--format=%cI", ref, "--", path], timeout).strip()
    return text, changed_at or None


def read_current_step(clone_dir, roadmap_path, remote="origin", git_bin="git", timeout=10):
    """Fetch ``remote``, then read ``roadmap_path`` as it exists on the
    remote's default branch -- never the clone's own working tree, which
    may be stale or absent entirely. Raises :class:`RoadmapReadError` on
    any failure (network, missing branch, unparsable TOML): the caller
    turns that into "inconnu" with the clone's age (spec .13, .39)."""
    return pick_current_step(
        read_steps(clone_dir, roadmap_path, remote=remote, git_bin=git_bin, timeout=timeout)
    )


# What the page of a project says of each status of a Roadmap Step.
STATUS_LABELS = {"done": "Terminé", "in_progress": "En cours", "todo": "À venir"}
FLAG_CLOSED = "Incohérent : marqué en cours, son chantier est fermé"
FLAG_MERGED = "Incohérent : marqué en cours, son résultat est fusionné"
FLAG_ACCEPTED = "Incohérent : marqué en cours, son résultat est accepté"
FLAG_UNLINKED = "Aucun chantier relié : rien dans le suivi ne cible cette étape"


def roadmap_rows(steps, chantiers_by_step):
    """The lines of a structured roadmap, in its order (E, af-8rbceu; R3,
    af-plu8kn; Spec af-fgcw0d, user story 103): ``[{"id", "title",
    "status", "label", "flag"}]``. ``chantiers_by_step``: ``{step id:
    [{"closed", "merged", "accepted"}]}``, the chantiers that target each
    step (their Specs carry it as ``planning_run_target``). A step said in
    progress whose chantiers are all closed, one of whose results is merged
    or accepted, is flagged: the roadmap contradicts the tracker. A step
    said in progress that no chantier targets is flagged too: nothing in
    the tracker vouches for it. ``flag`` is None otherwise."""
    rows = []
    for step in sorted(steps or [], key=lambda s: s.get("order", 0) if isinstance(s.get("order"), int) else 0):
        status = str(step.get("status", ""))
        chantiers = chantiers_by_step.get(str(step.get("id", ""))) or []
        flag = None
        if status == "in_progress":
            if not chantiers:
                flag = FLAG_UNLINKED
            elif any(c.get("merged") for c in chantiers):
                flag = FLAG_MERGED
            elif all(c.get("closed") for c in chantiers):
                flag = FLAG_CLOSED
            elif any(c.get("accepted") for c in chantiers):
                flag = FLAG_ACCEPTED
        rows.append({"id": str(step.get("id", "")), "title": str(step.get("title", "")), "status": status,
                     "label": STATUS_LABELS.get(status, status or "Inconnu"), "flag": flag})
    return rows


def current_step(rows):
    """The row of :func:`roadmap_rows` a page presents as the current step
    (R3, af-plu8kn): the first in progress without a flag, else the first
    to do without one; None when every such step carries a reserve -- a
    step flagged is never presented as current for certain."""
    for status in DEFAULT_STATUSES_BY_PRIORITY:
        row = next((r for r in rows if r["status"] == status and not r["flag"]), None)
        if row is not None:
            return row
    return None
