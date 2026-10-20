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

False if a connection says no state, if a value no longer current looks
current (no « vu il y a … », or drawn in the colour of a current one), if an
unknown becomes a failure or a success (a latency, « 0 », « échec »), or if
a value comes from the prototype: the latencies and the machine the dataset
says are example values, never shown as measured, and the load, the disk
and the time in service the page says are those of this host.
"""

from __future__ import annotations

import os
import pwd
import re
import shutil
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import (  # noqa: E402
    LATENCY, PAGE, TIME, UNKNOWN_SAYING, LaunchTree, colour, connection, connection_rows, measure, section_titled,
)
from home_destination import measure_until  # noqa: E402

GIB = 1024 ** 3
# The state a connection says, one of these: current and read at a time,
# no longer current and seen some time ago, never read, failing since it
# was seen, or -- the notifications -- configured or not.
STATE = re.compile(r"À jour · lu à \d{1,2}:\d{2}|Périmé · vu il y a|inconnu — la source ne répond pas"
                   r"|Inconnu — la source ne répond plus · vu il y a|Non configurées|Configurées, remise non vérifiée")


def number(text: str) -> float:
    return float(text.replace(",", "."))


def seconds_of(duration: str) -> int:
    """« 3 j 4 h 12 min 7 s » in seconds."""
    sizes = {"j": 86400, "h": 3600, "min": 60, "s": 1}
    return sum(int(count) * sizes[unit] for count, unit in re.findall(r"(\d+) (j|h|min|s)\b", duration))


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
        rows = connection_rows(frame)
        self.assertGreater(len(rows), 1, "the page shows one connection or none")
        for anchor, row in rows.items():
            self.assertEqual(1, len(STATE.findall(row)), f"{anchor} does not say one state: « {row} »")
            if "À jour" in row:
                self.assertRegex(row, LATENCY, f"{anchor} is current, and its latency is not said: « {row} »")
        self.assertEqual([], [figure for figure in ("9137 ms", "9138 ms", "9139 ms") if figure in frame["text"]],
                         "a latency of the dataset is shown as measured")

    def assert_seen_ago(self, dataset: str) -> None:
        frame, supervisor = self.supervisor_says(dataset, lambda row: "vu il y a" in row)
        self.assertIn("vu il y a", supervisor, "a supervisor that answers no more is not said seen some time ago")
        self.assertNotIn("À jour", supervisor, "a supervisor that answers no more is said current")
        self.assertNotIn(UNKNOWN_SAYING, supervisor, "a supervisor read once is said never read")
        rows = connection_rows(frame)
        greyed = next(anchor for anchor, row in rows.items() if row.startswith("Superviseur"))
        current = [anchor for anchor, row in rows.items() if "À jour" in row]
        self.assertTrue(current, f"no connection is current beside the supervisor: {rows}")
        section, _ = section_titled(self, frame, "Connexions")
        notes = [anchor["name"] for anchor in frame["anchors"]
                 if anchor["name"].startswith("readonly-note") and section in anchor["chain"]]
        self.assertTrue(notes, "the section « Connexions » has no muted note")
        note = notes[0]
        self.assertEqual(colour(frame, note), colour(frame, greyed),
                         "the supervisor that answers no more is not greyed like the muted note of its section")
        self.assertNotEqual(colour(frame, current[0]), colour(frame, greyed),
                            "the supervisor that answers no more is drawn like a current connection")

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
        self.assertRegex(machine, TIME, "the machine does not say when it was read")

        cores = os.cpu_count()
        load = re.search(r"Processeur\s+(\d+) %.*?Charge moyenne : (\d+(?:,\d)?) / (\d+) cœurs", machine)
        self.assertTrue(load, f"the processor's load is not said: « {machine} »")
        self.assertEqual(cores, int(load.group(3)), "the load is not said over the cores of the host")
        self.assertLessEqual(abs(number(load.group(2)) - os.getloadavg()[0]), 2.0,
                             "the load said is not the load average of the host")
        self.assertLessEqual(abs(int(load.group(1)) - 100 * number(load.group(2)) / cores), 1,
                             "the processor's percentage is not its load over its cores")

        usage = shutil.disk_usage(pwd.getpwuid(os.getuid()).pw_dir)
        disk = re.search(r"Disque\s+(\d+) %.*?(\d+(?:,\d)?) Go utilisés sur (\d+(?:,\d)?) Go", machine)
        self.assertTrue(disk, f"the disk's use is not said: « {machine} »")
        self.assertLessEqual(abs(number(disk.group(3)) - usage.total / GIB), 0.1,
                             "the disk is not the disk of the host's account")
        self.assertLessEqual(abs(int(disk.group(1)) - 100 * usage.used / usage.total), 1,
                             "the disk's use is not that of the host")

        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime = float(handle.read().split()[0])
        service = re.search(r"en service depuis ((?:\d+ (?:j|h|min) )*\d+ s)", machine)
        self.assertTrue(service, f"the machine does not say how long it has been in service: « {machine} »")
        self.assertLessEqual(abs(seconds_of(service.group(1)) - uptime), 120,
                             "the time in service is not that of the host")
        self.assertEqual([], [said for said in ("Hôte-de-prototype", "9999 Go", "03:33", "Exemple")
                              if said in frame["text"]], "the machine of the dataset is shown as the real one")


if __name__ == "__main__":
    unittest.main()
