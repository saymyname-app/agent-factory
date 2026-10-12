#!/usr/bin/env python3
"""Criterion tests of the frozen states of the cockpit (T01, af-oigubn; Spec
af-2zseit, « Validated Prototype », seven references).

`DeclaredAddresses` reads the Factory's own profile through
`bin/project-planning-profile describe`: every frozen state is a named
dataset of the tree, and belongs to one screen that has an address.

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
import subprocess
import sys
import unittest
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
    def test_every_frozen_state_is_a_named_dataset_of_the_tree(self):
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

    def test_every_frozen_state_belongs_to_one_screen_that_has_an_address(self):
        launch = declared_launch(self)
        declared = launch.get("screens") or []
        entry_points = {(e["method"], e["path"]) for e in launch["entry_points"] if e["kind"] == "http"}
        addresses = []
        for title, states in SCREENS.items():
            matching = [screen for screen in declared if sorted(screen["states"]) == sorted(states)]
            self.assertEqual(1, len(matching), f"no single screen shows exactly the states of « {title} »")
            path = matching[0]["path"]
            self.assertTrue(path.startswith("/"), path)
            self.assertIn(("GET", path), entry_points, "the address of the screen is not a declared entry point")
            addresses.append(path)
        self.assertEqual(len(SCREENS), len(declared), "a declared screen is none of the Spec's")
        self.assertEqual(len(SCREENS), len(set(addresses)), "two screens share one address")
        # What the cockpit is probed at for its launch.
        self.assertIn(("GET", "/"), entry_points)
        self.assertIn(("GET", "/api/status"), entry_points)


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
