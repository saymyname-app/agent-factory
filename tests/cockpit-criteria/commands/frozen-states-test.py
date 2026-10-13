#!/usr/bin/env python3
"""Criterion tests of the frozen states of the cockpit (T01R, af-m2tr6o; Spec
af-2zseit, « Validated Prototype », seven references).

`DeclaredAddresses` reads the Factory's own profile through
`bin/project-planning-profile describe`, then uses every address it
declares: each frozen state is launched by `bin/project-launch` from its
declared dataset, and the launched cockpit is asked at the address of the
screen that state belongs to. The page of a screen is delivered by the
ticket of its reference; what is proven here is that the address is one of
the launched product, ready for the controls that follow.

`ApprovedReferences` reads the seven references at their approved commits
through `bin/prototype-conformance anchors`, in the repository an author
works in, and compares each declared dataset with the frozen one. Those
commits are private: the repository that holds them is the one this file
sits in, or the one `PROTOTYPE_REFERENCES_REPO` names when the tests run in
a copy without history. `tests/cockpit-criteria-test.py` therefore leaves
this second class out of CI, where the commits do not exist.

The states below are those the Spec lists, reference by reference.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROFILE_TOOL = "bin/project-planning-profile"
CONFORMANCE_TOOL = "bin/prototype-conformance"
PROFILE = "config/project-descriptors/agent-factory.json"

PANORAMA_COMMIT = "632deea09daa22d8213807ef48a79891edf1c7bf"
RUNS_COMMIT = "d8cb462d3287234ce5349d358899441a5796353c"

# reference path -> (approved commit, its states)
REFERENCES = {
    "prototypes/c01-complete/frozen-panorama-home": (PANORAMA_COMMIT, [
        "home-content", "home-empty", "home-loading", "home-error", "home-long", "home-stale", "home-offline",
        "home-content-full", "home-narrow", "home-light", "result-ready", "result-dossier", "result-findings",
        "result-returned", "result-repairing", "result-accepted", "result-merging", "result-merged",
        "result-outdated", "result-outage", "result-conflict", "result-abandoned", "result-request",
        "result-confirmation",
    ]),
    "prototypes/c01-complete/frozen-panorama-project": (PANORAMA_COMMIT, [
        "projects-content", "projects-narrow", "projects-light", "release-expanded", "release-estimate",
        "project-missing",
    ]),
    "prototypes/c01-complete/frozen-panorama-journal": (PANORAMA_COMMIT, [
        "journal-content", "journal-empty", "journal-loading", "journal-error", "journal-long", "journal-stale",
        "journal-offline", "journal-narrow", "journal-light", "journal-logs",
    ]),
    "prototypes/c01-complete/frozen-panorama-factory": (PANORAMA_COMMIT, [
        "health-content", "health-empty", "health-loading", "health-error", "health-long", "health-stale",
        "health-offline", "health-narrow", "health-light", "factory-draining", "factory-suspended",
        "factory-resuming", "factory-blocked", "factory-machine", "factory-configure", "factory-configure-scope",
        "factory-clean-preview", "factory-clean-done",
    ]),
    "prototypes/c01-complete/frozen-panorama-rituals": (PANORAMA_COMMIT, [
        "rituals-content", "rituals-narrow", "rituals-light", "ritual-confirm", "ritual-review", "ritual-report",
        "ritual-preparing", "ritual-ready", "ritual-execution", "ritual-delivered", "release-confirm",
        "release-review", "release-report", "release-saved",
    ]),
    "prototypes/c01-complete/frozen-panorama-analysis": (PANORAMA_COMMIT, [
        "analysis-content", "analysis-narrow", "analysis-light", "analysis-time",
    ]),
    "prototypes/c01-flow/frozen-runs": (RUNS_COMMIT, [
        "job-code", "job-configuration", "job-event", "job-gates", "job-output", "job-sessions",
        "job-system-prompt", "job-usage", "job-usage-unavailable", "job-user-prompt-raw",
        "job-user-prompt-rendered", "run-abandoned", "run-active", "run-completed", "run-stale", "run-waiting",
        "runs-active", "runs-all", "runs-completed",
    ]),
}

# The screens of the Spec and the states each one shows: one screen per
# Panorama reference, three for Runs.
RUNS = REFERENCES["prototypes/c01-flow/frozen-runs"][1]
SCREENS = {
    "Vue d’ensemble, décisions et résultat": REFERENCES["prototypes/c01-complete/frozen-panorama-home"][1],
    "Projet, release et historique": REFERENCES["prototypes/c01-complete/frozen-panorama-project"][1],
    "Journal": REFERENCES["prototypes/c01-complete/frozen-panorama-journal"][1],
    "Usine, configuration et maintenance": REFERENCES["prototypes/c01-complete/frozen-panorama-factory"][1],
    "Rituels et préparation release": REFERENCES["prototypes/c01-complete/frozen-panorama-rituals"][1],
    "Analyses": REFERENCES["prototypes/c01-complete/frozen-panorama-analysis"][1],
    "Liste des runs": [state for state in RUNS if state.startswith("runs-")],
    "Frise temporelle du run": [state for state in RUNS if state.startswith("run-")],
    "Détail du job et sessions": [state for state in RUNS if state.startswith("job-")],
}


# The frozen states that say the same things, and so are served the same
# tracker and the same projects. A group holds the states of one screen that
# differ by the theme, the width, or the reading of the sources (« stale »,
# « offline »: the last values are kept); the three empty views; the six
# views of which nothing is read; and the 19 Runs states, one set of lanes,
# runs and jobs seen with another run or job selected. Every other state is
# served a state of its own.
SAME_STATE = [
    ["home-content", "home-content-full", "home-light", "home-narrow", "home-offline", "home-stale"],
    ["journal-content", "journal-light", "journal-long", "journal-narrow", "journal-offline", "journal-stale"],
    ["health-content", "health-light", "health-narrow", "health-offline", "health-stale"],
    ["projects-content", "projects-light", "projects-narrow"],
    ["rituals-content", "rituals-light", "rituals-narrow"],
    ["analysis-content", "analysis-light", "analysis-narrow"],
    ["health-empty", "home-empty", "journal-empty"],
    ["health-error", "health-loading", "home-error", "home-loading", "journal-error", "journal-loading"],
    sorted(REFERENCES["prototypes/c01-flow/frozen-runs"][1]),
]
# Nothing is read of these: their sources never answer.
UNREAD = SAME_STATE[7]


def tool(name: str, *args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / name), *args], cwd=ROOT, text=True, capture_output=True, stdin=subprocess.DEVNULL
    )
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"error": proc.stderr.strip() or proc.stdout.strip()}


def declared_launch(case: unittest.TestCase) -> dict:
    status, described = tool(PROFILE_TOOL, "describe", PROFILE)
    case.assertEqual(0, status, described)
    launch = described.get("launch")
    case.assertIsInstance(launch, dict, "the Factory's profile declares no launch recipe")
    return launch


class DeclaredAddresses(unittest.TestCase):
    """Every declared address is used for real: each frozen state is launched
    by `bin/project-launch` from its declared dataset, in a disposable Git
    repository that holds the tree under test and nothing of the planning
    prototypes, and the launched cockpit is asked at the address of the
    screen of that state."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="cockpit-frozen-states-"))
        cls.served: dict[str, str] = {}
        cls.repo = cls.work / "repo"
        shutil.copytree(
            ROOT, cls.repo, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
            "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
        }
        for args in (["init", "--quiet"], ["add", "--all", "--force"],
                     ["commit", "--quiet", "--message", "the tree under test"]):
            subprocess.run(["git", "-C", str(cls.repo), *args], check=True, capture_output=True, env=env)
        cls.commit = subprocess.run(
            ["git", "-C", str(cls.repo), "rev-parse", "HEAD"], check=True, text=True, capture_output=True
        ).stdout.strip()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def launched_state(self, state: str, screen_address: str) -> str | None:
        """Launch the cockpit on the dataset `state`, ask it the address of
        its screen, stop it. What is wrong, or None."""
        record_file = self.work / f"launch-{state}.json"
        launcher = [sys.executable, str(ROOT / "bin/project-launch"), "--repo-root", str(self.repo)]
        proc = subprocess.run(
            [*launcher, "start", str(self.repo / PROFILE), "--commit", self.commit, "--dataset", state,
             "--state-file", str(record_file), "--timeout", "60"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        try:
            record = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return f"{state}: bin/project-launch start answered no JSON ({proc.stderr.strip()})"
        if record.get("started") is not True:
            return f"{state}: not launched from its declared dataset ({record.get('error')})"
        try:
            if record.get("commit") != self.commit or record.get("dataset") != state:
                return f"{state}: launched as {record.get('dataset')} at {record.get('commit')}"
            try:
                with urllib.request.urlopen(record["address"] + screen_address, timeout=10) as response:
                    server = response.headers.get("Server", "")
            except urllib.error.HTTPError as answer:
                server = answer.headers.get("Server", "")
            if not server.startswith("cockpit/"):
                return f"{state}: {screen_address} is not answered by the launched cockpit (Server: {server!r})"
            self.served[state] = self.served_state(record["address"], read=state not in UNREAD)
            return None
        except (urllib.error.URLError, ConnectionError, OSError, ValueError) as exc:
            return f"{state}: the launched cockpit does not answer ({exc})"
        finally:
            subprocess.run([*launcher, "stop", "--state-file", str(record_file)], capture_output=True,
                           stdin=subprocess.DEVNULL)

    def served_state(self, address: str, read: bool) -> str:
        """What the launched cockpit reads of its tracker and of the
        declared projects, whatever the name of the state: once it has read
        them, or as it stands after 20 s (after 5 s for a state of which
        nothing is read)."""
        sources = ("beads", "projets")
        deadline = time.monotonic() + (20 if read else 5)
        while True:
            with urllib.request.urlopen(address + "/api/status", timeout=10) as response:
                snapshot = json.load(response)
            if all(snapshot[source]["freshness"] == "fresh" for source in sources) or time.monotonic() > deadline:
                break
            time.sleep(0.2)
        projects = (snapshot["projets"]["value"] or {}).get("projects")
        return json.dumps({
            "beads": snapshot["beads"]["value"] and sorted(snapshot["beads"]["value"], key=lambda bead: bead["id"]),
            "projects": projects and [(p["display_name"], [c["titre"] for c in p["chantiers"]]) for p in projects],
        }, sort_keys=True, ensure_ascii=False)

    def test_every_frozen_state_is_launched_from_its_declared_dataset_at_the_address_of_its_screen(self):
        launch = declared_launch(self)
        panorama = [s for path, (_, states) in REFERENCES.items() if "panorama" in path for s in states]
        self.assertEqual(76, len(set(panorama)))
        self.assertEqual(19, len(set(RUNS)))
        self.assertEqual([], sorted(set(panorama + RUNS) - set(launch["datasets"])), "frozen states without a dataset")
        for state in panorama + RUNS:
            address = launch["datasets"][state]
            # In the tree of the commit, and nowhere in the planning prototypes.
            self.assertFalse(address.startswith("prototypes/"), address)
            self.assertTrue((ROOT / address).is_file(), f"{address} is not a file of the tree")
            dataset = json.loads((ROOT / address).read_text(encoding="utf-8"))
            self.assertIs(True, dataset.get("synthetic"), address)
            self.assertTrue(dataset.get("generated_at"), f"{address} carries no fixed time")
        self.assertFalse(any("prototypes/" in token for token in launch["recipe"]), launch["recipe"])
        self.assertFalse((self.repo / "prototypes").exists(), "the tree under test holds the planning prototypes")

        # Each state belongs to one screen of the Spec, and each screen has its own address.
        declared = launch.get("screens") or []
        entry_points = {(e["method"], e["path"]) for e in launch["entry_points"] if e["kind"] == "http"}
        address_of = {}
        for title, states in SCREENS.items():
            matching = [screen for screen in declared if sorted(screen["states"]) == sorted(states)]
            self.assertEqual(1, len(matching), f"no single screen shows exactly the states of « {title} »")
            path = matching[0]["path"]
            self.assertTrue(path.startswith("/"), path)
            self.assertIn(("GET", path), entry_points, "the address of the screen is not a declared entry point")
            for state in states:
                address_of[state] = path
        self.assertEqual(len(SCREENS), len(declared), "a declared screen is none of the Spec's")
        self.assertEqual(len(SCREENS), len(set(address_of.values())), "two screens share one address")
        self.assertEqual(sorted(panorama + RUNS), sorted(address_of))

        # The launcher serves each state from its declared dataset, and the
        # launched cockpit is the one asked at the address of its screen.
        with ThreadPoolExecutor(max_workers=6) as pool:
            problems = [p for p in pool.map(lambda s: self.launched_state(s, address_of[s]), sorted(address_of)) if p]
        self.assertEqual([], problems)

        # What each launched cockpit read is what its dataset says: two
        # states are served the same state only when they say the same
        # things, never because no rule reads what they say.
        same = {}
        for state, served in self.served.items():
            same.setdefault(served, []).append(state)
        self.assertEqual(
            sorted(SAME_STATE),
            sorted(sorted(states) for states in same.values() if len(states) > 1),
            "states that say different things are served the same state, or the reverse",
        )
        self.assertEqual(95 - sum(len(group) for group in SAME_STATE) + len(SAME_STATE), len(same))


class ApprovedReferences(unittest.TestCase):
    def repository(self) -> Path:
        """The repository of the author context, which holds the approved commits."""
        named = os.environ.get("PROTOTYPE_REFERENCES_REPO")
        if named:
            return Path(named)
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], text=True, capture_output=True
        )
        self.assertEqual(
            0, proc.returncode,
            "no repository to read the approved commits in: run from a work tree, or name one in PROTOTYPE_REFERENCES_REPO",
        )
        return Path(proc.stdout.strip())

    def test_the_frozen_states_are_extracted_at_the_approved_commits_and_are_the_declared_datasets(self):
        launch = declared_launch(self)
        repository = self.repository()
        extracted = {"panorama": 0, "runs": 0}
        for path, (commit, states) in REFERENCES.items():
            status, answer = tool(
                CONFORMANCE_TOOL, "anchors", "--repo", str(repository), "--commit", commit, "--path", path
            )
            self.assertEqual(0, status, answer)
            self.assertIs(True, answer.get("ok"), answer)
            self.assertEqual(sorted(states), sorted(answer["anchors"]))
            for state in states:
                self.assertTrue(answer["anchors"][state], f"{state} shows no named anchor")
                frozen = subprocess.run(
                    ["git", "-C", str(repository), "show", f"{commit}:{path}/data/{state}.json"],
                    capture_output=True,
                )
                self.assertEqual(0, frozen.returncode, frozen.stderr.decode(errors="replace"))
                declared = ROOT / launch["datasets"].get(state, "absent")
                self.assertTrue(declared.is_file(), f"{state} has no declared dataset in the tree")
                self.assertEqual(frozen.stdout, declared.read_bytes(), f"{state}: not the frozen dataset")
            extracted["panorama" if "panorama" in path else "runs"] += len(answer["anchors"])
        self.assertEqual({"panorama": 76, "runs": 19}, extracted)


if __name__ == "__main__":
    unittest.main()
