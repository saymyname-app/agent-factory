"""The cockpit's own clones of the project repositories, and what it reads
in them (spec af-oohx2x §"Données de projet": "Le cockpit lit chaque dépôt
de projet sur origin/<branche par défaut> via un clone qu'il possède et
rafraîchit (git fetch périodique, sans token), jamais la copie de travail
Windows ; ... Il reste en lecture seule sur les dépôts projets.").

T19 and T20 built the readers (:mod:`cockpit.projects.roadmap`,
:mod:`cockpit.projects.promotion`) against a clone someone else had made;
nothing made the clones or called the readers. This module does both, as
one read for the read model's "depots" source:

- each project's current Roadmap Step, from its knowledge repository;
- "dev a N commits d'avance" for each rig that declares a promotion
  branch, from that rig's repository.

A clone is made with ``--no-checkout`` and only ever fetched: no file of a
project is written anywhere, and nothing is pushed. One project's roadmap
being unreadable (its structured roadmap not written yet) is that
project's "inconnue", not a failure of the whole read.
"""
import os
import subprocess
import tomllib
from pathlib import Path

from cockpit.projects import promotion
from cockpit.projects.model import RoadmapStep
from cockpit.projects.release import ReleaseError, parse_release, release_path
from cockpit.projects.roadmap import (RoadmapReadError, parse_steps, pick_current_step, presented_step,
                                      read_at_default_branch, roadmap_rows)

REPO_URL_TEMPLATE = "https://github.com/%s.git"
CLONE_TIMEOUT_SECONDS = 180


def clone_path(clones_dir, repo):
    return os.path.join(clones_dir, repo.replace("/", "__"))


