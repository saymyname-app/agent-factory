#!/usr/bin/env python3
"""Contract between the proposal door and the Cockpit inbox (2026-10-07).

What bin/proposal-door accepts, the Cockpit displays exactly as written;
what the Cockpit would replace by its fixed repli, the door refuses with
the reason. Both sides run cockpit.text.validate.request_violations (the
door through bin/operator-text-check), and this test holds them together
through their public interfaces only: the door's CLI on a fake gc, the
Cockpit process on a fake bd reading the very beads the door left.

Why it exists: on 2026-10-07 four proposals created through the door
(af-os9sh2, af-vnv59w, af-1ai5e3, af-vws964) were shown « incomplète :
champ … manquant » with every field present in Beads. The door checked
presence, one line and 140 characters; the inbox also refuses an
identifier (af-xxx, #300) and an internal term outside the Cockpit Lexicon
(bead, convoi, Mayor). Nothing compared the two. The four cases are in
tests/fixtures/cockpit/requests/refused-proposals.json, as Beads holds
them.
"""
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "bin" / "proposal-door"
TEXT_CHECK = ROOT / "bin" / "operator-text-check"
COCKPIT_BIN = ROOT / "bin" / "cockpit"
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
REQUESTS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "requests"
REFUSED = json.loads((REQUESTS_FIXTURES / "refused-proposals.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(CORE_FIXTURES))
from fake_gc import FakeGc  # noqa: E402


def _door_fake_gc():
    """The fake gc tests/proposal-door-test.py drives the door with: one
    fake for the door, wherever it is tested."""
    spec = importlib.util.spec_from_file_location(
        "proposal_door_test", ROOT / "tests" / "proposal-door-test.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FAKE_GC


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("nothing listening on 127.0.0.1:%d after %ss" % (port, timeout))


def payload_of(bead):
    """The `create` payload that produced ``bead``'s proposal fields."""
    metadata = bead["metadata"]
    options = [
        {k: v for k, v in option.items() if k != "lettre"}
        for option in json.loads(metadata["gc.proposal_que_faire"])
    ]
    return {
        "quoi": metadata["gc.proposal_quoi"],
        "pourquoi": metadata["gc.proposal_pourquoi"],
        "que_faire": options,
        "langue": metadata["gc.proposal_langue"],
    }


# Proposals the door must accept and the Cockpit must show as written.
# The first two are what bin/upstream-skills-check and
# bin/overlap-conflict-log file; options without `recommande`/`raison`,
# straight apostrophes and non-ASCII letters are all fine -- none of them
# was the cause.
DISPLAYABLE = [
    {
        "quoi": "mattpocock/skills a publié v1.3.1, au-delà de la référence Method Baseline",
        "pourquoi": "Référence épinglée à c55ee46073ed, plus ancienne que cette publication",
        "que_faire": [
            {"option": "Adopter la mise à jour", "consequence": "Réépingle la référence Method Baseline et réécrit ses usages (docs/UPSTREAM_SKILLS.md)."},
            {"option": "Ne pas adopter pour l'instant", "consequence": "La référence reste inchangée ; le prochain tag sera à nouveau signalé."},
        ],
        "langue": "fr",
    },
    {
        "quoi": "Proposer des leases dynamiques : conflits PR non déclarés répétés",
        "pourquoi": "3 conflits PR sans chevauchement déclaré en 7 jours",
        "que_faire": [
            {
                "option": "Étudier les leases dynamiques au prochain Planning Run",
                "consequence": "Aucun changement immédiat ; trié à la prochaine carte de planification.",
                "recommande": True,
                "raison": "Le seuil de conflits non déclarés est franchi.",
            }
        ],
        "langue": "fr",
    },
    {
        "quoi": "x" * 140,
        "pourquoi": "Une ligne de 140 caractères exactement tient à l'écran",
        "que_faire": [{"option": "Garder", "consequence": "Rien ne change."}],
        "langue": "fr",
    },
]


class DoorAndCockpit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bead_dir = root / "beads"
        self.bead_dir.mkdir()
        self.next_id_file = root / "next-id"
        self.state_file = root / "beads.json"
        self.state_file.write_text("[]", encoding="utf-8")
        fake_gc = root / "gc"
        fake_gc.write_text(_door_fake_gc(), encoding="utf-8")
        fake_gc.chmod(fake_gc.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        (root / "calls.log").write_text("", encoding="utf-8")
        self.door_env = {
            **os.environ,
            "GC_BIN": str(fake_gc),
            "PD_BEAD_DIR": str(self.bead_dir),
            "PD_CALL_LOG": str(root / "calls.log"),
            "PD_NEXT_ID_FILE": str(self.next_id_file),
            "PROPOSAL_DOOR_LOCK_FILE": str(root / "lock"),
            "PROPOSAL_DOOR_NOW": "1790000000",
        }
        self.fake_gc = FakeGc().start()
        self.addCleanup(self.fake_gc.stop)
        self.port = free_port()
        self.proc = None
        self.addCleanup(self.stop_cockpit)

    # --- the door, through its CLI ------------------------------------

    def create(self, bead_id, payload):
        self.next_id_file.write_text(bead_id, encoding="utf-8")
        return subprocess.run(
            [str(DOOR), "create", json.dumps(payload, ensure_ascii=False)],
            env=self.door_env, text=True, capture_output=True,
        )

    def beads_left_by_the_door(self):
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.bead_dir.glob("*.json"))
        ]

    # --- the Cockpit, through HTTP ------------------------------------

    def start_cockpit(self, beads):
        self.state_file.write_text(json.dumps(beads), encoding="utf-8")
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
                "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
                "COCKPIT_BD_BIN": str(REQUESTS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": os.path.join(self.tmp.name, "cockpit.pid"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.1",
                "FAKE_BD_STATE_FILE": str(self.state_file),
                "FAKE_BD_FAIL_FLAG_FILE": os.path.join(self.tmp.name, "fail"),
            }
        )
        self.proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        wait_for_port(self.port)

    def stop_cockpit(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.proc.stdout.close()
        self.proc.stderr.close()
        self.proc = None

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=3) as resp:
            return resp.read().decode("utf-8")

    def requests_by_id(self, expected):
        deadline = time.time() + 5
        found = {}
        while time.time() < deadline:
            found = {r["id"]: r for r in json.loads(self.get("/api/requests"))["requests"]}
            if set(found) == set(expected):
                return found
            time.sleep(0.05)
        self.fail("the Cockpit lists %r, expected %r" % (sorted(found), sorted(expected)))

    # --- the contract --------------------------------------------------

    def test_what_the_door_accepts_the_cockpit_shows_as_written(self):
        ids = ["af-ok%d" % i for i in range(len(DISPLAYABLE))]
        for bead_id, payload in zip(ids, DISPLAYABLE):
            result = self.create(bead_id, payload)
            self.assertEqual(0, result.returncode, result.stderr)
        self.start_cockpit(self.beads_left_by_the_door())
        shown = self.requests_by_id(ids)
        for bead_id, payload in zip(ids, DISPLAYABLE):
            request = shown[bead_id]
            self.assertFalse(request["incomplete"], request)
            self.assertEqual([], request["missing_fields"])
            self.assertEqual(payload["quoi"], request["quoi"])
            self.assertEqual(payload["pourquoi"], request["pourquoi"])
            self.assertEqual(
                [(o["option"], o["consequence"]) for o in payload["que_faire"]],
                [(o["option"], o["consequence"]) for o in request["que_faire"]],
            )

    def test_the_door_refuses_the_four_proposals_the_cockpit_could_not_show(self):
        for bead in REFUSED:
            with self.subTest(bead=bead["id"]):
                result = self.create(bead["id"], payload_of(bead))
                self.assertNotEqual(0, result.returncode)
                self.assertIn("le Cockpit ne pourrait pas l'afficher", result.stderr)
                # The producer reads which field and why, not a bare refusal.
                self.assertRegex(result.stderr, r"contient un (identifiant|terme interne)")
        self.assertEqual([], self.beads_left_by_the_door(), "a refused proposal must write nothing")

    def test_the_cockpit_says_why_and_keeps_the_text_of_the_four_existing_ones(self):
        """The four exist in Beads and the door never rewrites a proposal:
        the main text stays the fixed repli (an identifier or an internal
        term never reaches it), the folded details give the reason and the
        text exactly as written."""
        self.start_cockpit(REFUSED)
        shown = self.requests_by_id([bead["id"] for bead in REFUSED])
        expected_missing = {
            "af-os9sh2": ["quoi", "pourquoi", "que_faire"],
            "af-vnv59w": ["quoi", "pourquoi", "que_faire"],
            "af-1ai5e3": ["pourquoi", "que_faire"],
            "af-vws964": ["pourquoi", "que_faire"],
        }
        home = self.get("/")
        for bead in REFUSED:
            with self.subTest(bead=bead["id"]):
                request = shown[bead["id"]]
                metadata = bead["metadata"]
                self.assertEqual(expected_missing[bead["id"]], request["missing_fields"])
                for field_name in request["missing_fields"]:
                    self.assertTrue(request["motifs"][field_name], field_name)
                    for reason in request["motifs"][field_name]:
                        self.assertNotIn("manquant", reason, "the field is present, not missing")
                    self.assertEqual(
                        metadata["gc.proposal_" + field_name], request["texte_origine"][field_name]
                    )
                if "quoi" not in request["missing_fields"]:
                    self.assertEqual(metadata["gc.proposal_quoi"], request["quoi"])
                import html as html_module
                self.assertIn(html_module.escape(metadata["gc.proposal_pourquoi"]), home)
        self.assertIn("cockpit-request-motif", home)
        self.assertIn("cockpit-request-origine", home)

    def test_identifiers_go_in_details_and_show_only_folded(self):
        payload = dict(
            DISPLAYABLE[1],
            details="af-6jyjrz, af-guyzth ; PR #360 ; pr-autopilot ; le Mayor ferme à la main",
        )
        result = self.create("af-det1", payload)
        self.assertEqual(0, result.returncode, result.stderr)
        self.start_cockpit(self.beads_left_by_the_door())
        request = self.requests_by_id(["af-det1"])["af-det1"]
        self.assertFalse(request["incomplete"], request)
        self.assertEqual(payload["details"], request["precisions"])
        home = self.get("/")
        self.assertIn('cockpit-request-precisions"><span>Précisions</span><code>af-6jyjrz', home)

    def test_door_and_cockpit_agree_on_every_case(self):
        """One verdict per payload, whichever side gives it."""
        cases = DISPLAYABLE + [payload_of(bead) for bead in REFUSED]
        seeded = []
        verdict_door = {}
        for index, payload in enumerate(cases):
            bead_id = "af-case%d" % index
            verdict_door[bead_id] = self.create(bead_id, payload).returncode == 0
            # What Beads would hold had the door let it through, as the
            # four did before this contract existed.
            lettered = [
                dict(option, lettre="abcdefghijklmnopqrstuvwxyz"[i])
                for i, option in enumerate(payload["que_faire"])
            ]
            seeded.append(
                {
                    "id": bead_id, "status": "open", "labels": ["proposal"], "notes": "",
                    "metadata": {
                        "gc.proposal_quoi": payload["quoi"],
                        "gc.proposal_pourquoi": payload["pourquoi"],
                        "gc.proposal_que_faire": json.dumps(lettered, ensure_ascii=False),
                        "gc.proposal_langue": payload["langue"],
                        "gc.proposal_state": "ouverte",
                        "gc.proposal_horodatage": "2026-10-06T10:00:00Z",
                    },
                }
            )
        self.start_cockpit(seeded)
        shown = self.requests_by_id([bead["id"] for bead in seeded])
        for bead_id, accepted in verdict_door.items():
            self.assertEqual(
                accepted, not shown[bead_id]["incomplete"],
                "%s: door accepted=%s, Cockpit incomplete=%s"
                % (bead_id, accepted, shown[bead_id]["incomplete"]),
            )


class TextCheckCli(unittest.TestCase):
    def run_check(self, payload):
        return subprocess.run(
            [str(TEXT_CHECK), json.dumps(payload, ensure_ascii=False)],
            text=True, capture_output=True,
        )

    def test_accepts_a_displayable_request(self):
        result = self.run_check(DISPLAYABLE[0])
        self.assertEqual((0, ""), (result.returncode, result.stderr))

    def test_names_the_field_and_the_reason(self):
        result = self.run_check(
            {
                "quoi": "Un texte lisible",
                "pourquoi": "voir af-th4gdf",
                "que_faire": [{"option": "Attendre", "consequence": "Le Mayor reprend la main."}],
            }
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("champ « pourquoi » contient un identifiant", result.stderr)
        self.assertIn("conséquence de l'option 1", result.stderr)
        self.assertNotIn("« quoi »", result.stderr)

    def test_refuses_a_body_that_is_not_an_object(self):
        result = subprocess.run([str(TEXT_CHECK), "[]"], text=True, capture_output=True)
        self.assertEqual(2, result.returncode)


if __name__ == "__main__":
    unittest.main()
