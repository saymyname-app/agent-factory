#!/usr/bin/env python3
"""Criterion tests of the isolated cockpit launch (T01R, af-m2tr6o; Spec
af-2zseit, user story 126).

They go through `bin/project-launch`, the launcher an author, the Evaluator
and the Acceptance Session all use, with the Factory's own profile
(`config/project-descriptors/agent-factory.json`), then through the address
the launcher announces. Nothing here reads the code of the cockpit.

The decor is a disposable Git repository holding the tree these tests run
in, with three commits: the tree as it is (`requested`); the same tree
where the datasets `home-content` and `runs-active` say something else
(`reworded`); then a HEAD where `home-content` is no longer a synthetic
dataset. A launch asked at a commit must serve that commit, and what the
cockpit shows must be what the dataset of that commit says.

What these cases prove that `tests/project-launch-test.py` does not: that
test proves the launcher on the recipe of the Delivery Fixture City, one
process and no dependency. These prove the recipe of the real cockpit: its
process, the synthetic sources it reads instead of the city in service, and
that none of them outlives `stop`.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = "bin/project-launch"
PROFILE = "config/project-descriptors/agent-factory.json"
# The sources of the read model the cockpit serves at /api/status.
SOURCES = ("gc", "beads", "projets", "journal", "sessions")
PR_SET_CHILD_SUBREAPER = 36  # <linux/prctl.h>


def git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
        "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, env=env
    ).stdout.strip()


def reword(repo: Path, name: str, replacements: dict[str, str]) -> None:
    """Rewrite the dataset `name` of `repo`, where its profile declares one:
    each text of `replacements` becomes the other, wherever it is written."""
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    declared = ((profile.get("launch") or {}).get("datasets") or {}).get(name)
    if not declared:
        return
    text = (repo / declared).read_text(encoding="utf-8")
    for before, after in replacements.items():
        assert before in text, f"{name} does not say {before!r}"
        text = text.replace(before, after)
    (repo / declared).write_text(text, encoding="utf-8")


def fetch(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def answers(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2).close()
    except (urllib.error.URLError, ConnectionError, OSError):
        return False
    return True


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


@contextlib.contextmanager
def adopting_orphans():
    """While this holds, a process a launch leaves behind becomes a child of
    this test process instead of the host's init, so `children()` names it."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) refused")
    try:
        yield
    finally:
        libc.prctl(PR_SET_CHILD_SUBREAPER, 0, 0, 0, 0)


def children() -> list[int]:
    """The live processes whose parent is this test process, and no other."""
    with contextlib.suppress(ChildProcessError):
        while os.waitpid(-1, os.WNOHANG)[0]:
            pass
    me, found = str(os.getpid()), []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if fields[1] == me and fields[0] != "Z":
            found.append(int(stat.parent.name))
    return sorted(found)


class IsolatedCockpitLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="cockpit-launch-criteria-"))
        cls.repo = cls.work / "repo"
        shutil.copytree(
            ROOT, cls.repo, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        git(cls.repo, "init", "--quiet", "--initial-branch", "main")
        git(cls.repo, "add", "--all", "--force")
        git(cls.repo, "commit", "--quiet", "--message", "the tree under test")
        cls.requested = git(cls.repo, "rev-parse", "HEAD")

        reword(cls.repo, "home-content", {"Choisir le format d’export": "Choisir le format d’archive",
                                          "Portfolio": "Vitrine"})
        reword(cls.repo, "runs-active", {"Reprise du cockpit": "Reprise du tableau de bord", "Léa": "Lina"})
        git(cls.repo, "add", "--all")
        git(cls.repo, "commit", "--quiet", "--allow-empty", "--message", "two datasets say something else")
        cls.reworded = git(cls.repo, "rev-parse", "HEAD")

        reword(cls.repo, "home-content", {'"synthetic": true': '"synthetic": false'})
        git(cls.repo, "add", "--all")
        git(cls.repo, "commit", "--quiet", "--allow-empty", "--message", "home-content is no longer synthetic")
        cls.head = git(cls.repo, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def setUp(self) -> None:
        self.states: list[Path] = []

    def tearDown(self) -> None:
        for state in self.states:
            if state.exists():
                self.stop(state)

    def start(self, commit: str, dataset: str) -> tuple[dict, Path]:
        state = self.work / f"launch-{self._testMethodName}-{len(self.states)}.json"
        self.states.append(state)
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "start", str(self.repo / PROFILE),
             "--commit", commit, "--dataset", dataset, "--state-file", str(state), "--timeout", "30"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        try:
            return json.loads(proc.stdout), state
        except json.JSONDecodeError:
            self.fail(f"bin/project-launch start answered no JSON (exit {proc.returncode}): {proc.stdout}{proc.stderr}")

    def stop(self, state: Path) -> dict:
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "stop", "--state-file", str(state)],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        return json.loads(proc.stdout)

    def launched(self, commit: str, dataset: str) -> str:
        """The address of the cockpit launched at `commit` on `dataset`."""
        record, _ = self.start(commit, dataset)
        self.assertIs(True, record.get("started"), record)
        self.assertEqual(commit, record["commit"])
        return record["address"]

    def status(self, address: str, settled=None) -> dict:
        """GET /api/status, once `settled` holds of it -- by default, once
        the cockpit has read each of its sources -- or as it stands after
        20 s, for the assertions to say what is missing."""
        if settled is None:
            def settled(snapshot):
                return all((snapshot.get(source) or {}).get("freshness") == "fresh" for source in SOURCES)
        deadline = time.monotonic() + 20
        while True:
            code, content_type, body = fetch(address + "/api/status")
            self.assertEqual(200, code)
            self.assertTrue(content_type.startswith("application/json"), content_type)
            snapshot = json.loads(body)
            if settled(snapshot) or time.monotonic() > deadline:
                return snapshot
            time.sleep(0.2)

    # Criterion 1 ---------------------------------------------------------

    def test_start_serves_the_real_cockpit_at_the_requested_commit_on_an_isolated_port(self):
        record, _ = self.start(self.requested, "home-content")
        self.assertIs(True, record.get("started"), record)
        # The requested commit, not the HEAD of the repository: at HEAD the
        # dataset home-content is not synthetic, and is never served.
        self.assertEqual(self.requested, record["commit"])
        self.assertNotEqual(self.head, record["commit"])
        self.assertEqual("home-content", record["dataset"])
        address = record["address"]
        self.assertEqual(f"http://127.0.0.1:{record['port']}", address)

        code, content_type, page = fetch(address + "/")
        self.assertEqual(200, code)
        self.assertTrue(content_type.startswith("text/html"), content_type)
        self.assertIn("<title>Cockpit</title>", page)

        snapshot = self.status(address)
        # The read model of the cockpit, each source read and fresh.
        for source in SOURCES:
            self.assertEqual("fresh", snapshot[source]["freshness"], source)
        self.assertEqual("home-content", snapshot["gc"]["value"]["city"])

        # Another named dataset, another state, on another isolated port.
        other, _ = self.start(self.requested, "factory-suspended")
        self.assertIs(True, other.get("started"), other)
        self.assertNotEqual(record["port"], other["port"])
        self.assertEqual("factory-suspended", self.status(other["address"])["gc"]["value"]["city"])
        self.assertEqual("home-content", self.status(address)["gc"]["value"]["city"])

    def test_the_state_served_is_what_the_named_panorama_dataset_says(self):
        def said(commit: str, dataset: str) -> dict:
            address = self.launched(commit, dataset)
            snapshot = self.status(address)
            for source in ("beads", "projets"):
                self.assertEqual("fresh", snapshot[source]["freshness"], f"{dataset}: {source}")
            requests = json.loads(fetch(address + "/api/requests")[2])["requests"]
            return {
                "awaited": sorted(
                    (bead["title"], bead["metadata"]["gc.project_id"])
                    for bead in snapshot["beads"]["value"] if "gc.needs_benjamin" in (bead.get("metadata") or {})
                ),
                "asked": sorted(request["quoi"] for request in requests if request["type"] == "escalation"),
                "projects": sorted(project["display_name"] for project in snapshot["projets"]["value"]["projects"]),
                "chantiers": sorted(
                    (project["display_name"], chantier["titre"])
                    for project in snapshot["projets"]["value"]["projects"] for chantier in project["chantiers"]
                ),
                "tracker": sorted(bead["title"] for bead in snapshot["beads"]["value"]),
            }

        # home-content: « Décisions à prendre 2 », the two lines of « Ce qui
        # t’attend », and the three cards of « Projets » with their chantier.
        content = said(self.requested, "home-content")
        self.assertEqual(
            [("Choisir le format d’export", "notes"), ("Le cockpit attend ton avis", "usine")], content["awaited"]
        )
        self.assertEqual(["Choisir le format d’export", "Le cockpit attend ton avis"], content["asked"])
        self.assertEqual(["Notes", "Portfolio", "Usine"], content["projects"])
        self.assertEqual(
            [("Notes", "Recherche dans les notes"), ("Portfolio", "Présentation du projet"),
             ("Usine", "Reprise du cockpit")],
            content["chantiers"],
        )

        # The same dataset where it says something else: the state follows
        # what is written in it, the name of the dataset is the same.
        reworded = said(self.reworded, "home-content")
        self.assertEqual(
            [("Choisir le format d’archive", "notes"), ("Le cockpit attend ton avis", "usine")], reworded["awaited"]
        )
        self.assertEqual(["Choisir le format d’archive", "Le cockpit attend ton avis"], reworded["asked"])
        self.assertEqual(["Notes", "Usine", "Vitrine"], reworded["projects"])
        self.assertIn(("Vitrine", "Présentation du projet"), reworded["chantiers"])

        # home-empty: « Rien à afficher ici. Aucun élément dans cette vue. »
        empty = said(self.requested, "home-empty")
        self.assertEqual({"awaited": [], "asked": [], "projects": [], "chantiers": [], "tracker": []}, empty)

        # projects-content: the page of the one project Notes.
        project = said(self.requested, "projects-content")
        self.assertEqual(["Notes"], project["projects"])
        self.assertEqual([("Notes", "Recherche dans les notes")], project["chantiers"])
        self.assertEqual([], project["awaited"])

        # ritual-report: « ← Rituels · Revue d’incidents · Usine ».
        ritual = said(self.requested, "ritual-report")
        self.assertEqual(["Revue d’incidents"], ritual["tracker"])
        self.assertEqual(["Usine"], ritual["projects"])

    def test_the_state_served_is_what_the_named_runs_dataset_says(self):
        def said(commit: str, dataset: str) -> dict:
            snapshot = self.status(self.launched(commit, dataset))
            for source in ("gc", "beads", "sessions"):
                self.assertEqual("fresh", snapshot[source]["freshness"], f"{dataset}: {source}")
            beads = snapshot["beads"]["value"]
            titles = {bead["id"]: bead["title"] for bead in beads}
            return {
                "runs": sorted((bead["title"], bead["status"]) for bead in beads if "parent" not in bead),
                "running": sorted(
                    (titles[bead["parent"]], bead["title"], bead["assignee"])
                    for bead in beads if bead.get("parent") and bead["status"] == "in_progress"
                ),
                "sessions": sorted(
                    (session["assignee"], titles[session["bead_id"]])
                    for session in snapshot["sessions"]["value"]["sessions"]
                ),
                "agents_running": snapshot["gc"]["value"]["agents_running"],
            }

        # runs-active: of its five runs, « Reprise du cockpit » and « Préciser
        # le périmètre du dossier » have no end -- the open work, which is
        # what the cockpit reads of a tracker; the jobs without an end, each
        # in the lane of who holds it.
        active = said(self.requested, "runs-active")
        self.assertEqual([("Préciser le périmètre du dossier", "open"), ("Reprise du cockpit", "open")], active["runs"])
        self.assertEqual(
            [("Préciser le périmètre du dossier", "Décision attendue", "Benjamin"),
             ("Reprise du cockpit", "Essayer la tâche", "Noé"),
             ("Reprise du cockpit", "Revue du code", "Léa")],
            active["running"],
        )
        # The agents at work are the agent lanes that hold a job without an end.
        self.assertEqual([("Léa", "Revue du code"), ("Noé", "Essayer la tâche")], active["sessions"])
        self.assertEqual(2, active["agents_running"])

        # The same dataset where it says something else.
        reworded = said(self.reworded, "runs-active")
        self.assertIn(("Reprise du tableau de bord", "open"), reworded["runs"])
        self.assertNotIn(("Reprise du cockpit", "open"), reworded["runs"])
        self.assertEqual([("Lina", "Revue du code"), ("Noé", "Essayer la tâche")], reworded["sessions"])
        self.assertIn(("Reprise du tableau de bord", "Revue du code", "Lina"), reworded["running"])

    def test_the_sources_are_read_as_the_named_dataset_says(self):
        # factory-suspended: « Suspension confirmée ».
        suspended = self.status(self.launched(self.requested, "factory-suspended"))
        self.assertIs(True, suspended["gc"]["value"]["suspended"])
        self.assertIs(False, self.status(self.launched(self.requested, "home-content"))["gc"]["value"]["suspended"])

        # home-offline: « Lecture périmée · état actuel inconnu. Dernières
        # valeurs conservées » -- the supervisor was read, then answers no more.
        offline = self.status(
            self.launched(self.requested, "home-offline"),
            settled=lambda snapshot: snapshot["gc"]["value"] and snapshot["gc"]["freshness"] != "fresh",
        )
        self.assertIn(offline["gc"]["freshness"], ("stale", "unknown"), "the supervisor of home-offline is still read")
        self.assertEqual("home-offline", offline["gc"]["value"]["city"], "the last values are not kept")

        # home-error: « Cette vue est indisponible. L’état réel est inconnu. »
        # -- no source is ever read. Left the time home-content takes to be read.
        address = self.launched(self.requested, "home-error")
        self.status(self.launched(self.requested, "home-content"))
        error = self.status(address, settled=lambda snapshot: True)
        for source in ("gc", "beads", "projets"):
            self.assertEqual("unknown", error[source]["freshness"], source)
            self.assertIsNone(error[source]["value"], source)

    def test_a_dataset_that_is_not_synthetic_is_never_served(self):
        # At the requested commit the dataset is synthetic and the cockpit answers.
        self.launched(self.requested, "home-content")
        # At HEAD the same dataset is a source that is not synthetic: no cockpit.
        with adopting_orphans():
            refused, state = self.start(self.head, "home-content")
            self.assertIs(False, refused.get("started"), refused)
            self.assertFalse(state.exists(), "a refused launch leaves no launch record")
            deadline = time.monotonic() + 10
            while children() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual([], children(), "a refused launch leaves no process")

    # Criterion 2 ---------------------------------------------------------

    def test_stop_closes_the_isolated_process_and_port_and_leaves_other_services(self):
        class Neighbour(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

        # A service that is not the launched product, as the city in service is.
        neighbour = ThreadingHTTPServer(("127.0.0.1", 0), Neighbour)
        threading.Thread(target=neighbour.serve_forever, daemon=True).start()
        self.addCleanup(neighbour.server_close)
        self.addCleanup(neighbour.shutdown)
        neighbour_url = f"http://127.0.0.1:{neighbour.server_address[1]}/"

        with adopting_orphans():
            record, state = self.start(self.requested, "home-content")
            self.assertIs(True, record.get("started"), record)
            address, port, worktree = record["address"], record["port"], Path(record["worktree"])
            self.assertNotEqual(neighbour.server_address[1], port)
            self.assertEqual("home-content", self.status(address)["gc"]["value"]["city"])
            self.assertTrue(children(), "the launched cockpit is a process of this launch")

            self.assertIs(True, self.stop(state).get("stopped"))

            self.assertFalse(answers(address + "/"), "the previous address still answers")
            self.assertFalse(answers(address + "/api/status"), "the previous address still answers")
            self.assertTrue(port_is_free(port), "the isolated port is still open")
            deadline = time.monotonic() + 10
            while children() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual([], children(), "an orphan process outlives the stop")
        with self.assertRaises(ProcessLookupError):
            os.kill(record["pid"], 0)
        self.assertFalse(worktree.exists(), "the clean copy of the commit is still there")
        self.assertFalse(state.exists())
        self.assertTrue(answers(neighbour_url), "a service that is not the launched product was stopped")


if __name__ == "__main__":
    unittest.main()
