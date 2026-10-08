#!/usr/bin/env python3
"""The same scripts on the second project of the Delivery Fixture City (T35,
af-f62cxt; Spec af-wf4w5r §12, user story 79; Testing Decisions seam 2).

The second project (tests/fixtures/delivery-fixture-city-api) is written in
another language than the first one and serves no web page: a JSON API on
Node.js. Nothing here is told which language it is: the launcher, the red
step, the freeze, the green step and the prefactoring regime read its launch
recipe, its probe, its per-test test command, its seam mode and its
regression command in its profile. One test per pass and per refusal, each
refusal re-reading the tracker and the evidence store to prove nothing was
written. Only command lines are exercised; the product is launched for real
by bin/project-launch, the proofs are filed for real by bin/evidence-capture.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "tdd-step"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
LAUNCH_TOOL = ROOT / "bin" / "project-launch"
PROFILE_TOOL = ROOT / "bin" / "project-planning-profile"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city-api"
DESCRIPTOR = ROOT / FIXTURE / "descriptor.json"
FIRST_DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, PREFACTORING = "fx-t1", "fx-p1"

EXIT_REFUSED = 1

TESTS = f"{FIXTURE}/tests"
SERVER = f"{FIXTURE}/server.js"
TABLE = f"{TESTS}/criteria.json"
COUNT_FILE, HEALTH_FILE = f"{TESTS}/count.test.js", f"{TESTS}/health.test.js"
COUNT_ID = f"{COUNT_FILE}::count_is_answered"
HEALTH_ID = f"{HEALTH_FILE}::dataset_is_named"

CRITERIA = """## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] Point d'entrée : GET /items — Observable : champ count — Faux si : le nombre d'éléments n'y est pas
- [ ] Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent

## Target rigs

delivery-fixture-city-api"""

# Criterion 1: GET /items answers how many items the dataset holds.
COUNT_TEST = """'use strict';
const assert = require('node:assert');

module.exports = {
  async count_is_answered() {
    const body = await (await fetch(process.env.PRODUCT_ADDRESS + '/items')).json();
    assert.strictEqual(body.count, 3);
  },
};
"""

# Criterion 2: the health probe names the dataset served.
HEALTH_TEST = """'use strict';
const assert = require('node:assert');

module.exports = {
  async dataset_is_named() {
    const body = await (await fetch(process.env.PRODUCT_ADDRESS + '/health')).json();
    assert.strictEqual(body.dataset, 'content');
  },
};
"""

# Breaks before any assertion: an error, not a red.
COUNT_TEST_IN_ERROR = COUNT_TEST.replace("assert.strictEqual(body.count, 3);", "body.count.toFixed(0);")

# Fails by assertion, and asks the product nothing.
COUNT_TEST_WITHOUT_THE_PRODUCT = """'use strict';
const assert = require('node:assert');

