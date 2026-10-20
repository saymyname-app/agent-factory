"""The destination Usine at the lowest level (G1, af-wrxrmg): the page drawn
from its checks (cockpit.ui.factory), the checks of its sections
(cockpit.factory.checks), the roles read from the Factory's files
(cockpit.factory.configuration) and the latency each read records in the
read model. What the launched cockpit serves is proven by the criterion
tests tests/cockpit-criteria/commands/factory-*-test.py."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.core.polling_source import PollingSource  # noqa: E402
from cockpit.core.readmodel import ReadModel  # noqa: E402
from cockpit.factory.checks import SectionChecks  # noqa: E402
from cockpit.factory.configuration import read_configuration  # noqa: E402
from cockpit.ui.factory.page import model_label, read_machine, render_factory_page  # noqa: E402
from cockpit.ui.panorama.shell import Anchors  # noqa: E402

NOW = 1760000000.0  # 2025-10-09 10:53:20 Paris
MACHINE = {"host": "vm", "system": "Linux 6", "cores": 8, "load": 2.0, "mem_total": 24 * 1024 ** 3,
           "mem_used": 6 * 1024 ** 3, "disk_total": 200 * 1024 ** 3, "disk_used": 50 * 1024 ** 3}
FRESH_GC = {"display_name": "superviseur", "freshness": "fresh", "read_at": NOW - 5, "latency": 0.008}
CONFIGURATION = read_configuration(ROOT)


def page(live, checked=None, selected="author", configuration=CONFIGURATION, sessions=None):
    view = {
        "machine": {"at": NOW - 5, "value": MACHINE},
        "connections": {"at": NOW - 5, "value": checked if checked is not None else live},
        "agents": {"at": NOW - 5, "value": {"configuration": configuration, "sessions": sessions}},
        "live": live, "now": NOW, "selected": selected, "notify_configured": False,
        "health_html": "<p>santé</p>", "actions_html": "<p>arrêt</p>",
    }
    return render_factory_page(view)(Anchors())


class FactoryPageTest(unittest.TestCase):
    def test_the_machine_says_its_load_memory_disk_and_when_it_was_checked(self):
        drawn = page({"gc": FRESH_GC})
        for said in ("25 %", "Charge moyenne : 2,0 / 8 cœurs", "6,0 Go", "50,0 Go utilisés sur 200,0 Go",
                     "Vérifiée à 10:53:15", 'aria-label="Revérifier la machine"'):
            self.assertIn(said, drawn)

    def test_a_current_connection_says_its_latency_and_when_it_was_read(self):
        drawn = page({"gc": FRESH_GC})
        self.assertIn("À jour · lu à 10:53:15", drawn)
        self.assertIn("8,0 ms", drawn)

    def test_a_connection_no_longer_current_says_how_long_ago_it_was_seen(self):
        stale = dict(FRESH_GC, freshness="stale", read_at=NOW - 125)
        drawn = page({"gc": stale}, checked={"gc": FRESH_GC})
        self.assertIn("Périmé · vu il y a 2 min", drawn)
        self.assertIn("dernière latence 8,0 ms", drawn)
        self.assertNotIn("À jour", drawn)

    def test_a_connection_never_read_is_unknown_never_zero(self):
        drawn = page({"gc": {"display_name": "superviseur", "freshness": "unknown", "read_at": None, "latency": None}})
        self.assertIn("inconnu — la source ne répond pas", drawn)
        self.assertNotIn("0 ms", drawn)

    def test_the_selected_role_shows_its_configuration_and_what_is_observed(self):
        drawn = page({"gc": FRESH_GC}, selected="reviewer",
                     sessions={"read_at": NOW, "value": {"sessions": [{"assignee": "delivery-reviewer-1"}]}})
        self.assertIn('href="/usine?role=reviewer#role" aria-current="true"', drawn)
        self.assertIn("<dt>Modèle configuré</dt><dd>GPT-5.6 Sol</dd>", drawn)
        self.assertIn("Secours, dans l’ordre : Claude Opus 5.5", drawn)
        self.assertIn("<dt>Sessions de ce rôle au travail</dt><dd>1</dd>", drawn)
        self.assertIn('<button type="button" disabled>Demander la suspension</button>', drawn)

    def test_model_ids_read_as_their_names(self):
        self.assertEqual("Claude Opus 5.5", model_label("claude-opus-5-5"))
        self.assertEqual("GPT-5.6 Sol", model_label("gpt-5.6-sol"))
        self.assertEqual("mistral-x", model_label("mistral-x"))
        self.assertEqual("modèle non configuré", model_label(None))

    def test_the_machine_read_here_is_complete_or_none(self):
        machine = read_machine()
        self.assertTrue(machine["cores"])
        for key in ("load", "mem_total", "disk_total"):
            self.assertTrue(machine[key] is None or machine[key] > 0)


class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="factory-configuration-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        for name in ("config/delivery-roles.json", "config/provider-policy.json", "city.toml",
                     "config/delivery-flow.json"):
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.root / name)

    def role(self, configuration, key):
        return next(role for role in configuration["roles"] if role["key"] == key)

    def test_the_first_provider_of_a_chain_is_configured_the_others_are_its_fallbacks(self):
        reviewer = self.role(read_configuration(self.root), "reviewer")
        self.assertEqual(("codex-readonly", "gpt-5.6-sol"), (reviewer["configured"]["name"],
                                                             reviewer["configured"]["model"]))
        self.assertEqual(["claude-readonly"], [p["name"] for p in reviewer["fallbacks"]])
        self.assertEqual("high", reviewer["fallbacks"][0]["effort"])

    def test_the_ceilings_and_the_flow_come_from_the_flow_settings(self):
        path = self.root / "config/delivery-flow.json"
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["max_sessions"] = 6
        del flow["evaluation"]
        path.write_text(json.dumps(flow), encoding="utf-8")
        configuration = read_configuration(self.root)
        self.assertEqual(6, self.role(configuration, "author")["max_sessions"])
        self.assertEqual([["start"], ["code_review"], ["end_review", "outcome_evaluation"]],
                         [[step["key"] for step in stage] for stage in configuration["flow"]])

    def test_a_file_that_cannot_be_read_is_named_and_nothing_is_guessed(self):
        (self.root / "city.toml").unlink()
        configuration = read_configuration(self.root)
        self.assertEqual(["city.toml"], configuration["unreadable"])
        self.assertIsNone(self.role(configuration, "author")["configured"]["model"])
        self.assertIsNone(configuration["in_service"])

    def test_the_provider_in_service_is_read_apart(self):
        (self.root / "city.provider.toml").write_text(
            '[[patches.agent]]\nname = "delivery-reviewer"\nprovider = "claude-readonly"\n', encoding="utf-8")
        self.assertEqual({"delivery-reviewer": "claude-readonly"}, read_configuration(self.root)["in_service"])


class SectionChecksTest(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.reads = []
        self.checks = SectionChecks({"a": lambda: self.reads.append("a") or len(self.reads)},
                                    lambda: self.now[0], max_age_seconds=60)

    def test_a_section_is_read_once_until_it_is_checked_again(self):
        first = self.checks.get("a")
        self.now[0] = 130
        self.assertEqual(first, self.checks.get("a"))
        self.assertEqual({"at": 130, "value": 2}, self.checks.recheck("a"))

    def test_a_check_too_old_is_done_again_when_asked_for(self):
        self.checks.get("a")
        self.now[0] = 161
        self.assertEqual({"at": 161, "value": 2}, self.checks.get("a"))


class LatencyTest(unittest.TestCase):
    def test_a_poll_records_how_long_its_read_took(self):
        clock = type("Clock", (), {"now": staticmethod(lambda: NOW)})()
        model = ReadModel(clock, validity_seconds={"beads": 60})
        PollingSource(model, "beads", lambda: [], 60).poll_now()
        latency = model.snapshot()["beads"]["latency"]
        self.assertIsNotNone(latency)
        self.assertGreaterEqual(latency, 0)


if __name__ == "__main__":
    unittest.main()
