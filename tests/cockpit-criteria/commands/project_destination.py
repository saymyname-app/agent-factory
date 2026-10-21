"""What the criterion tests of the destination « Projet, release et
historique » share (E, af-8rbceu, the Prototype Fold of that reference;
Spec af-fgcw0d, Testing Decisions 1, 5 and 8). Not a test file: the three
criterion test files of E load it.

It adds to `home_destination` (the launcher, the browser, the readability
checks) what a page of a project needs:

- `declare`: a dataset the cases write, declared in the profile of the tree
  under test at a commit of its own, from which the launcher starts the
  cockpit -- as the criterion tests of A1 declare the records of the D01
  commands;
- `knowledge_repository`: a disposable Git repository holding the files of
  the knowledge repository of a project, committed at a date the case
  writes;
- `part`, `rows`: the part of a measured page under a heading, and the
  lines it holds;
- `assert_fold`: the page measured is the page of a project in the
  navigation B, held to the named parts of the reference a case lists.

The named parts are those of the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-project, states/projects-content.html
and the states drawn the same). Nothing here reads the code of the cockpit.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import NAVIGATION, PROFILE, LaunchTree, git, hierarchy, says  # noqa: E402

# The named parts of the page of a project with its release, as the
# reference draws them: part -> (element, the named part that holds it).
# The parts the page of the project keeps beside them (its chantiers by
# stage, its historique) are not the reference's and are not held here.
SHELL = {
    "shell-nav-1": ("aside", None),
    "nav-1": ("nav", "shell-nav-1"),
    "main-1": ("main", None),
    "crumb-1": ("div", "main-1"),
    "project-hero-1": ("div", "main-1"),
    "compact-kpis-1": ("div", "main-1"),
    "panel-1": ("section", "main-1"),
}
RELEASE = {
    "release-goal-1": ("p", "panel-1"),
    "release-columns-1": ("div", "panel-1"),
    "release-columns-2": ("div", "panel-1"),
    "release-milestone-1": ("div", "release-columns-2"),
}
BELOW = {
    "section-grid-1": ("div", "main-1"),
    "panel-2": ("section", "section-grid-1"),
    "panel-3": ("section", "section-grid-1"),
    "section-grid-2": ("div", "main-1"),
    "panel-4": ("section", "section-grid-2"),
    "panel-5": ("section", "section-grid-2"),
}
# The page of a project with its release: the shell, the release with its
# goal, its columns and its milestone, the parts below it.
CONTENT_PARTS = {**SHELL, **RELEASE, **BELOW}
# The page of a project whose release is not known: the shell, a release
# that holds none of its parts, the parts below it.
MISSING_PARTS = {**SHELL, **BELOW}

# A date written in full or in figures: « 19/10/2026 », « 19 octobre 2026 »,
# « le 3 novembre ».
MONTHS = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
DATE = re.compile(rf"(?i)\b\d{{1,2}}(?:/\d{{1,2}}/\d{{2,4}}|\s+(?:{MONTHS})\b)")


def declare(tree: LaunchTree, name: str, dataset: dict) -> str:
    """The commit, on top of the tree under test as it stands, where
    `dataset` is a dataset of the profile under `name`. The launcher reads
    the profile in the tree: the tree stays at this commit."""
    repo = tree.repo
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    profile["launch"]["datasets"][name] = path.as_posix()
    (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--message", f"{name}: a dataset of the case")
    return git(repo, "rev-parse", "HEAD")


def dataset_of(tree: LaunchTree, name: str) -> dict:
    """The dataset `name` the profile of the tree under test declares."""
    profile = json.loads((tree.repo / PROFILE).read_text(encoding="utf-8"))
    return json.loads((tree.repo / profile["launch"]["datasets"][name]).read_text(encoding="utf-8"))


def descriptor_of(tree: LaunchTree, project: str) -> dict:
    """The descriptor of `project`, as the tree under test declares it
    (config/project-descriptors/<project>.json)."""
    path = tree.repo / "config" / "project-descriptors" / f"{project}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def knowledge_repository(path: Path, files: dict[str, str], date: str) -> Path:
    """A Git repository at `path`, its branch main holding `files` (path ->
    text) in one commit made at `date` (ISO 8601)."""
    path.mkdir(parents=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
           "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
           "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    for args in (["init", "--quiet", "--initial-branch", "main"], ["add", "--all"],
                 ["commit", "--quiet", "--message", "the knowledge of the project"]):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, env=env)
    return path


def part(frame: dict, heading: str) -> str:
    """The text, on one line, of the named part of a measured page that
    begins with `heading` (letter case aside) -- the innermost one when
    parts hold each other --, or '' when none does."""
    found = ""
    for anchor in frame.get("anchors", []):
        text = says(frame, anchor["name"])
        if anchor["name"].startswith(("panel-", "section-")) and text.lower().startswith(heading.lower()):
            if not found or len(text) < len(found):
                found = text
    return found


def part_name(frame: dict, heading: str) -> str | None:
    """The anchor of the part `part` finds, or None."""
    text = part(frame, heading)
    if not text:
        return None
    return next((anchor["name"] for anchor in frame.get("anchors", [])
                 if anchor["name"].startswith(("panel-", "section-")) and says(frame, anchor["name"]) == text), None)


def rows(frame: dict, holder: str | None) -> list[str]:
    """The lines (`row-N`) the named part `holder` holds, each on one line,
    in the order of the page."""
    if holder is None:
        return []
    return [says(frame, anchor["name"]) for anchor in frame.get("anchors", [])
            if re.fullmatch(r"row-\d+", anchor["name"]) and holder in anchor["chain"]]


def assert_fold(case, frame: dict, project: str, parts: dict) -> None:
    """The page measured is the page of `project` at its own address: the
    navigation B with « Projets » marked as the destination open, and each
    named part `parts` lists as the reference draws it -- its element,
    inside the same named part."""
    case.assertEqual(f"/projet/{project}", frame.get("path"), "the page of the project is not served at its address")
    labels = [entry["label"].rstrip("0123456789 ") for entry in frame.get("nav", [])]
    case.assertEqual(NAVIGATION, labels, "the navigation B is not the reference's")
    current = [label for label, entry in zip(labels, frame.get("nav", [])) if entry["current"]]
    case.assertEqual(["Projets"], current, "the navigation does not say « Projets » is the destination open")
    served = hierarchy(frame)
    case.assertEqual(parts, {name: served.get(name) for name in parts},
                     "the named parts of the page of the project are not the reference's")
