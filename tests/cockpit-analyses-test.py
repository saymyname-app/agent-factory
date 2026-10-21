"""The Analyses of the launched cockpit (D, af-ten1sp), read at GET
/analyses: the CI its local settings file declares, every page of what
GitHub answers, the runs and the journal the indicators are computed from,
and a source gone stale or never readable, which no indicator presents as
current.

Each case starts the cockpit process (bin/cockpit run) on fake sources --
the fake gc supervisor, the fake tracker of the requests
(FAKE_BD_STATE_FILE), the fake GitHub client (FAKE_GH_STATE_FILE) -- and
reads the page it serves. The values the cockpit computes from the
records are proven on the datasets of the profile by
tests/cockpit-criteria/commands/analyses-destination-*."""
import html
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT_BIN = ROOT / "bin" / "cockpit"
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit"
sys.path.insert(0, str(FIXTURES / "core"))

from fake_gc import FakeGc  # noqa: E402


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ago(**delta):
    """An instant before now, as the tracker and GitHub write it."""
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat().replace("+00:00", "Z")


def ci_run(number, conclusion, at):
    return {"id": number, "name": "CI", "status": "completed", "conclusion": conclusion, "created_at": at}


def merged_pull(number, at):
    return {"number": number, "title": "PR %d" % number, "merged_at": at, "updated_at": at}


def merged_result(title, published, merged):
    """A convoy whose merge the flow proved, as the flow leaves it."""
    return {"id": "af-%s" % title.lower().replace(" ", "-"), "title": title, "issue_type": "convoy",
            "status": "closed", "created_at": published,
            "metadata": {"gc.flow.mark": "new-flow/v1", "gc.flow.promotion": json.dumps({"at": merged})}}


