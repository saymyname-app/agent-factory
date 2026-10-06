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
from cockpit.projects.roadmap import RoadmapReadError, pick_current_step, read_steps

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


def read_depots(descriptors, rig_repos, clones_dir, url_template=REPO_URL_TEMPLATE, git_bin="git"):
    """One read. Returns plain data: ``{"roadmaps": {project_id: {"ok",
    "step"}}, "steps": {project_id: [{"id", "status"}]}, "ecarts":
    {project_id: {rig: n or None}}}``. Raises only when not a single clone
    could be read -- then the whole source is failing, not one project."""
    roadmaps, steps_by_project, ecarts = {}, {}, {}
    attempts = successes = 0
    for descriptor in descriptors:
        project_id = descriptor["project_id"]
        if descriptor.get("knowledge_repo") and descriptor.get("roadmap_path"):
            attempts += 1
            try:
                clone = ensure_clone(clones_dir, descriptor["knowledge_repo"], url_template, git_bin)
                steps = read_steps(clone, descriptor["roadmap_path"], git_bin=git_bin)
                step = pick_current_step(steps)
                roadmaps[project_id] = {
                    "ok": True,
                    "step": {"id": str(step.get("id", "")), "title": str(step.get("title", "")), "status": str(step.get("status", ""))},
                }
                steps_by_project[project_id] = [
                    {"id": str(s.get("id", "")), "title": str(s.get("title", "")), "status": str(s.get("status", ""))}
                    for s in steps
                ]
                successes += 1
            except RoadmapReadError:
                roadmaps[project_id] = {"ok": False, "step": None}
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
    return {"roadmaps": roadmaps, "steps": steps_by_project, "ecarts": ecarts}


def apply_to_projects(projects, row):
    """Puts what the "depots" source holds on the projects about to be
    rendered. ``row``: the read model's row, or ``None`` when this cockpit
    reads no project repository -- the projects are then left without any
    roadmap claim at all."""
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
            project.roadmap_step = RoadmapStep(**roadmap["step"])
            project.roadmap_read_at = row.get("read_at")
        elif roadmap is not None:
            project.roadmap_unknown = True
        project.ecart_commits_par_rig = dict((value.get("ecarts") or {}).get(project.project_id) or {})
    return projects
