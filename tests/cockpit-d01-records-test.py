#!/usr/bin/env python3
"""The records of the Delivery Workflow's public commands, observed in the
cockpit (T01R4, af-u2fa7b; Spec af-2zseit, « Condition d'autonomie à
publier » and Testing Decisions 2: « Produire les records par les commandes
publiques existantes d'acceptation, jugement et promotion ; vérifier
ensuite les mêmes records dans le cockpit »).

The convoy is the one the reference driver of the Fixture City Oracle
walks to its Delivered Outcome (the harness FixtureCityWalk of
tests/convoy-stops-fixture-city-test.py). On it, the commands the launch
profile declares as entry points (`launch.entry_points`, kind `command`)
are run for real: bin/acceptance-session opens and closes the products
Benjamin judges, bin/owner-answer records his « accepté », and the next
pass of the order runs bin/outcome-promote, which merges and closes. Then
the real bin/cockpit reads the tracker those commands wrote -- through the
fake `bd` of the isolated launch, which answers what the tracker holds --
and shows the chantier as the records say.

It is one more file of the whole journey of
tests/convoy-stops-fixture-city-test.py (docs/TEST_GUIDELINE.md, « In this
repository: the whole journeys »), decided by the Spec's Testing Decisions
2; the Delivered Outcome it starts from is restored once walked.

The isolated proof does not claim that a real convoy went through the new
flow (Testing Decisions 2). The other cases of that list (findings
returned, a stale dossier, a red take-up, an abandon...) are observed by
the tickets of the screens that show them.
"""

import html
import importlib.machinery
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit"
PROFILE = ROOT / "config" / "project-descriptors" / "agent-factory.json"
WAIT_SECONDS = 30

sys.path.insert(0, str(FIXTURES / "core"))

