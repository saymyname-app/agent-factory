"""Reads a project's current Roadmap Step from its structured roadmap
(spec af-oohx2x .12, .39: "l'étape de roadmap en cours (lue sur origin via
un clone que le cockpit possède, en lecture seule, avec l'âge de lecture
affiché)"; CONTEXT.md: Roadmap Step; ``bin/project-roadmap`` validates the
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


def read_current_step(clone_dir, roadmap_path, remote="origin", git_bin="git", timeout=10):
    """Fetch ``remote``, then read ``roadmap_path`` as it exists on the
    remote's default branch -- never the clone's own working tree, which
    may be stale or absent entirely. Raises :class:`RoadmapReadError` on
    any failure (network, missing branch, unparsable TOML): the caller
    turns that into "inconnu" with the clone's age (spec .13, .39)."""
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
    return pick_current_step(steps)