def ensure_clone(clones_dir, repo, url_template=REPO_URL_TEMPLATE, git_bin="git"):
    """The cockpit's clone of ``repo`` (``owner/name``), made on first use.
    Raises :class:`RoadmapReadError` when it cannot be made."""
    path = clone_path(clones_dir, repo)
    if os.path.isdir(os.path.join(path, ".git")):
        return path
    os.makedirs(clones_dir, exist_ok=True)
    try:
        completed = subprocess.run(
            [git_bin, "clone", "--quiet", "--no-checkout", url_template % repo, path],
            capture_output=True, text=True, timeout=CLONE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoadmapReadError(str(exc)) from exc
    if completed.returncode != 0:
        raise RoadmapReadError(completed.stderr.strip() or "git clone failed for %s" % repo)
    return path


def read_rig_repos(rig_files_dir):
    """``{rig: "owner/name"}`` from the rig files (``config/projects/*.toml``,
    one per rig, its ``repo`` key)."""
    out = {}
    for file in sorted(Path(rig_files_dir).glob("*.toml")):
        try:
            repo = tomllib.loads(file.read_text(encoding="utf-8")).get("repo")
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if isinstance(repo, str) and repo:
            out[file.stem] = repo
    return out


def read_roadmap(clone, roadmap_path, git_bin="git"):
    """The structured roadmap of a project in its clone, as the last fetch
    brought it: ``(roadmap, steps)``. ``roadmap`` is ``{"ok": True, "step",
    "changed_at"}`` when read, else ``{"ok": False, "step": None, "state":
    "absent" | "unreadable", "path", "reason"}``; ``steps`` is None unless
    read."""
    try:
        text, changed_at = read_at_default_branch(clone, roadmap_path, git_bin=git_bin)
        if text is None:
            return {"ok": False, "step": None, "state": "absent", "path": roadmap_path,
                    "reason": "aucun fichier %s" % roadmap_path}, None
        steps = parse_steps(text, roadmap_path)
    except RoadmapReadError as exc:
        return {"ok": False, "step": None, "state": "unreadable", "path": roadmap_path, "reason": str(exc)}, None
    step = pick_current_step(steps)
    return {
        "ok": True,
        "step": {"id": str(step.get("id", "")), "title": str(step.get("title", "")), "status": str(step.get("status", ""))},
        "changed_at": changed_at,
    }, steps


def read_release(clone, roadmap_path, git_bin="git"):
    """The release plan of a project in its clone (E, af-8rbceu;
    :mod:`cockpit.projects.release`), as plain data: ``{"state": "read",
    "plan", "path"}``, ``{"state": "absent", "path"}`` when the knowledge
    repository holds none, ``{"state": "unreadable", "path", "reason"}``."""
    path = release_path(roadmap_path)
    try:
        text, _ = read_at_default_branch(clone, path, git_bin=git_bin)
        if text is None:
            return {"state": "absent", "path": path}
        return {"state": "read", "plan": parse_release(text), "path": path}
    except (RoadmapReadError, ReleaseError) as exc:
        return {"state": "unreadable", "path": path, "reason": str(exc)}


def read_depots(descriptors, rig_repos, clones_dir, url_template=REPO_URL_TEMPLATE, git_bin="git"):
    """One read. Returns plain data: ``{"roadmaps": {project_id: the roadmap
    of read_roadmap(…)}, "steps": {project_id: [{"id", "title",
    "status"}]}, "releases": {project_id: read_release(…), or {"state":
    "undeclared"} for a project that declares no knowledge repository},
    "ecarts": {project_id: {rig: n or None}}}``. Raises only when not a
    single clone could be read -- then the whole source is failing, not one
    project."""
    roadmaps, steps_by_project, releases, ecarts = {}, {}, {}, {}
    attempts = successes = 0
    for descriptor in descriptors:
        project_id = descriptor["project_id"]
        releases[project_id] = {"state": "undeclared"}
        if descriptor.get("knowledge_repo") and descriptor.get("roadmap_path"):
            attempts += 1
            try:
                clone = ensure_clone(clones_dir, descriptor["knowledge_repo"], url_template, git_bin)
                promotion.fetch(clone, git_bin=git_bin, timeout=30)
            except RoadmapReadError as exc:
                # The repository itself does not answer: neither file is read.
                roadmaps[project_id] = {"ok": False, "step": None, "state": "unknown",
                                        "path": descriptor["roadmap_path"], "reason": str(exc)}
                releases[project_id] = {"state": "unreadable", "path": release_path(descriptor["roadmap_path"]),
                                        "reason": str(exc)}
            else:
                # Each file of the repository is read on its own: one missing
                # or unreadable never gives its reason to the other (R4).
                roadmaps[project_id], steps = read_roadmap(clone, descriptor["roadmap_path"], git_bin=git_bin)
                if steps is not None:
                    steps_by_project[project_id] = [
                        {"id": str(s.get("id", "")), "title": str(s.get("title", "")), "status": str(s.get("status", "")),
                         "order": s.get("order") if isinstance(s.get("order"), int) else 0}
                        for s in steps
                    ]
                releases[project_id] = read_release(clone, descriptor["roadmap_path"], git_bin=git_bin)
                successes += 1
        for rig, branches in sorted((descriptor.get("promotion_branch") or {}).items()):
            attempts += 1
            n = None
            try:
                clone = ensure_clone(clones_dir, rig_repos[rig], url_template, git_bin)
                promotion.fetch(clone, git_bin=git_bin)
                n = promotion.commits_ahead(
                    clone, "origin/%s" % branches["from"], "origin/%s" % branches["to"], git_bin=git_bin
                )
                successes += 1
            except (RoadmapReadError, KeyError, TypeError, ValueError):
                pass  # unknown, never a guessed zero (spec .62)
            ecarts.setdefault(project_id, {})[rig] = n
    if attempts and not successes:
        raise RoadmapReadError("aucun dépôt de projet lisible")
    return {"roadmaps": roadmaps, "steps": steps_by_project, "releases": releases, "ecarts": ecarts}


def apply_to_projects(projects, row, roadmap_chantiers=None):
    """Puts what the "depots" source holds on the projects about to be
    rendered. ``row``: the read model's row, or ``None`` when this cockpit
    reads no project repository -- the projects are then left without any
    roadmap claim at all. ``roadmap_chantiers``: ``{project_id: {step id:
    [{"closed", "merged", "accepted"}]}}``, the chantiers the "projets"
    source read for each step: the current step is then the one the page
    of the project presents, or the step it falls back on with its reserve
    (:func:`cockpit.projects.roadmap.presented_step`, R3)."""
    if row is None:
        return projects
    value = row.get("value")
    known = value is not None and row.get("freshness") != "unknown"
    for project in projects:
        if not known:
            project.roadmap_unknown = True
            project.roadmap_unknown_since = row.get("read_at")
            continue
        roadmap = (value.get("roadmaps") or {}).get(project.project_id)
        if roadmap and roadmap.get("ok") and roadmap.get("step"):
            step = roadmap["step"]
            steps = (value.get("steps") or {}).get(project.project_id)
            if roadmap_chantiers is not None and steps:
                shown = presented_step(roadmap_rows(steps, roadmap_chantiers.get(project.project_id) or {}))
                step = ({"id": shown["id"], "title": shown["title"], "status": shown["status"],
                         "reserve": shown["flag"]} if shown else None)
            project.roadmap_step = RoadmapStep(**step) if step else None
            project.roadmap_read_at = row.get("read_at")
        elif roadmap is not None:
            project.roadmap_unknown = True
        project.ecart_commits_par_rig = dict((value.get("ecarts") or {}).get(project.project_id) or {})
    return projects