module.exports = {
  count_is_answered() {
    assert.strictEqual(0, 3);
  },
};
"""


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SecondProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="second-project-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "EVIDENCE_STORE_DIR": str(self.store),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.seed_tracker()
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE)
        self.git("init", "-q", "-b", "main")
        self.base = self.commit("base")
        self.base_server = (self.repo / SERVER).read_text()

    # --- harness ------------------------------------------------------------

    def seed_tracker(self):
        """A marked convoy with a slice and a prefactoring of the second project."""
        def ticket(kind, description):
            return {"title": "ticket du second projet", "status": "open", "issue_type": "task",
                    "description": description, "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, PREFACTORING]},
            SLICE: ticket("vertical_slice", CRITERIA),
            PREFACTORING: ticket("prefactoring", "## What to build\n\nRanger la réponse."),
        }
        self.tracker.write_text(json.dumps({"beads": beads}))
        proc = subprocess.run(
            (str(STATE_TOOL), "mark", CONVOY, "--demonstration-line", f"{SLICE}=GET /items répond count = 3",
             "--user-stories", f"{SLICE}=1"),
            env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, message, files=None):
        for path, content in (files or {}).items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def commit_tests(self, files=None):
        """The red step of the author: the criterion tests and their table."""
        tests = {COUNT_FILE: COUNT_TEST, HEALTH_FILE: HEALTH_TEST,
                 TABLE: json.dumps({"criteria": {"1": [COUNT_ID], "2": [HEALTH_ID]}})}
        tests.update(files or {})
        return self.commit("tests de critère", tests)

    def green_server(self):
        """The product once the ticket is written: both criteria hold."""
        green = self.base_server.replace(
            "    state: String(dataset.state ?? ''),",
            "    state: String(dataset.state ?? ''),\n    count: Array.isArray(dataset.items) ? dataset.items.length : 0,",
        ).replace("{ status: 'ok' }", "{ status: 'ok', dataset: String(dataset.state) }")
        self.assertIn("count: Array.isArray", green)
        self.assertIn("dataset: String(dataset.state)", green)
        return green

    def profile(self, **launch):
        """The profile of the second project, with other launch declarations."""
        profile = json.loads(DESCRIPTOR.read_text())
        profile["launch"].update(launch)
        path = self.tmp / "descriptor.json"
        path.write_text(json.dumps(profile))
        return path

    def run_tool(self, step, ticket, *args, profile=DESCRIPTOR):
        argv = [str(TOOL), step, CONVOY, ticket, "--repo", str(self.repo)]
        if step != "freeze":
            argv += ["--profile", str(profile), "--dataset", "content"]
        return subprocess.run((*argv, *[str(a) for a in args]), env=self.env, text=True, capture_output=True, cwd=self.tmp)

    def ok(self, step, ticket=SLICE, *args, **kwargs):
        proc = self.run_tool(step, ticket, *args, **kwargs)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def refused(self, step, ticket=SLICE, *args, **kwargs):
        """A refusal: exit 1, one JSON answer, and neither the tracker nor
        the evidence store changed."""
        tracker_before, store_before = self.tracker.read_text(), self.store_files()
        proc = self.run_tool(step, ticket, *args, **kwargs)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertEqual(tracker_before, self.tracker.read_text(), "un refus a écrit dans le tracker")
        self.assertEqual(store_before, self.store_files(), "un refus a écrit dans le magasin de preuves")
        return answer["error"]

    def red(self, **kwargs):
        return self.ok("red", SLICE, "--base", self.base, "--table", TABLE, **kwargs)

    def red_refused(self, **kwargs):
        return self.refused("red", SLICE, "--base", self.base, "--table", TABLE, **kwargs)

    def state(self, *args):
        proc = subprocess.run((str(STATE_TOOL), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def reviewed(self):
        """The favorable review of the criterion tests proven red at HEAD,
        as bin/test-review records it, bound to what the freeze seals."""
        _, proof = self.piece("tdd_red")
        paths = [proof["table"], *(test["id"].partition("::")[0] for test in proof["tests"]),
                 *proof["frozen_harness_paths"]]
        fingerprints = {path: sha256_of(self.repo / path) for path in dict.fromkeys(paths)}
        request, verdict = self.tmp / "review-request.json", self.tmp / "review-verdict.json"
        request.write_text(json.dumps({"files": fingerprints, "criteria": proof["criteria"]}))
        self.state("open-test-review", CONVOY, SLICE, "--commit", proof["commit"], "--file", request)
        verdict.write_text(json.dumps({
            "commit": proof["commit"], "files": fingerprints, "recorded_by": "delivery-reviewer-fx",
            "tests": {test["id"]: {"state": "favorable"} for test in proof["tests"]}}))
        self.state("record-test-review", CONVOY, SLICE, "--file", verdict)

    def store_files(self):
        if not self.store.exists():
            return {}
        return {str(path.relative_to(self.store)): sha256_of(path)
                for path in sorted(self.store.rglob("*")) if path.is_file() and path.name != ".seal-key"}

    def ticket_state(self, ticket=SLICE):
        shown = self.state("show", CONVOY, "--repo", self.repo)
        return next(t for t in shown["tickets"] if t["id"] == ticket)

    def piece(self, name, ticket=SLICE):
        record = json.loads((self.store / SPEC / ticket / f"{name}.json").read_text())
        return record, json.loads(record["output"])

    def launch(self, *args):
        return subprocess.run((str(LAUNCH_TOOL), "--repo-root", str(self.repo), *[str(a) for a in args]),
                              env=self.env, text=True, capture_output=True)

    def describe(self, descriptor=DESCRIPTOR):
        proc = subprocess.run((str(PROFILE_TOOL), "describe", str(descriptor)), text=True, capture_output=True)
        return proc.returncode, json.loads(proc.stdout)

    # --- the launch command ----------------------------------------------------

    def test_launch_command_starts_the_second_project_by_the_recipe_of_its_profile_and_its_probe_answers(self):
        state = self.tmp / "launch.json"
        proc = self.launch("start", DESCRIPTOR, "--commit", self.base, "--dataset", "content", "--state-file", state)
        self.addCleanup(self.launch, "stop", "--state-file", state)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        record = json.loads(proc.stdout)

        self.assertTrue(record["started"])
        self.assertEqual((self.base, "content"), (record["commit"], record["dataset"]))
        with urllib.request.urlopen(record["address"] + "/health", timeout=5) as probe:
            self.assertEqual((200, {"status": "ok"}), (probe.status, json.loads(probe.read())))
        with urllib.request.urlopen(record["address"] + "/items", timeout=5) as answer:
            self.assertEqual("application/json", answer.headers["Content-Type"])
            self.assertEqual({"state": "content", "generated_at": "2026-01-01T00:00:00Z",
                              "items": ["alpha", "beta", "gamma"]}, json.loads(answer.read()))
        # No web page: the product serves nothing at its root.
        with self.assertRaises(urllib.error.HTTPError) as no_page:
            urllib.request.urlopen(record["address"] + "/", timeout=5)
        self.assertEqual(404, no_page.exception.code)

        stopped = self.launch("stop", "--state-file", state)
        self.assertEqual(0, stopped.returncode, stopped.stdout + stopped.stderr)
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(record["address"] + "/health", timeout=2)

    def test_the_second_project_is_of_another_language_than_the_first_and_declares_no_screen(self):
        _, first = self.describe(FIRST_DESCRIPTOR)
        status, second = self.describe()

        self.assertEqual(0, status)
        self.assertEqual("{python}", first["launch"]["recipe"][0])
        self.assertEqual("node", second["launch"]["recipe"][0])
        self.assertTrue(second["launch"]["test_command"].startswith("node "))
        self.assertIn("screens", first["launch"])
        self.assertNotIn("screens", second["launch"])
        # The same declarations, whatever the language.
        self.assertEqual(set(first["launch"]) - {"screens"}, set(second["launch"]) - {"anchors"})

    # --- the equivalent of the anchors, for an interface that is not a web page ---

    def test_profile_reading_command_renders_the_equivalent_of_the_anchors_of_the_second_project(self):
        status, described = self.describe()

        self.assertEqual(0, status)
        anchors = described["launch"]["anchors"]
        self.assertEqual({"equivalent"}, set(anchors))
        self.assertEqual(
            [("items-state", "GET /items", "champ state"), ("items-generated-at", "GET /items", "champ generated_at"),
             ("items-list", "GET /items", "champ items"), ("health-status", "GET /health", "champ status")],
            [(a["name"], a["entry_point"], a["observable"]) for a in anchors["equivalent"]])

    def test_profile_reading_command_renders_anchors_without_object_with_their_reason(self):
        reason = "une ligne de commande sans sortie structurée"
        status, described = self.describe(self.profile(anchors={"not_applicable": reason}))

        self.assertEqual(0, status)
        self.assertEqual({"not_applicable": reason}, described["launch"]["anchors"])

    def test_a_profile_without_the_declaration_renders_none(self):
        _, described = self.describe(FIRST_DESCRIPTOR)

        self.assertNotIn("anchors", described["launch"])

    def test_malformed_anchor_declarations_are_rejected(self):
        named = {"name": "items-list", "entry_point": "GET /items", "observable": "champ items"}
        for anchors, expected in (
            ({"not_applicable": ""}, "not_applicable"),
            ({"not_applicable": "   "}, "not_applicable"),
            ({}, "equivalent"),
            ({"equivalent": [named], "not_applicable": "sans objet"}, "equivalent"),
            ({"equivalent": []}, "equivalent"),
            ({"equivalent": [named, named]}, "items-list"),
            ({"equivalent": [{**named, "entry_point": "GET /absent"}]}, "GET /absent"),
            ({"equivalent": [{**named, "observable": ""}]}, "observable"),
            ({"equivalent": [{**named, "name": "deux mots"}]}, "name"),
            ({"equivalent": [named], "selector": "x"}, "selector"),
            ("sans objet", "anchors"),
        ):
            with self.subTest(anchors=anchors):
                status, answer = self.describe(self.profile(anchors=anchors))
                self.assertEqual(1, status)
                self.assertFalse(answer["valid"])
                self.assertIn("launch.anchors", answer["error"])
                self.assertIn(expected, answer["error"])

    # --- the red script and the green script -----------------------------------

    def test_red_passes_on_a_ticket_of_the_second_project_with_the_test_command_and_seam_mode_of_its_profile(self):
        head = self.commit_tests()

        answer = self.red()

        self.assertEqual(("red", head), (answer["step"], answer["commit"]))
        state = self.ticket_state()
        self.assertEqual((head, self.base), (state["tdd"]["red"]["commit"], state["tdd"]["red"]["base"]))
        self.assertIsNone(state["stop"])
        record, proof = self.piece("tdd_red")
        self.assertEqual(head, record["commit"])
        self.assertEqual(("red", "black_box"), (proof["verdict"], proof["seam_mode"]))
        self.assertEqual({COUNT_ID: ("failure", ["GET /items"]), HEALTH_ID: ("failure", ["GET /health"])},
                         {test["id"]: (test["outcome"], test["entry_points"]) for test in proof["tests"]})
        self.assertEqual([f"{TESTS}/harness.js"], proof["frozen_harness_paths"])
        self.assertEqual({"healthy": True, "commit": self.base}, proof["launch"])

    def test_green_passes_on_a_ticket_of_the_second_project_k_times(self):
        self.commit_tests()
        self.red()
        self.reviewed()
        frozen = self.ok("freeze")
        head = self.commit("code du ticket", {SERVER: self.green_server()})

        answer = self.ok("green")

        self.assertEqual(("green", head), (answer["step"], answer["commit"]))
        self.assertEqual(head, self.ticket_state()["tdd"]["green"]["commit"])
        _, registry = self.piece("tdd_freeze")
        self.assertEqual({TABLE, COUNT_FILE, HEALTH_FILE, f"{TESTS}/harness.js"}, set(registry["files"]))
        self.assertEqual(frozen["commit"], registry["commit"])
        _, proof = self.piece("tdd_green")
        self.assertEqual(("green", 3, "black_box"), (proof["verdict"], proof["k"], proof["seam_mode"]))
        self.assertEqual({COUNT_ID: (["passed"] * 3, ["GET /items"]), HEALTH_ID: (["passed"] * 3, ["GET /health"])},
                         {test["id"]: (test["runs"], test["entry_points"]) for test in proof["tests"]})
        proc = subprocess.run((str(CAPTURE_TOOL), "verify", CONVOY, SLICE), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual({"tdd_red", "tdd_freeze", "tdd_green"}, {e["piece"] for e in json.loads(proc.stdout)["pieces"]})

    def test_green_reads_k_in_the_profile_of_the_second_project(self):
        self.commit_tests()
        self.red()
        self.reviewed()
        self.ok("freeze")
        self.commit("code du ticket", {SERVER: self.green_server()})

        self.ok("green", profile=self.profile(k=2))

        _, proof = self.piece("tdd_green")
        self.assertEqual({COUNT_ID: ["passed"] * 2, HEALTH_ID: ["passed"] * 2},
                         {test["id"]: test["runs"] for test in proof["tests"]})

    def test_green_refuses_a_ticket_of_the_second_project_whose_code_is_not_written(self):
        self.commit_tests()
        self.red()
        self.reviewed()
        self.ok("freeze")

        error = self.refused("green")

        self.assertIn(f"test en échec : {COUNT_ID}", error)

    def test_red_refuses_a_criterion_test_of_the_second_project_that_breaks_before_its_assertion(self):
        self.commit_tests({COUNT_FILE: COUNT_TEST_IN_ERROR})

        error = self.red_refused()

        self.assertIn(f"test en erreur : {COUNT_ID} (TypeError", error)
        self.assertIn("un rouge valable est un échec d'assertion", error)

    def test_red_refuses_a_criterion_test_of_the_second_project_that_asks_the_product_nothing(self):
        self.commit_tests({COUNT_FILE: COUNT_TEST_WITHOUT_THE_PRODUCT})

        error = self.red_refused()

        self.assertIn(f"aucun point d'entrée du produit : {COUNT_ID}", error)

    def test_red_refuses_a_file_of_the_second_project_changed_outside_its_test_perimeter(self):
        self.commit_tests({SERVER: self.green_server()})

        error = self.red_refused()

        self.assertIn(f"fichier modifié hors du périmètre de test : {SERVER}", error)

    def test_prefactoring_runs_the_regression_command_of_the_second_project_before_and_after(self):
        head = self.commit("rangement", {SERVER: self.base_server.replace("function respond(", "function answer(")
                                         .replace("respond(response", "answer(response")})

        answer = self.ok("prefactoring", PREFACTORING, "--base", self.base)

        self.assertEqual(head, answer["commit"])
        _, proof = self.piece("tdd_prefactoring", PREFACTORING)
        self.assertEqual(json.loads(DESCRIPTOR.read_text())["launch"]["regression_command"], proof["command"])
        self.assertEqual([(self.base, 0), (head, 0)], [(run["commit"], run["exit_code"]) for run in proof["regression"]])

    def test_prefactoring_refuses_a_change_that_breaks_the_regression_command_of_the_second_project(self):
        self.commit("rangement qui casse", {SERVER: self.base_server.replace("items: Array.isArray", "elements: Array.isArray")})

        error = self.refused("prefactoring", PREFACTORING, "--base", self.base)

        self.assertIn("commande de régression en échec après le changement", error)


if __name__ == "__main__":
    unittest.main()
