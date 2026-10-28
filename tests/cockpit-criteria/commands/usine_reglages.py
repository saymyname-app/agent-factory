"""What the criterion tests of G2 « Usine — réglages et nettoyage par les
portes existantes » share (af-f8nlhr; Spec af-fgcw0d, user stories 163, 164,
166, 174 and 175, Testing Decisions 1, 3 and 8). Not a test file: the
criterion test files of G2 load it.

- `serve_usine`: the cockpit the launcher of the profile, bin/project-launch,
  starts on the Usine as health-content draws it, at a commit of its own
  where a dataset of the case is declared -- with, when the case asks, how
  the doors of that launch answer (`doors`: `expires`, it never answers, or
  `records-then-expires`, it writes its record then never answers) and how
  long a check of a section of the page stays current
  (`usine_check_validity_seconds`, the five minutes of service otherwise);
- the settings and the upkeep of the launch are the real doors of the
  commit on what the launch holds (docs/COCKPIT.md, « settings and upkeep of
  the Factory »): `bin/provider-failover` in the Factory tree of the launch,
  `bin/factory-maintain` on its throwaway Git repositories, where the
  worktree `af-merged` is merged and pushed (the one candidate), and
  `af-modified` (a local change), `af-unpushed` (a commit not pushed) and
  `af-active` (work under way) are the ones to keep;
- the operator's gestures (pour_moi.Operator, over HTTP as the browser sends
  them) and the page walked in a headless Chromium behind the identity proxy
  of the host (pour_moi.walk), or measured (usine_page.measure);
- what a role says it has in service, read in the text of the page.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it, the
gestures are sent where the browser sends them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from home_destination import PROFILE, git, measure, measure_until  # noqa: F401  (re-exported for the cases)
from pour_moi import (  # noqa: F401  (re-exported for the cases)
    Operator, control, folded, read_json, requests_of, visible_text, wait_for, walk,
)
from usine_page import PAGE, recheck_of, section_titled, sections  # noqa: F401  (re-exported for the cases)

# The state of the Usine the cases start from.
BASE_DATASET = "config/cockpit-datasets/health-content.json"
# How long a command of the cockpit is waited for in an isolated launch
# (bin/cockpit-isolated, ACTION_TIMEOUT_SECONDS): a gesture answered sooner
# than this was not sent to a door that never answers.
DOOR_SECONDS = 5


def serve_usine(tree, *, doors: dict[str, str] | None = None, check_validity: float | None = None) -> str:
    """The address of the cockpit the launcher of the profile starts on the
    Usine of health-content, from a dataset of the case declared in the
    profile at a commit of its own, on top of the others: with `doors`, how
    the doors of the launch answer; with `check_validity`, how many seconds
    a check of a section of the page stays current."""
    repo = Path(tree.repo)
    dataset = json.loads((repo / BASE_DATASET).read_text(encoding="utf-8"))
    with tree.lock:
        tree.launches_of_usine = getattr(tree, "launches_of_usine", 0) + 1
        name = f"usine-reglages-{tree.launches_of_usine}"
    dataset["ui"] = dict(dataset["ui"], id=name)
    if doors:
        dataset["doors"] = doors
    if check_validity is not None:
        dataset["usine_check_validity_seconds"] = check_validity
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    profile["launch"]["datasets"][name] = path.as_posix()
    (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--message", f"{name}: the Usine of a case")
    return tree.launch(name, git(repo, "rev-parse", "HEAD"))


def in_service(text: str) -> str:
    """What the role shown in `text` (the text of a page, on one line) says
    it has in service: the words after « Fournisseur en service », up to
    « Disponibilité observée »; empty when the page says none."""
    found = re.search(r"Fournisseur en service\s*:?\s*(.*?)\s*Disponibilité observée", text)
    return found.group(1) if found else ""


def sentences(text: str) -> list[str]:
    """The sentences of `text`, cut at their final point."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def says_in_one_sentence(text: str, *patterns: str) -> bool:
    """Whether one sentence of `text` matches every pattern of `patterns`
    (case-insensitive)."""
    return any(all(re.search(pattern, sentence, re.I) for pattern in patterns) for sentence in sentences(text))


def frame_control(frame: dict, name: str) -> dict | None:
    """The first control of a measured page whose accessible name is `name`
    or starts with it."""
    return next((c for c in frame["controls"] if c["name"] == name or c["name"].startswith(name)), None)
