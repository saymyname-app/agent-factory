#!/usr/bin/env python3
"""The launch recipe of the isolated cockpit, `bin/cockpit-isolated`: the
datasets it refuses to serve, and the mark of its launch the cockpit carries
(T01R4, af-u2fa7b; Spec af-2zseit, user story 126; docs/COCKPIT.md).

Each refusal is proven once, at the lowest level where it is observed
(docs/TEST_GUIDELINE.md): `synthetic_city.from_dataset`, the translation
`bin/cockpit-isolated` serves its sources from, for what a dataset says; the
recipe itself for a file that is not a dataset at all. What a dataset that
is served answers is proven on the launched product by the criterion tests
(`tests/cockpit-criteria/commands/isolated-launch-test.py`), the refusal of
a dataset that is not synthetic among them.

The cockpit the recipe becomes carries the mark `bin/project-launch` gives
its launch (`FACTORY_LAUNCH_ID`): it is how the launcher stops what it
launched and how the controller of an evaluation attests that the process
answering on the port is that launch.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from synthetic_city import DatasetRefused, from_dataset  # noqa: E402

RECIPE = ROOT / "bin" / "cockpit-isolated"

AT = "2026-10-12T12:00:00+02:00"


def panorama(*lines, state=None, name="a-state"):
    """A Panorama state: the text of one page, its lines in order."""
    ui = {"id": name, **({"state": state} if state else {})}
    return {"synthetic": True, "generated_at": AT, "ui": ui, "visible_text": "\n".join(lines)}


def overview(*lines, state=None):
    return panorama("Vue d’ensemble", *lines, state=state)


class TheDatasetItself(unittest.TestCase):

    def test_a_dataset_without_a_fixed_time_is_refused(self):
        dataset = panorama("Journal")
        del dataset["generated_at"]
        with self.assertRaisesRegex(DatasetRefused, r"no fixed time \(generated_at\)"):
            from_dataset(dataset)

    def test_a_fixed_time_that_is_not_a_date_is_refused(self):
        dataset = {**panorama("Journal"), "generated_at": "midi"}
        with self.assertRaisesRegex(DatasetRefused, r"generated_at\) is not a date: 'midi'"):
            from_dataset(dataset)

    def test_a_dataset_that_names_no_state_is_refused(self):
        dataset = {**panorama("Journal"), "ui": {}}
        with self.assertRaisesRegex(DatasetRefused, r"names no state"):
            from_dataset(dataset)

    def test_a_panorama_state_without_the_text_of_its_page_is_refused(self):
        dataset = {**panorama("Journal"), "visible_text": "  "}
        with self.assertRaisesRegex(DatasetRefused, r"without the text of its page"):
            from_dataset(dataset)

    def test_a_screen_no_rule_reads_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"a screen no rule reads: « Paramètres »"):
            from_dataset(panorama("Paramètres", "Thème"))

    def test_a_runs_state_whose_fixtures_cannot_be_read_is_refused(self):
        dataset = {"synthetic": True, "generated_at": AT, "state": "runs-active", "ui": {},
                   "fixtures": {"lanes": [], "runs": [{"id": "r1", "title": "Un run"}]}}
        with self.assertRaisesRegex(DatasetRefused, r"Runs state whose fixtures .* cannot be read"):
            from_dataset(dataset)


class TheOverview(unittest.TestCase):

    def test_a_count_of_decisions_that_is_no_number_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"« Décisions à prendre » is followed by no count"):
            from_dataset(overview("Décisions à prendre", "deux"))

    def test_a_count_of_decisions_the_list_does_not_hold_is_refused(self):
        dataset = overview("Décisions à prendre", "2", "Ce qui t’attend", "Choisir le format", "Projet Notes · décision")
        with self.assertRaisesRegex(DatasetRefused, r"counts 2, « Ce qui t’attend » lists 1"):
            from_dataset(dataset)

    def test_a_dossier_that_names_no_project_is_refused(self):
        dataset = overview("Décisions à prendre", "0", "Ce qui t’attend", "Sans projet ni titre")
        with self.assertRaisesRegex(DatasetRefused, r"a dossier that names no project and title"):
            from_dataset(dataset)

    def test_a_dossier_that_says_nothing_under_its_title_is_refused(self):
        dataset = overview("Décisions à prendre", "0", "Ce qui t’attend", "Usine · Reprise du cockpit",
                           "Le cockpit attend ton avis", "Essai ↗", "Avis")
        with self.assertRaisesRegex(DatasetRefused, r"a dossier that says nothing under its title"):
            from_dataset(dataset)

    def test_a_dossier_whose_checks_are_not_label_and_status_is_refused(self):
        dataset = overview("Décisions à prendre", "0", "Ce qui t’attend", "Usine · Reprise du cockpit",
                           "Le cockpit attend ton avis", "Dossier du résultat", "Version 1", "Parcours",
                           "Pièces et version", state="dossier")
        with self.assertRaisesRegex(DatasetRefused, r"a dossier whose checks are not label and status"):
            from_dataset(dataset)

    def test_a_project_card_that_names_no_chantier_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"a project card that names no project and chantier"):
            from_dataset(overview("Projets", "Notes", "→"))

    def test_lines_under_the_projects_that_belong_to_no_card_are_refused(self):
        dataset = overview("Projets", "Notes", "Recherche · En cours")
        with self.assertRaisesRegex(DatasetRefused, r"lines under « Projets » that belong to no card"):
            from_dataset(dataset)

    def test_the_state_of_a_result_on_a_page_that_opens_no_dossier_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"opens no dossier to be in the state 'result-ready'"):
            from_dataset(overview("Projets", state="result-ready"))


class TheOtherScreens(unittest.TestCase):

    def test_a_project_page_that_names_no_project_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"a project page that names no project"):
            from_dataset(panorama("← Projets", "ROADMAP", "V1"))

    def test_an_event_of_the_journal_without_a_title_is_refused(self):
        dataset = panorama("Journal", "Aujourd’hui", "14:48 (Paris) · Usine · Proposition")
        with self.assertRaisesRegex(DatasetRefused, r"an event of the journal without a title: 14:48"):
            from_dataset(dataset)

    def test_a_ritual_without_a_title_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"a ritual without a title, under « CADRAGE DU PROJET »"):
            from_dataset(panorama("Rituels", "CADRAGE DU PROJET"))

    def test_a_ritual_page_that_names_no_project_is_refused(self):
        with self.assertRaisesRegex(DatasetRefused, r"a ritual page that names no ritual and project"):
            from_dataset(panorama("← Rituels", "Revue d’incidents", "Sans projet"))


def listening_sockets(port):
    """The sockets listening on `port`, as /proc/<pid>/fd names them."""
    found = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in Path(table).read_text().splitlines()[1:]:
            fields = line.split()
            if int(fields[1].split(":")[1], 16) == port and fields[3] == "0A":
                found.add(f"socket:[{fields[9]}]")
    return found


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TheRecipe(unittest.TestCase):
    """bin/cockpit-isolated, run as bin/project-launch runs it."""

    def launch(self, dataset, env=None):
        """The address of the cockpit the recipe serves on `dataset`, once
        it answers."""
        port = free_port()
        proc = subprocess.Popen(
            [sys.executable, str(RECIPE), "--port", str(port), "--dataset",
             str(ROOT / "config" / "cockpit-datasets" / f"{dataset}.json")],
            env={**os.environ, **(env or {})}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        address = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(address + "/api/status", timeout=2) as response:
                    if response.status == 200:
                        return proc, address
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)

    def page(self, address):
        with urllib.request.urlopen(address + "/", timeout=10) as response:
            return response.read().decode("utf-8")

    def test_home_loading_stays_a_reading_under_way_however_late_it_is_looked_at(self):
        # Seen by the Ticket Evaluation of af-0gonc9 at 8fcd48a: looked at
        # some seconds after the launch, home-loading was home-error.
        _, address = self.launch("home-loading")
        time.sleep(15)
        page = self.page(address)
        self.assertIn("Lecture en cours…", page)
        self.assertNotIn("Cette vue est indisponible", page)

    def test_home_error_says_the_view_is_unavailable_as_soon_as_the_tracker_failed(self):
        _, address = self.launch("home-error")
        deadline = time.monotonic() + 5
        while "Cette vue est indisponible" not in (page := self.page(address)):
            self.assertLess(time.monotonic(), deadline, "home-error is still a reading under way 5 s after the launch")
            time.sleep(0.2)
        self.assertNotIn("Lecture en cours…", page)

    def test_the_cockpit_that_listens_carries_the_mark_of_its_launch(self):
        port, mark = free_port(), "FACTORY_LAUNCH_ID=recipe-test-launch"
        proc = subprocess.Popen(
            [sys.executable, str(RECIPE), "--port", str(port), "--dataset",
             str(ROOT / "config" / "cockpit-datasets" / "home-content.json")],
            env={**os.environ, "FACTORY_LAUNCH_ID": "recipe-test-launch"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)
        listening = listening_sockets(port)
        held = {os.readlink(fd) for fd in Path(f"/proc/{proc.pid}/fd").iterdir()}
        # The process the launcher holds is the one that listens on the port...
        self.assertTrue(listening & held, "the launched process does not hold the listening socket")
        # ... and it carries the mark of the launch.
        environ = Path(f"/proc/{proc.pid}/environ").read_bytes().split(b"\0")
        self.assertIn(mark.encode(), environ)

    def test_a_file_that_is_not_a_dataset_is_refused_and_nothing_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken.json")
            path.write_text("{ pas du json", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(RECIPE), "--port", "1",
                                   "--dataset", str(path)], text=True, capture_output=True, timeout=30)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn(f"cockpit-isolated: dataset unreadable ({path})", proc.stderr)


if __name__ == "__main__":
    unittest.main()