class AnalysesOfTheLaunchedCockpitTest(unittest.TestCase):
    def setUp(self):
        self.gc = FakeGc().start()
        self.work = tempfile.TemporaryDirectory()
        self.tracker = Path(self.work.name, "beads.json")
        self.tracker_down = Path(self.work.name, "beads-down")
        self.github = Path(self.work.name, "github.json")
        self.settings = Path(self.work.name, "cockpit-local.json")
        self.port = free_port()
        self.proc = None
        self.write_tracker([])

    def tearDown(self):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.gc.stop()
        self.work.cleanup()

    def write_tracker(self, beads):
        self.tracker.write_text(json.dumps(beads), encoding="utf-8")

    def write_github(self, repository, workflow_runs, pull_requests):
        self.github.write_text(json.dumps({"repository": repository, "workflow_runs": workflow_runs,
                                           "pull_requests": pull_requests}), encoding="utf-8")

    def start(self, settings=None, **env):
        """The cockpit started on the fake sources, with `settings` as its
        local settings file and `env` over its environment."""
        if settings is not None:
            self.settings.write_text(json.dumps(settings), encoding="utf-8")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("COCKPIT_")}
        environment.update({
            "COCKPIT_HOST": "127.0.0.1", "COCKPIT_PORT": str(self.port),
            "COCKPIT_PID_FILE": str(Path(self.work.name, "cockpit.pid")),
            "COCKPIT_LOCAL_CONFIG": str(self.settings),
            "COCKPIT_GC_BASE_URL": self.gc.base_url, "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
            "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
            "COCKPIT_BD_BIN": str(FIXTURES / "requests" / "fake-bd"),
            "FAKE_BD_STATE_FILE": str(self.tracker), "FAKE_BD_FAIL_FLAG_FILE": str(self.tracker_down),
            "FAKE_GH_STATE_FILE": str(self.github),
            "COCKPIT_BEADS_POLL_SECONDS": "0.2", "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
            "COCKPIT_PROJECTS_POLL_SECONDS": "0.2", "COCKPIT_GITHUB_POLL_SECONDS": "0.2",
            "COCKPIT_DESCRIPTORS_DIR": self.work.name,
            **env,
        })
        self.proc = subprocess.Popen([sys.executable, str(COCKPIT_BIN), "run"], env=environment,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as response:
            return response.read().decode("utf-8")

    def page(self, view):
        """The text of the view `view` of the Analyses, on one line."""
        body = re.sub(r"<(script|style)\b.*?</\1>", " ", self.get("/analyses?vue=%s" % view), flags=re.S)
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())

    def until(self, view, condition, seconds=10):
        """The text of `view` once `condition(text)` holds."""
        deadline, text = time.monotonic() + seconds, ""
        while time.monotonic() < deadline:
            try:
                text = self.page(view)
            except OSError:
                text = ""
            if condition(text):
                return text
            time.sleep(0.1)
        self.fail("the view « %s » never held: « %s »" % (view, text))

    def freshness(self, source):
        return json.loads(self.get("/api/status")).get(source, {}).get("freshness")

    def until_fresh_then(self, source, state, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if self.freshness(source) == state:
                    return
            except OSError:
                pass
            time.sleep(0.05)
        self.fail("the source %s never became %s: %s" % (source, state, self.get("/api/status")))

    # --- the CI the cockpit reads ------------------------------------------------

    def test_the_ci_named_by_the_local_settings_file_is_read(self):
        self.write_github("saymyname-app/notes", [ci_run(1, "success", ago(hours=1)), ci_run(2, "success", ago(hours=2)),
                                                   ci_run(3, "failure", ago(hours=3))], [])
        self.start(settings={"github_repo": "saymyname-app/notes", "gh_bin": str(FIXTURES / "github" / "fake-gh")})
        text = self.until("verifications", lambda text: "%" in text)
        self.assertIn("67 % des exécutions CI terminées ont réussi · 2 réussies sur 3 terminées", text)
        self.assertIn("du dépôt saymyname-app/notes", text)

    def test_without_a_declared_repository_the_ci_is_unavailable_and_says_why(self):
        self.write_github("saymyname-app/notes", [ci_run(1, "success", ago(hours=1))], [])
        self.start(settings={})
        text = self.until("verifications", lambda text: "Raison" in text)
        self.assertIn("Raison : aucun dépôt GitHub n’est déclaré pour la CI du cockpit (réglage github_repo)", text)
        self.assertNotIn("%", text)

    def test_more_runs_and_pull_requests_than_a_page_of_github_are_all_counted(self):
        """GitHub answers 100 items a page: 130 runs completed and 104 pull
        requests merged today are all counted, not the first 100."""
        runs = [ci_run(n, "success", ago(minutes=n)) for n in range(1, 121)]
        runs += [ci_run(n, "failure", ago(minutes=n)) for n in range(121, 131)]
        pulls = [merged_pull(n, ago(minutes=n)) for n in range(1, 105)]
        self.write_github("saymyname-app/notes", runs, pulls)
        self.start(COCKPIT_GITHUB_REPO="saymyname-app/notes", COCKPIT_GH_BIN=str(FIXTURES / "github" / "fake-gh"))
        checks = self.until("verifications", lambda text: "%" in text)
        self.assertIn("92 % des exécutions CI terminées ont réussi · 120 réussies sur 130 terminées", checks)
        merged = [int(count) for count in re.findall(r"PR fusionnées · \S+ \d\d/\d\d : (\d+)", self.get("/analyses"))]
        self.assertEqual(104, sum(merged), "the pull requests merged over the period are not all counted: %s" % merged)

    # --- a source not current ----------------------------------------------------

    def test_a_ci_gone_stale_is_not_presented_as_current(self):
        """GitHub answered, then stopped answering: once its value is older
        than its Validity window, the rate is no longer shown, and why."""
        self.write_github("saymyname-app/notes", [ci_run(1, "success", ago(hours=1))], [])
        self.start(COCKPIT_GITHUB_REPO="saymyname-app/notes", COCKPIT_GH_BIN=str(FIXTURES / "github" / "fake-gh"),
                   COCKPIT_VALIDITY_GITHUB_SECONDS="2")
        self.assertIn("100 %", self.until("verifications", lambda text: "%" in text))
        self.github.unlink()
        self.until_fresh_then("github", "stale")
        text = self.page("verifications")
        self.assertNotIn("%", text, "a stale rate of the CI is presented as current")
        self.assertRegex(text, r"Raison : la CI GitHub n’est plus à jour \(dernière lecture le \d\d/\d\d à \d\d:\d\d "
                               r"\(Paris\)\)")

    def test_the_merged_results_are_read_from_the_runs_and_not_presented_as_current_once_stale(self):
        """The run of a delivery holds the proof of its merge: once the runs
        are older than their Validity window, neither the merged results
        nor the delay are shown, and the runs are why."""
        self.write_tracker([merged_result("Export des notes", ago(hours=3), ago(hours=1))])
        self.start(COCKPIT_VALIDITY_RUNS_SECONDS="2")
        self.assertIn("1 résultat sur sept jours", self.until("resultats", lambda text: "1 résultat" in text))
        self.assertIn("2 h 00", self.until("delais", lambda text: "Délai médian" in text))
        self.tracker_down.touch()
        self.until_fresh_then("runs", "stale")
        text = self.page("resultats")
        self.assertNotIn("1 résultat sur sept jours", text, "a stale count of the results is presented as current")
        self.assertIn("Résultats indisponibles", text)
        self.assertRegex(text, r"Raison : les runs ne sont plus à jour \(dernière lecture le \d\d/\d\d à "
                               r"\d\d:\d\d \(Paris\)\)")
        delay = self.page("delais")
        self.assertNotIn("2 h 00", delay, "a stale delay is presented as current")
        self.assertIn("Raison : les runs ne sont plus à jour", delay)

    def test_the_open_decisions_are_read_from_the_journal_and_not_presented_as_current_once_stale(self):
        """The journal holds every decision asked of Benjamin: once it is
        older than its Validity window, the open decisions are not counted,
        and the journal is why."""
        self.write_tracker([{"id": "af-question", "title": "Nommer la page", "issue_type": "task", "status": "open",
                             "created_at": ago(hours=2), "notes": "NEEDS BENJAMIN: Nommer la page",
                             "metadata": {"gc.needs_benjamin": "Nommer la page",
                                          "gc.escalation_pourquoi": "le nom de la page est à choisir",
                                          "gc.escalation_horodatage": ago(hours=2)}}])
        self.start(COCKPIT_VALIDITY_JOURNAL_SECONDS="2")
        self.assertIn("1 décision ouverte", self.until("activite", lambda text: "1 décision ouverte" in text))
        self.tracker_down.touch()
        self.until_fresh_then("journal", "stale")
        text = self.page("activite")
        self.assertNotIn("1 décision ouverte", text, "a stale count of the decisions is presented as current")
        self.assertIn("Décisions indisponibles", text)
        self.assertRegex(text, r"Raison : le journal n’est plus à jour \(dernière lecture le \d\d/\d\d à "
                               r"\d\d:\d\d \(Paris\)\)")

    def test_github_never_answering_gives_no_rate_and_says_when_it_was_tried(self):
        self.start(COCKPIT_GITHUB_REPO="saymyname-app/notes", COCKPIT_GH_BIN=str(FIXTURES / "github" / "fake-gh"))
        text = self.until("verifications", lambda text: "dernier essai" in text)
        self.assertRegex(text, r"Raison : GitHub n’a pas répondu \(dernier essai le \d\d/\d\d à \d\d:\d\d \(Paris\)\)")
        self.assertNotIn("%", text)


if __name__ == "__main__":
    unittest.main()
