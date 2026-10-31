"""What the criterion tests of H « Usine — arrêt propre, suivi et reprise
vérifiée » share (af-69qhlk; Spec af-fgcw0d, user stories 80 to 87, 90, 165
and 175, the decision « Arrêt/reprise indépendant », Testing Decisions 1, 4
and 8). Not a test file: the criterion test files of H load it.

- `serve_stop`: the cockpit the launcher of the profile, bin/project-launch,
  starts on a dataset of the case, at a commit of its own, whose synthetic
  supervisor holds what the case says (`stop_supervisor`):

      work: [{"session", "role", "ticket", "title"}], the sessions at work
          on a ticket, each ticket in the tracker of the launch;
      drains_in_seconds: {session: seconds}, how long after the city is
          suspended a session stops by itself, its ticket kept; a session
          not named never does -- as the installed supervisor, which lets a
          session finish what it holds (seen on 1.5.0: a suspended city
          gives a session in progress its work, none new);
      reassigned_on_resume: {ticket: session}, who holds it once resumed,
          when it is not the session that held it;
      vanishes_when_drained: [ticket], gone from the tracker by then;
      asked_minutes_ago: a stop asked that long before the launch, still
          under way, the sessions silent since;
      missing_after_restart: [session], not back once the host restarted;
      writes: where it records, one JSON per line, each write it receives.

  `host_restarted_during_stop` is the one the launch recipe already reads.
- `written`: those writes, the only way to know what the cockpit asked of
  the supervisor: a complete stop is a write too.
- `said`: the page as served, on one line, what a closed details holds
  included; the walks in a headless Chromium are `pour_moi.walk`.

Nothing here reads the code of the cockpit.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path

from home_destination import PROFILE, git
from pour_moi import Operator, control, requests_of, visible_text, wait_for, walk  # noqa: F401  (re-exported for the cases)
from usine_page import PAGE, assert_usable  # noqa: F401  (re-exported for the cases)

# A stop needs at most this many seconds to show what a fact changed: the
# launch reads its stop every second, and its sources a little less often.
FOLLOWED_SECONDS = 25
# How long a case watches a page that must not change.
WATCHED_SECONDS = 6


def serve_stop(tree, base: str, stop: dict, *, restarted: bool = False) -> tuple[str, Path]:
    """(the address of the cockpit, the file of the supervisor's writes):
    the cockpit the launcher of the profile starts from a dataset of the case
    declared in the profile at a commit of its own, on top of the others:
    the dataset `base` of the profile, with the supervisor `stop`."""
    repo = Path(tree.repo)
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    dataset = json.loads((repo / profile["launch"]["datasets"][base]).read_text(encoding="utf-8"))
    with tree.lock:
        tree.stops = getattr(tree, "stops", 0) + 1
        name = f"usine-arret-{tree.stops}"
    writes = Path(tree.work) / f"{name}-writes.jsonl"
    dataset["ui"] = dict(dataset["ui"], id=name)
    dataset["stop_supervisor"] = dict(stop, writes=str(writes))
    if restarted:
        dataset["host_restarted_during_stop"] = True
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile["launch"]["datasets"][name] = path.as_posix()
    (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--message", f"{name}: the supervisor of a case")
    return tree.launch(name, git(repo, "rev-parse", "HEAD")), writes


def written(writes: Path) -> list[tuple]:
    """What the supervisor received, in order: (method, the end of the path
    after the city, body). Nothing yet: an empty list."""
    if not writes.exists():
        return []
    found = []
    for line in writes.read_text(encoding="utf-8").splitlines():
        write = json.loads(line)
        path = re.sub(r"^/v0/city/[^/]+", "", write["path"])
        found.append((write["method"], path, write.get("body")))
    return found


def said(address: str) -> str:
    """The page /usine as served, without its styles and scripts, on one
    line, spaces collapsed."""
    with urllib.request.urlopen(address + PAGE, timeout=20) as response:
        page = response.read().decode("utf-8")
    page = re.sub(r"<(style|script)\b.*?</\1>", " ", page, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def said_until(address: str, words: str, seconds: float = FOLLOWED_SECONDS) -> str:
    """`said`, again until it holds `words` or `seconds` passed."""
    return wait_for(lambda: said(address), lambda text: words in text, seconds)


def stays(address: str, seconds: float = WATCHED_SECONDS) -> list[str]:
    """`said`, read each second for `seconds`: what a case watches stay."""
    found = []
    wait_for(lambda: found.append(said(address)), lambda _: False, seconds, interval=1)
    return found
