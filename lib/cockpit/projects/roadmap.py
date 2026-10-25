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
FLAG_REQUIRED = "Incohérent : marquée terminée, %s n'est pas terminée"
# What it says of a step said done that is not acquired (FLAG_REQUIRED).
LABEL_NOT_ACQUIRED = "Non acquise"


def roadmap_rows(steps, chantiers_by_step):
    """The lines of a structured roadmap, in its order (E, af-8rbceu; Spec
    af-fgcw0d, user story 103): ``[{"id", "title", "status", "label",
    "flag", "acquired"}]``. ``chantiers_by_step``: ``{step id: [{"closed", "merged"}]}``,
    the chantiers that target each step (their Specs carry it as
    ``planning_run_target``). A step said in progress whose chantiers are
    all closed, or one of whose results is merged, is flagged: the roadmap
    contradicts the tracker. A step said done one of whose required steps
    (``done_requires``, the step ids its end condition requires; R5,
    af-3r1tmr) is not done is flagged too, naming that step: its end
    condition is not met, so it is not counted as acquired -- ``label``
    does not say it done and ``acquired`` is false; ``acquired`` is true
    for every other step done. A step in
    progress that still waits on a required step is not flagged for its own
    chantiers being closed or merged: it is in progress until that step is
    done. ``flag`` is None otherwise -- a step no chantier targets says
    nothing either way."""
    by_id = {str(step.get("id", "")): step for step in steps or []}
    rows = []
    for step in sorted(steps or [], key=lambda s: s.get("order", 0) if isinstance(s.get("order"), int) else 0):
        status = str(step.get("status", ""))
        chantiers = chantiers_by_step.get(str(step.get("id", ""))) or []
        requires = step.get("done_requires") if isinstance(step.get("done_requires"), list) else []
        pending = [str(required) for required in requires
                   if str((by_id.get(str(required)) or {}).get("status", "")) != "done"]
        flag = None
        if status == "done" and pending:
            flag = FLAG_REQUIRED % ", ".join(
                str((by_id.get(required) or {}).get("title") or required) for required in pending)
        elif status == "in_progress" and chantiers and not pending:
            if any(c.get("merged") for c in chantiers):
                flag = FLAG_MERGED
            elif all(c.get("closed") for c in chantiers):
                flag = FLAG_CLOSED
        acquired = status == "done" and not pending
        label = LABEL_NOT_ACQUIRED if status == "done" and pending else STATUS_LABELS.get(status, status or "Inconnu")
        rows.append({"id": str(step.get("id", "")), "title": str(step.get("title", "")), "status": status,
                     "label": label, "flag": flag, "acquired": acquired})
    return rows