from fake_gc import FakeGc  # noqa: E402


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: unittest collects the test classes
# named at the top of a file, and the cases of that file run there.
stops = load("convoy-stops-fixture-city-test.py")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TheCockpitShowsWhatTheDeliveryCommandsRecorded(stops.FixtureCityWalk):

    APPROVER = "benjamin"
    WORDS = "Accepté, c'est ce que je voulais."

    def command(self, path, *args):
        return self.tool_ok(ROOT / path, *args)

    def cockpit(self, name):
        """The real cockpit on what the tracker of the walk holds now; its
        address."""
        home = self.workspace / name
        (home / "projects").mkdir(parents=True)
        tracker = json.loads(self.tracker.read_text(encoding="utf-8"))
        (home / "tracker.json").write_text(json.dumps(list(tracker["beads"].values()), ensure_ascii=False),
                                           encoding="utf-8")
        shutil.copy(self.profile, home / "projects" / self.profile.name)
        supervisor = FakeGc().start()
        self.addCleanup(supervisor.stop)
        port = free_port()
        address = f"http://127.0.0.1:{port}"
        proc = subprocess.Popen([sys.executable, str(ROOT / "bin" / "cockpit"), "run"], env={
            "PATH": os.environ["PATH"], "HOME": str(home),
            "COCKPIT_HOST": "127.0.0.1", "COCKPIT_PORT": str(port), "COCKPIT_ALLOWED_ORIGIN": address,
            "COCKPIT_BENJAMIN_LOGIN": "synthetic@example.ts.net",
            "COCKPIT_PID_FILE": str(home / "cockpit.pid"), "COCKPIT_LOCAL_CONFIG": str(home / "absent.json"),
            "COCKPIT_GC_BASE_URL": supervisor.base_url, "COCKPIT_GC_BIN": "/bin/false",
            "COCKPIT_ESCALATION_DOOR_BIN": "/bin/false", "COCKPIT_PROPOSAL_DOOR_BIN": "/bin/false",
            "COCKPIT_LOOP_GUARD_BIN": "/bin/false",
            "COCKPIT_BD_BIN": str(FIXTURES / "requests" / "fake-bd"),
            "FAKE_BD_STATE_FILE": str(home / "tracker.json"),
            "COCKPIT_DESCRIPTORS_DIR": str(home / "projects"),
            "COCKPIT_GC_STATUS_POLL_SECONDS": "0.2", "COCKPIT_BEADS_POLL_SECONDS": "0.2",
            "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
        }, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        return address

    def page(self, address, path):
        with urllib.request.urlopen(address + path, timeout=5) as response:
            return response.read().decode("utf-8")

    def projects_read(self, address):
        """What the cockpit read of the projects, once it has read them."""
        deadline = time.monotonic() + WAIT_SECONDS
        while True:
            try:
                with urllib.request.urlopen(address + "/api/status", timeout=2) as response:
                    projets = json.load(response).get("projets") or {}
                if projets.get("value"):
                    return projets["value"]
            except OSError:
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never read the projects")
            time.sleep(0.2)

    def test_an_outcome_accepted_by_owner_answer_and_merged_by_outcome_promote_is_shown_accepted(self):
        declared = {(entry["path"], entry["method"]) for entry in json.loads(PROFILE.read_text())["launch"]["entry_points"]
                    if entry["kind"] == "command"}
        self.assertEqual({("bin/acceptance-session", "open"), ("bin/acceptance-session", "close"),
                          ("bin/owner-answer", "verdict"), ("bin/owner-answer", "record"),
                          ("bin/outcome-promote", "run")}, declared)
        # The dossier carries one « proposition »: what an author found « hors ticket ».
        delivered = self.walk_to_delivered(inject="proposition")
        project = json.loads(self.profile.read_text())["project_id"]

        # Delivered, not answered: the cockpit shows the chantier among the active ones, not accepted.
        before = self.projects_read(self.cockpit("cockpit-before"))
        [active] = [chantier for entry in before["projects"] if entry["project_id"] == project
                    for chantier in entry["chantiers"] if chantier["id"] == self.convoy]
        self.assertFalse(active["termine"], active)
        self.assertNotEqual("Accepté", active["stage"], active)
        self.assertEqual([], before["historique"].get(project, []))

        # Benjamin's session: the products of the dossier he judges, then closed.
        opened = json.loads(self.command("bin/acceptance-session", "open", self.convoy, "--repo", self.repo,
                                         "--profile", self.profile).stdout)
        self.assertEqual(delivered["commit"], opened["commit"])
        addresses = [product["address"] for product in opened["products"]]
        self.assertTrue(addresses and all(stops.answers(address) for address in addresses), opened)
        self.command("bin/acceptance-session", "close", self.convoy)

        # His verdict on the proposition, then his answer, recorded by bin/owner-answer; the pass
        # that follows runs bin/outcome-promote.
        [proposition] = [finding["id"] for ticket in self.shown()["tickets"] for finding in ticket.get("findings") or []
                         if finding["classification"] == "proposal"]
        self.command("bin/owner-answer", "verdict", self.convoy, "--repo", self.repo, "--approved-by", self.APPROVER,
                     "--proposition", proposition, "--verdict", "sans suite", "--words", "Vu.")
        self.command("bin/owner-answer", "record", self.convoy, "--repo", self.repo, "--approved-by", self.APPROVER,
                     "--response", "accepté", "--words", self.WORDS,
                     "--commit", delivered["commit"], "--pack-digest", delivered["pack"])
        self.order_pass()
        shown = self.shown()
        self.assertEqual(("closed", "accepted"), (shown["convoy"]["status"], shown["convoy"]["outcome"]))

        # The cockpit reads the same records: the chantier is accepted, and done.
        address = self.cockpit("cockpit-after")
        after = self.projects_read(address)
        self.assertEqual([], [chantier["id"] for entry in after["projects"] for chantier in entry["chantiers"]])
        [accepted] = [chantier for chantier in after["historique"].get(project, []) if chantier["id"] == self.convoy]
        self.assertEqual(("Accepté", "Accepté", True, False),
                         (accepted["stage"], accepted["detail"], accepted["termine"], accepted["abandonne"]))
        # The page of the project lists it in its historique, accepted.
        self.assertIn('<div class="cockpit-historique-row" data-kind="termine" data-stage="Accepté">'
                      f'<span class="cockpit-historique-titre">{html.escape(accepted["titre"])}</span>'
                      '<span class="cockpit-historique-detail">Accepté</span></div>',
                      self.page(address, f"/projet/{project}"))


if __name__ == "__main__":
    unittest.main()
