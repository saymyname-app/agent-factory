"""The destination Usine at the lowest level where each case is seen (G1,
af-wrxrmg): the cockpit started as a process (`bin/cockpit run`) on a fake
supervisor and a fake tracker, its page read at GET /usine. The cockpit
reads the Factory's files in a copy of them (`COCKPIT_FACTORY_ROOT`): the
roles, the providers, what the provider failover observed.

What the cockpit launched by `bin/project-launch` serves on a dataset, in a
browser, is proven by the criterion tests
tests/cockpit-criteria/commands/factory-*-test.py; the cases here are those
a dataset cannot set: a supervisor that fails after it answered, a file of
the Factory that cannot be read, a provider in service or disabled.

Decor: the copy of the Factory's files is built once per file, then copied
for each case; the supervisor and the cockpit are live processes, started
by each case.
"""
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
COCKPIT_BIN = ROOT / "bin" / "cockpit"
FACTORY_FILES = ("config/delivery-roles.json", "config/provider-policy.json", "city.toml",
                 "config/delivery-flow.json")

sys.path.insert(0, str(FIXTURES))

from fake_gc import FakeGc  # noqa: E402


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(predicate, timeout=20, interval=0.1):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = predicate()
        except OSError:
            last = None
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


def http_get(port, path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as resp:
        return resp.read().decode("utf-8")


def text_of(fragment):
    """The text of an HTML fragment, its elements cut into ' | '."""
    fragment = re.sub(r"<style.*?</style>", "", fragment, flags=re.S)
    parts = [html.unescape(p).strip() for p in re.split(r"<[^>]+>", fragment)]
    return " | ".join(p for p in parts if p)


def row(page, name):
    """The text of the one row (`<li>`) of the page whose name is `name`."""
    found = [text_of(item) for item in re.findall(r"<li\b.*?</li>", page, flags=re.S)
             if re.search(r"<strong>%s</strong>" % re.escape(name), item)]
    assert len(found) == 1, "the page has not one row « %s »: %r" % (name, found)
    return found[0]


def hhmm(epoch):
    return datetime.fromtimestamp(epoch, tz=ZoneInfo("Europe/Paris")).strftime("%H:%M")


class FactoryPageTest(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.stored = tempfile.mkdtemp(prefix="cockpit-factory-files-")
        for name in FACTORY_FILES:
            (Path(cls.stored) / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, Path(cls.stored) / name)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.stored, ignore_errors=True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cockpit-factory-page-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.factory = Path(self.tmp) / "factory"
        shutil.copytree(self.stored, self.factory)
        self.fake_gc = FakeGc().start()
        self.addCleanup(self.fake_gc.stop)
        self.port = free_port()

    def start_cockpit(self, **extra_env):
        env = dict(os.environ)
        env.update({
            "COCKPIT_HOST": "127.0.0.1",
            "COCKPIT_PORT": str(self.port),
            "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
            "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
            "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
            "COCKPIT_BD_BIN": str(FIXTURES / "fake-bd"),
            "COCKPIT_PID_FILE": str(Path(self.tmp) / "cockpit.pid"),
            "COCKPIT_BEADS_POLL_SECONDS": "0.2",
            "COCKPIT_FACTORY_ROOT": str(self.factory),
        })
        env.update(extra_env)
        proc = subprocess.Popen([sys.executable, str(COCKPIT_BIN), "run"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def stop():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        self.addCleanup(stop)
        wait_until(lambda: http_get(self.port, "/api/status"))

    def usine(self, query=""):
        return http_get(self.port, "/usine" + query)

    def write(self, name, text):
        path = self.factory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_supervisor_that_fails_after_it_answered_is_unknown_with_its_age_never_stale(self):
        self.start_cockpit(COCKPIT_VALIDITY_GC_SECONDS="0.5")
        wait_until(lambda: json.loads(http_get(self.port, "/api/status"))["gc"]["freshness"] == "fresh")
        self.fake_gc.go_down()
        wait_until(lambda: json.loads(http_get(self.port, "/api/status"))["gc"]["freshness"] == "unknown")
        supervisor = row(self.usine(), "Superviseur")
        self.assertIn("Inconnu — la source ne répond plus · vu il y a", supervisor)
        self.assertNotIn("Périmé", supervisor)
        self.assertNotRegex(supervisor, r"\d ms", "a source that fails is given a latency")

    def test_a_file_of_the_factory_that_cannot_be_read_is_named_and_nothing_is_guessed(self):
        (self.factory / "city.toml").unlink()
        self.start_cockpit()
        page = self.usine()
        self.assertIn("Fichiers de configuration illisibles : city.toml.", page)
        self.assertIn("<dt>Modèle configuré</dt><dd>modèle non configuré</dd>", page)

    def test_the_provider_in_service_is_shown_apart_from_the_one_configured(self):
        self.write("city.provider.toml", '[[patches.agent]]\nname = "delivery-reviewer"\nprovider = "claude-readonly"\n')
        self.start_cockpit()
        page = self.usine("?role=reviewer")
        self.assertIn("<dt>Modèle configuré</dt><dd>GPT-5.6 Sol</dd>", page)
        self.assertIn("<dt>Fournisseur en service</dt><dd>Claude Opus 5.5</dd>", page)

    def test_a_provider_disabled_and_a_pool_exhausted_are_the_availability_observed(self):
        until = time.time() + 3 * 3600
        self.write(".gc/provider-state.json", json.dumps({
            "contract": "agent-factory-provider-state/v1",
            "pools": {"anthropic": {"status": "exhausted", "source": "detected",
                                    "until": datetime.fromtimestamp(until).astimezone().isoformat()}},
            "disabled": {"codex-readonly": {"reason": "clé révoquée", "by": "benjamin"}},
        }))
        self.start_cockpit()
        page = self.usine("?role=reviewer")
        self.assertIn("Quota épuisé jusqu’à %s" % hhmm(until), row(page, "Anthropic · Claude (compte partagé)"))
        self.assertIn("Aucune limite détectée", row(page, "OpenAI · Codex (quota standard)"))
        self.assertIn("<dt>Disponibilité observée</dt><dd>GPT-5.6 Sol : désactivé (clé révoquée) ; "
                      "Claude Opus 5.5 : quota épuisé jusqu’à %s</dd>" % hhmm(until), page)

    def test_without_a_state_of_the_failover_the_availability_is_said_not_observed(self):
        self.start_cockpit()
        page = self.usine("?role=evaluator")
        self.assertIn("Disponibilité non observée", row(page, "Anthropic · Claude (compte partagé)"))
        self.assertIn("<dt>Disponibilité observée</dt><dd>non observée sur cet hôte (aucun état du repli écrit)</dd>",
                      page)


if __name__ == "__main__":
    unittest.main()
