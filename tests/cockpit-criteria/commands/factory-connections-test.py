#!/usr/bin/env python3
"""Criterion test 1 of G1 « Usine — observation, fraîcheur et rôles réels »
(af-wrxrmg; Spec af-fgcw0d, user stories 63 and 160, Testing Decisions 1
and 8): the connections and the machine of the destination Usine, on the
datasets health-content, health-stale, health-offline, health-error and
factory-machine.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on its dataset -- or on a commit of the tree where that
dataset says other figures than the prototype's -- and reads the page GET
/usine as a headless Chromium renders it (usine_page.py).

False if a value no longer current looks current (no « vu il y a … »), if an
unknown becomes a failure or a success (a latency, « 0 », « échec »), or if
a value comes from the prototype: the latencies and the machine the dataset
says are example values, never shown as measured.
"""

from __future__ import annotations

import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import (  # noqa: E402
    LATENCY, PAGE, TIME, UNKNOWN_SAYING, LaunchTree, connection, connection_rows, measure, section_titled,
)
from home_destination import measure_until  # noqa: E402

GIB = 1024 ** 3


def memory_total() -> int:
    """The memory of this host, in whole Go: the cockpit runs here."""
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024 // GIB
    raise AssertionError("this host does not say its memory")


class FactoryConnections(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def supervisor_says(self, dataset: str, ready, commit: str | None = None) -> tuple[dict, str]:
        """The page GET /usine of the cockpit launched on `dataset`, once
        the connection « Superviseur » says what `ready` looks for (or as it
        stands after 20 s), and the text of that connection."""
        address = self.tree.launch(dataset, commit)

        def reached(frames):
            rows = [text for text in connection_rows(frames[0]).values() if text.startswith("Superviseur")]
            return bool(rows) and ready(rows[0])

        frame = measure_until(address, reached, path=PAGE)[0]
        return frame, connection(self, frame, "Superviseur")

    def test_health_content_says_the_state_latency_and_freshness_of_each_connection_none_of_the_example(self):
        # The dataset says the prototype's latencies; at this commit it says
        # figures no measure here can give.
        commit = self.tree.reword("health-content", {"24 ms": "9137 ms", "8 ms": "9138 ms", "126 ms": "9139 ms"})
        frame, supervisor = self.supervisor_says("health-content", lambda row: bool(LATENCY.search(row)), commit)
        self.assertRegex(supervisor, LATENCY, "the supervisor answers, and its latency is not said")
        self.assertRegex(supervisor, TIME, "the supervisor's connection does not say when it was read")
        self.assertNotIn("inconnu", supervisor.lower(), "a connection that answers is said unknown")
        for anchor, row in connection_rows(frame).items():
            measured = bool(LATENCY.search(row)) and bool(TIME.search(row))
            unmeasured = "non mesur" in row.lower() or "inconnu" in row.lower()
            self.assertTrue(measured or unmeasured,
                            f"{anchor} says neither a latency and a time read, nor that it is not measured: « {row} »")
        self.assertEqual([], [figure for figure in ("9137 ms", "9138 ms", "9139 ms") if figure in frame["text"]],
                         "a latency of the dataset is shown as measured")

    def assert_seen_ago(self, dataset: str) -> None:
        frame, supervisor = self.supervisor_says(dataset, lambda row: "vu il y a" in row)
        self.assertIn("vu il y a", supervisor, "a supervisor that answers no more is not said seen some time ago")
        self.assertNotIn("À jour", supervisor, "a supervisor that answers no more is said current")
        self.assertNotIn(UNKNOWN_SAYING, supervisor, "a supervisor read once is said never read")

    def test_health_stale_says_the_supervisor_that_answers_no_more_seen_some_time_ago(self):
        self.assert_seen_ago("health-stale")

    def test_health_offline_says_the_supervisor_that_answers_no_more_seen_some_time_ago(self):
        self.assert_seen_ago("health-offline")

    def test_health_error_says_the_supervisor_that_never_answered_unknown_neither_failed_nor_answered(self):
        frame, supervisor = self.supervisor_says("health-error", lambda row: UNKNOWN_SAYING in row)
        self.assertIn(UNKNOWN_SAYING, supervisor, "a supervisor that never answered is not said unknown")
        self.assertNotRegex(supervisor, LATENCY, "a supervisor that never answered is given a latency")
        self.assertNotRegex(supervisor, r"(?<![\d:,])0(?![\d:,])", "a supervisor that never answered is said « 0 »")
        for word in ("échec", "erreur", "à jour"):
            self.assertNotIn(word, supervisor.lower(), f"a supervisor that never answered is said « {word} »")

    def test_factory_machine_is_the_machine_the_cockpit_runs_on_not_the_example(self):
        # The dataset says the prototype's machine; at this commit it says a
        # machine that is not this one.
        commit = self.tree.reword("factory-machine", {
            "VM Factory": "Hôte-de-prototype",
            "82 Go utilisés sur 200 Go": "1 Go utilisés sur 9999 Go",
            "dernière lecture 14:42": "dernière lecture 03:33",
        })
        address = self.tree.launch("factory-machine", commit)
        frame = measure(address, PAGE)[0]
        _, machine = section_titled(self, frame, "Machine d’exécution")
        self.assertIn(socket.gethostname(), machine, "the machine is not the host the cockpit runs on")
        self.assertIn(f"{os.cpu_count()} cœurs", machine, "the cores are not those of the host")
        self.assertRegex(machine, rf"\b{memory_total()}(,\d)? Go\b", "the memory is not that of the host")
        self.assertRegex(machine, r"Processeur\s+\d+ %", "the processor's load is not said")
        self.assertRegex(machine, r"Disque\s+\d+ %", "the disk's use is not said")
        self.assertRegex(machine, TIME, "the machine does not say when it was read")
        self.assertEqual([], [said for said in ("Hôte-de-prototype", "9999 Go", "03:33", "Exemple")
                              if said in frame["text"]], "the machine of the dataset is shown as the real one")


if __name__ == "__main__":
    unittest.main()
