#!/usr/bin/env python3
"""Producer -> reader contract for the two proposal classes (ADR-0029,
2026-10-07). The real door (bin/proposal-door, on the fake gc of
tests/fixtures/proposal-door) writes one proposal of each class plus the
situations the ADR names; the real Cockpit process (bin/cockpit on the
controllable fake bd of tests/fixtures/cockpit/requests) then reads those
very beads. Every assertion goes through the Cockpit's HTTP surface — the
contract is what the door writes and what the screen shows, nothing in
between.

What is proven, per the ADR:
  point 3  a `decision` is in « Ce qui t'attend », Quand tu veux, complete,
           with its « Recommandé » option and raison;
  point 2  a `maintenance` is not in « Ce qui t'attend », is said in the
           health zone (« l'usine corrige seule … », no bead id, no Mayor)
           and its take-over is in the journal;
  point 4  a proposal no door wrote is not in « Ce qui t'attend » and is a
           health anomaly « à reformuler par la porte »;
  point 6  a reconverted maintenance proposal comes back as a `decision`
           request and leaves the health line.
"""
import html
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "bin" / "proposal-door"
FAKE_GC = ROOT / "tests" / "fixtures" / "proposal-door" / "fake-gc"
REQUESTS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "requests"
COCKPIT_BIN = ROOT / "bin" / "cockpit"
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

# The HTTP helpers the inbox seam test already owns (one harness, two
# seams): loaded from the file, whose name is not an importable module.
_spec = importlib.util.spec_from_file_location("cockpit_requests_test", ROOT / "tests" / "cockpit-requests-test.py")
_requests_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_requests_test)
free_port = _requests_test.free_port
wait_for_port = _requests_test.wait_for_port
http_get_json = _requests_test.http_get_json
http_get_text = _requests_test.http_get_text
wait_until = _requests_test.wait_until


DECISION = {
    "quoi": "Montrer l'âge de chaque chantier sur la page des projets",
    "pourquoi": "Deux chantiers livrés attendent depuis trois jours sans que cela se voie",
    "que_faire": [
        {"option": "Afficher l'âge depuis l'entrée dans l'étape", "consequence": "Chaque chantier porte « depuis 3 j ».",
         "recommande": True, "raison": "C'est l'information qui manque pour décider quoi accepter."},
        {"option": "Ne rien afficher", "consequence": "La page reste comme aujourd'hui."},
    ],
    "langue": "fr",
    "classe": "decision",
}

MAINTENANCE = {
    "quoi": "Filtrer les pages périmées de la liste des tâches planifiées",
    "pourquoi": "Trois pages périmées encombrent la liste depuis deux jours",
    "que_faire": [{"option": "Filtrer les pages fermées", "consequence": "La liste ne montre que les pages ouvertes."}],
    "langue": "fr",
    "classe": "maintenance",
}


class ProposalClassesContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bead_dir = root / "beads"
        self.bead_dir.mkdir()
        self.next_id_file = root / "next-id"
        self.next_id_file.write_text("af-deci1\naf-maint1\naf-bug1\n", encoding="utf-8")
        self.door_env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "PD_BEAD_DIR": str(self.bead_dir),
            "PD_CALL_LOG": str(root / "calls.log"),
            "PD_NEXT_ID_FILE": str(self.next_id_file),
            "PROPOSAL_DOOR_LOCK_FILE": str(root / "lock"),
            "PROPOSAL_DOOR_NOW": "1790000000",
        }
        self.fake_gc = FakeGc().start()
        self.pid_file = str(root / "cockpit.pid")
        self.state_file = str(root / "beads.json")
        self.port = free_port()
        self.proc = None
        self.publish_beads()

    def tearDown(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            self.proc.stdout.close()
            self.proc.stderr.close()
        self.fake_gc.stop()

    # -- the producer side: the real door on the fake tracker ------------
    def door(self, *args):
        return subprocess.run((str(DOOR),) + args, env=self.door_env, text=True, capture_output=True, check=True)

    def seed(self, bead):
        (self.bead_dir / ("%s.json" % bead["id"])).write_text(json.dumps(bead), encoding="utf-8")

    def publish_beads(self):
        """What the door wrote, exactly as `bd list --json` would hand it to
        the Cockpit: the fake bd reads this file."""
        beads = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(self.bead_dir.glob("*.json"))
            if ".tmp" not in p.name
        ]
        with open(self.state_file, "w") as fh:
            json.dump(beads, fh)

    # -- the reader side: the real Cockpit on the fake bd ----------------
    def start_cockpit(self):
        env = dict(os.environ)
        env.update({
            "COCKPIT_HOST": "127.0.0.1",
            "COCKPIT_PORT": str(self.port),
            "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
            "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
            "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
            "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
            "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
            "COCKPIT_BD_BIN": str(REQUESTS_FIXTURES / "fake-bd"),
            "COCKPIT_PID_FILE": self.pid_file,
            "COCKPIT_BEADS_POLL_SECONDS": "0.1",
            "FAKE_BD_STATE_FILE": self.state_file,
        })
        self.proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        wait_for_port("127.0.0.1", self.port)

    def requests(self):
        return http_get_json(self.port, "/api/requests")

    def health(self):
        return http_get_json(self.port, "/api/health")

    def journal(self):
        return http_get_json(self.port, "/api/journal")

    def wait_requests(self, predicate):
        return wait_until(lambda: (lambda p: p if predicate(p) else None)(self.requests()))

    def wait_health_line(self, needle):
        return wait_until(lambda: next((l for l in self.health()["lines"] if needle in l["text"]), None))

    def wait_health_line_gone(self, needle):
        wait_until(lambda: True if not any(needle in l["text"] for l in self.health()["lines"]) else None)

    # --------------------------------------------------------------------
    def test_each_class_lands_where_the_adr_says(self):
        self.door("create", json.dumps(DECISION))
        out = self.door("create", json.dumps(MAINTENANCE)).stdout
        self.assertIn("PRISE EN CHARGE: af-maint1 — ticket af-bug1", out)
        # A proposal no door wrote (before the door existed).
        self.seed({"id": "af-avant0", "status": "open", "labels": ["proposal"], "notes": "", "metadata": {}})
        self.publish_beads()
        self.start_cockpit()

        # Point 3: the decision, and only it, waits on the operator.
        payload = self.wait_requests(lambda p: len(p["requests"]) >= 1)
        self.assertEqual(["af-deci1"], [r["id"] for r in payload["requests"]])
        req = payload["requests"][0]
        self.assertEqual("proposal", req["type"])
        self.assertEqual("Quand tu veux", req["niveau"])
        self.assertFalse(req["incomplete"])
        self.assertEqual(DECISION["quoi"], req["quoi"])
        recommended = [o for o in req["que_faire"] if o["recommande"]]
        self.assertEqual(1, len(recommended))
        self.assertEqual(DECISION["que_faire"][0]["raison"], recommended[0]["raison"])

        # Point 2: the maintenance is the health zone's, with no bead id.
        line = self.wait_health_line("corrige seule")
        self.assertEqual("ok", line["kind"])
        self.assertNotIn("af-", line["text"])
        self.assertNotIn("Mayor", line["text"])
        # Point 4: the proposal no door wrote is an anomaly, not a request.
        line = self.wait_health_line("reformuler par la porte")
        self.assertEqual("warn", line["kind"])
        self.assertNotIn("af-avant0", line["text"])
        self.assertEqual(["af-deci1"], [r["id"] for r in self.requests()["requests"]])

        home = html.unescape(http_get_text(self.port, "/"))
        inbox, sante = home.split("Santé de l", 1)
        self.assertIn(DECISION["quoi"], inbox)
        self.assertIn("Recommandé", inbox)
        self.assertNotIn(MAINTENANCE["quoi"], inbox)
        self.assertIn("corrige seule", sante)
        self.assertIn("reformuler par la porte", sante)

        # The take-over is in the journal, as the door traced it.
        entries = wait_until(lambda: (lambda j: j if any(
            e["bead_id"] == "af-maint1" for e in j.get("entries", [])) else None)(self.journal()))["entries"]
        taken = next(e for e in entries if e["bead_id"] == "af-maint1")
        self.assertEqual("proposal-door", taken["voie"])
        self.assertIn("prise en charge", taken["quoi"])
        self.assertEqual(MAINTENANCE["quoi"], taken["demande"])

    def test_a_reconverted_maintenance_comes_back_as_a_decision(self):
        self.next_id_file.write_text("af-maint1\naf-bug1\n", encoding="utf-8")
        self.door("create", json.dumps(MAINTENANCE))
        self.publish_beads()
        self.start_cockpit()
        self.wait_health_line("corrige seule")
        self.assertEqual([], self.requests()["requests"])

        options = json.dumps([
            {"option": "Filtrer les pages fermées", "consequence": "Tu ne verras plus les pages fermées.",
             "recommande": True, "raison": "La liste redevient lisible."},
            {"option": "Garder la liste telle quelle", "consequence": "Rien ne change."},
        ])
        self.door("reconvertir", "af-maint1", "Touche ce que l'opérateur voit", options, "mayor")
        self.publish_beads()

        payload = self.wait_requests(lambda p: [r["id"] for r in p["requests"]] == ["af-maint1"])
        req = payload["requests"][0]
        self.assertFalse(req["incomplete"])
        self.assertTrue(any(o["recommande"] for o in req["que_faire"]))
        self.assertEqual("Quand tu veux", req["niveau"])
        self.wait_health_line_gone("corrige seule")


if __name__ == "__main__":
    unittest.main()
