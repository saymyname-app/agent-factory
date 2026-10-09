#!/usr/bin/env python3
"""bin/tdd-step on a fake tracker state (T10, af-j8jo02; Spec af-wf4w5r §5,
Testing Decisions seam 2): one test per pass and per refusal, each refusal
re-reading the tracker and the evidence store to prove nothing was written.
Only command lines are exercised. The product is a copy of the Delivery
Fixture City in a throwaway repository, launched for real by
bin/project-launch; the proofs are filed for real by bin/evidence-capture."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "tdd-step"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
DESCRIPTOR = ROOT / FIXTURE / "descriptor.json"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, RECIPE_SLICE, PREFACTORING = "fx-t1", "fx-t2", "fx-p1"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4
EXIT_STOPPED = 5

TESTS = f"{FIXTURE}/tests"
APP = f"{FIXTURE}/app.py"
TABLE = f"{TESTS}/criteria.json"
REGRESSION_FILE = f"{TESTS}/regression.py"
COUNT_FILE, HEALTH_FILE = f"{TESTS}/test_count.py", f"{TESTS}/test_health.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
HEALTH_ID = f"{HEALTH_FILE}::HealthTest.test_dataset_is_named"

CRITERIA = """## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas
- [ ] Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent

## Target rigs

delivery-fixture-city"""

# Criterion 1: the home page shows how many items the dataset holds.
COUNT_TEST = """import os
import unittest
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        page = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/").read().decode()
        self.assertIn('<p data-anchor="fixture-count">3</p>', page)
"""

# Criterion 2: the health probe names the dataset served.
HEALTH_TEST = """import json
import os
import unittest
import urllib.request


class HealthTest(unittest.TestCase):
    def test_dataset_is_named(self):
        body = json.loads(urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/health").read())
        self.assertEqual("content", body.get("dataset"))
"""

# Already true of the product at the start commit.
HEALTH_TEST_ALREADY_GREEN = HEALTH_TEST.replace(
    'self.assertEqual("content", body.get("dataset"))', 'self.assertEqual("ok", body.get("status"))')

# Reaches the code of the product without going through an entry point.
COUNT_TEST_THROUGH_THE_CODE = """import pathlib
import unittest


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text()
        self.assertIn("fixture-count", source)
"""

# Fails by assertion, and asks the product nothing.
COUNT_TEST_WITHOUT_THE_PRODUCT = """import unittest


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        self.assertEqual(3, 0)
"""

# Library seam: the test calls the product's public module.
IMPORT_TEST = """import sys
import unittest

sys.path.insert(0, "tests/fixtures/delivery-fixture-city")
import app


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        self.assertEqual(3, app.count_items({"items": ["a", "b", "c"]}))
"""

IMPORT_TEST_OF_AN_INTERNAL = IMPORT_TEST.replace("import app\n", "from app import FixtureHandler\n").replace(
    "self.assertEqual(3, app.count_items({\"items\": [\"a\", \"b\", \"c\"]}))",
    "self.assertTrue(hasattr(FixtureHandler, 'count_items'))")


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TddStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tdd-step-test-"))
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
        # The fixture as git holds it: a bytecode cache another suite left in
        # it would be committed here as a file of the test perimeter.
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        self.git("init", "-q", "-b", "main")
        self.base = self.commit("base")
        self.base_app = (self.repo / APP).read_text()

    # --- harness ------------------------------------------------------------

    def seed_tracker(self):
        """A marked convoy with two slices and a prefactoring, and a convoy
        without the mark."""
        def ticket(kind, description=CRITERIA):
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": description, "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, RECIPE_SLICE, PREFACTORING]},
            SLICE: ticket("vertical_slice"), RECIPE_SLICE: ticket("vertical_slice"),
            PREFACTORING: ticket("prefactoring", "## What to build\n\nRanger le rendu."),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads}))
        proc = subprocess.run(
            (str(STATE_TOOL), "mark", CONVOY,
             "--demonstration-line", f"{SLICE}=La page d'accueil affiche 3",
             "--demonstration-line", f"{RECIPE_SLICE}=Le produit se lance",
             "--user-stories", f"{SLICE}=1", "--user-stories", f"{RECIPE_SLICE}=3",
             "--establishes-launch-recipe", RECIPE_SLICE),
            env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, message, files=None, remove=()):
        """One commit of the ticket branch: the files given, by path."""
        for path, content in (files or {}).items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        for path in remove:
            (self.repo / path).unlink()
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def table(self, criteria=None):
        return json.dumps({"criteria": criteria or {"1": [COUNT_ID], "2": [HEALTH_ID]}})

    def commit_tests(self, files=None, table=None):
        """The red step of the author: the criterion tests and their table."""
        tests = {COUNT_FILE: COUNT_TEST, HEALTH_FILE: HEALTH_TEST, TABLE: table or self.table()}
        tests.update(files or {})
        return self.commit("tests de critère", tests)

    def green_app(self):
        """The product once the ticket is written: both criteria hold."""
        return self.base_app.replace(
            '"</body></html>"', 'f\'<p data-anchor="fixture-count">{len(items)}</p>\'\n            "</body></html>"',
        ).replace('{"status": "ok"}', '{"status": "ok", "dataset": self.dataset.get("state")}')

    def descriptor(self, **launch):
        """The profile of the fixture, with other launch declarations; a
        declaration given as None is removed."""
        profile = json.loads(DESCRIPTOR.read_text())
        profile["launch"].update(launch)
        for field in [field for field, value in launch.items() if value is None]:
            del profile["launch"][field]
        path = self.tmp / "descriptor.json"
        path.write_text(json.dumps(profile))
        return path

    def run_tool(self, step, ticket, *args, convoy=CONVOY, profile=DESCRIPTOR, env=None):
        argv = [str(TOOL), step, convoy, ticket, "--repo", str(self.repo)]
        if step != "freeze":
            argv += ["--profile", str(profile), "--dataset", "content"]
        return subprocess.run(
            (*argv, *[str(a) for a in args]), env=env or self.env, text=True, capture_output=True, cwd=self.tmp)

    def ok(self, step, ticket=SLICE, *args, **kwargs):
        proc = self.run_tool(step, ticket, *args, **kwargs)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def refused(self, step, ticket=SLICE, *args, status=EXIT_REFUSED, **kwargs):
        """A refusal: the expected exit status, one JSON answer, and neither
        the tracker nor the evidence store changed."""
        tracker_before, store_before = self.tracker.read_text(), self.store_files()
        proc = self.run_tool(step, ticket, *args, **kwargs)
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertEqual(tracker_before, self.tracker.read_text(), "un refus a écrit dans le tracker")
        self.assertEqual(store_before, self.store_files(), "un refus a écrit dans le magasin de preuves")
        return answer.get("error") or answer.get("message")

    def red(self, ticket=SLICE, *args, **kwargs):
        return self.ok("red", ticket, "--base", self.base, "--table", TABLE, *args, **kwargs)

    def red_refused(self, ticket=SLICE, **kwargs):
        return self.refused("red", ticket, "--base", self.base, "--table", TABLE, **kwargs)

    def frozen(self):
        """A ticket whose criterion tests are proven red, reviewed and frozen."""
        self.commit_tests()
        self.red()
        self.reviewed()
        return self.ok("freeze")

    def state(self, *args):
        proc = subprocess.run((str(STATE_TOOL), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def reviewed(self, refused=None, files=None, ticket=SLICE):
        """The review of the criterion tests proven red at HEAD (T13), as
        bin/test-review records it: every test favorable, except those of
        `refused`; bound to the fingerprints of what the freeze seals, or to
        `files`."""
        _, proof = self.piece("tdd_red", ticket)
        paths = [proof["table"], *(test["id"].partition("::")[0] for test in proof["tests"]),
                 *proof["frozen_harness_paths"]]
        fingerprints = {path: sha256_of(self.repo / path) for path in dict.fromkeys(paths)}
        fingerprints.update(files or {})
        request, verdict = self.tmp / "review-request.json", self.tmp / "review-verdict.json"
        request.write_text(json.dumps({"files": fingerprints, "criteria": proof["criteria"]}))
        self.state("open-test-review", CONVOY, ticket, "--commit", proof["commit"], "--file", request)
        answers = {test["id"]: {"state": "unfavorable", "reason": refused[test["id"]]} if test["id"] in (refused or {})
                   else {"state": "favorable"} for test in proof["tests"]}
        verdict.write_text(json.dumps({"commit": proof["commit"], "files": fingerprints, "tests": answers,
                                       "recorded_by": "delivery-reviewer-fx"}))
        return self.state("record-test-review", CONVOY, ticket, "--file", verdict)

    def store_files(self):
        if not self.store.exists():
            return {}
        return {
            str(path.relative_to(self.store)): sha256_of(path)
            for path in sorted(self.store.rglob("*")) if path.is_file() and path.name != ".seal-key"
        }

    def ticket_state(self, ticket=SLICE):
        proc = subprocess.run((str(STATE_TOOL), "show", CONVOY, "--repo", str(self.repo)),
                              env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket)

    def piece(self, name, ticket=SLICE):
        """What the script recorded in one piece of the evidence store."""
        record = json.loads((self.store / SPEC / ticket / f"{name}.json").read_text())
        return record, json.loads(record["output"])

    def verified(self, ticket=SLICE):
        proc = subprocess.run((str(CAPTURE_TOOL), "verify", CONVOY, ticket), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return {entry["piece"] for entry in json.loads(proc.stdout)["pieces"]}

    # --- red step -----------------------------------------------------------

    def test_red_passes_and_records_the_proof_when_every_criterion_test_fails_by_assertion(self):
        head = self.commit_tests()

        answer = self.red()

        self.assertEqual(("red", head), (answer["step"], answer["commit"]))
        state = self.ticket_state()
        self.assertEqual((head, self.base), (state["tdd"]["red"]["commit"], state["tdd"]["red"]["base"]))
        self.assertIsNone(state["stop"])
        self.assertEqual(head, state["evidence"]["tdd_red"]["commit"])
        self.assertEqual({"tdd_red"}, self.verified())
        record, proof = self.piece("tdd_red")
        self.assertEqual(head, record["commit"])
        self.assertEqual("red", proof["verdict"])
        self.assertEqual({"1": [COUNT_ID], "2": [HEALTH_ID]}, proof["criteria"])
        self.assertEqual({COUNT_ID: "failure", HEALTH_ID: "failure"},
                         {test["id"]: test["outcome"] for test in proof["tests"]})

    def test_red_refuses_a_criterion_test_in_error(self):
        self.commit_tests({HEALTH_FILE: HEALTH_TEST.replace("body.get(\"dataset\")", "body[\"dataset\"]")})

        error = self.red_refused()

        self.assertIn(HEALTH_ID, error)
        self.assertIn("erreur", error)
        self.assertIn("KeyError", error)
        self.assertNotIn(COUNT_ID, error)

    def test_red_refuses_an_empty_criterion_test(self):
        empty = f"{HEALTH_FILE}::HealthTest"
        self.commit_tests(
            {HEALTH_FILE: "import unittest\n\n\nclass HealthTest(unittest.TestCase):\n    pass\n"},
            table=self.table({"1": [COUNT_ID], "2": [empty]}))

        error = self.red_refused()

        self.assertIn(f"test vide : {empty}", error)

    def test_red_refuses_a_criterion_without_a_test(self):
        self.commit_tests(table=self.table({"1": [COUNT_ID, HEALTH_ID]}))

        error = self.red_refused()

        self.assertIn("critère 2 sans test", error)

    def test_red_refuses_a_table_naming_a_test_outside_the_test_perimeter(self):
        self.commit_tests(table=self.table({"1": [COUNT_ID], "2": [f"{APP}::HealthTest"]}))

        error = self.red_refused()

        self.assertIn(APP, error)
        self.assertIn("périmètre de test", error)

    def test_red_stops_the_ticket_on_a_criterion_already_green(self):
        self.commit_tests({HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})
        store_before = self.store_files()

        proc = self.run_tool("red", SLICE, "--base", self.base, "--table", TABLE)

        self.assertEqual(EXIT_STOPPED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertTrue(answer["stopped"])
        self.assertIn("critère 2 déjà vert", answer["error"])
        self.assertNotIn("critère 1", answer["error"])
        state = self.ticket_state()
        self.assertEqual("criterion_already_green", state["stop"]["reason"])
        self.assertIn("critère 2", state["stop"]["detail"])
        self.assertEqual({}, state["tdd"])
        self.assertEqual(store_before, self.store_files())

    def test_a_stopped_ticket_is_refused_by_every_step(self):
        self.commit_tests({HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})
        self.run_tool("red", SLICE, "--base", self.base, "--table", TABLE)
        self.commit("test corrigé", {HEALTH_FILE: HEALTH_TEST})

        self.assertIn("ticket arrêté", self.red_refused())
        self.assertIn("ticket arrêté", self.refused("freeze"))
        self.assertIn("ticket arrêté", self.refused("green"))

    def test_red_refuses_a_file_changed_outside_the_test_perimeter(self):
        self.commit_tests({APP: self.green_app()})

        error = self.red_refused()

        self.assertIn(f"hors du périmètre de test : {APP}", error)

    def test_red_refuses_an_unhealthy_product(self):
        self.base = self.commit("produit cassé", {APP: "raise SystemExit(1)\n"})
        self.commit_tests()

        error = self.red_refused()

        self.assertIn("bonne santé", error)

    def test_red_accepts_the_launch_failure_of_the_slice_that_establishes_the_launch_recipe(self):
        """Declared case: the product does not launch yet, and that failure
        is the red this slice is expected to show."""
        self.base = self.commit("produit sans recette", {APP: "raise SystemExit(1)\n"})
        head = self.commit_tests()

        self.red(RECIPE_SLICE)

        self.assertEqual(head, self.ticket_state(RECIPE_SLICE)["tdd"]["red"]["commit"])
        _, proof = self.piece("tdd_red", RECIPE_SLICE)
        self.assertEqual("red", proof["verdict"])
        self.assertFalse(proof["launch"]["healthy"])
        self.assertEqual({"error"}, {test["outcome"] for test in proof["tests"]})

    def test_red_accepts_a_missing_symbol_when_the_profile_declares_it(self):
        """Declared case: on a library seam, a missing symbol is the red."""
        self.commit_tests({COUNT_FILE: IMPORT_TEST}, table=self.table({"1": [COUNT_ID], "2": [COUNT_ID]}))
        rule = {"product_import": r"^\s*(?:import|from)\s+app\b", "entry_point_import": r"^import app$"}

        self.assertIn("AttributeError", self.red_refused(profile=self.descriptor(seam_mode="import_rule", import_rule=rule)))
        self.red(profile=self.descriptor(seam_mode="import_rule", import_rule=rule, red_error_types=["AttributeError"]))

        _, proof = self.piece("tdd_red")
        self.assertEqual("import_rule", proof["seam_mode"])
        self.assertEqual([{"id": COUNT_ID, "outcome": "error"}],
                         [{"id": test["id"], "outcome": test["outcome"]} for test in proof["tests"]])

    # --- red step: proof of the seam ----------------------------------------

    def test_red_records_the_entry_point_each_black_box_test_went_through(self):
        self.commit_tests()

        self.red()

        _, proof = self.piece("tdd_red")
        self.assertEqual("black_box", proof["seam_mode"])
        requests = {test["id"]: test["entry_points"] for test in proof["tests"]}
        self.assertEqual({COUNT_ID: ["GET /"], HEALTH_ID: ["GET /health"]}, requests)

    # --- red step: a mode per seam (T38, af-8o4jcp) ---------------------------

    IMPORT_RULE = {"product_import": r"^\s*(?:import|from)\s+app\b", "entry_point_import": r"^import app$"}

    def two_seams(self, black_box, import_rule):
        """A profile with two seams of different modes, each over one test file."""
        return self.descriptor(
            seam_mode=None, import_rule=self.IMPORT_RULE, red_error_types=["AttributeError"],
            seams=[{"name": "http", "mode": "black_box", "test_paths": [black_box]},
                   {"name": "library", "mode": "import_rule", "test_paths": [import_rule]}])

    def test_red_proves_each_criterion_test_by_the_mode_of_its_seam_and_names_both_per_test(self):
        self.commit_tests({COUNT_FILE: IMPORT_TEST})

        self.red(profile=self.two_seams(black_box=HEALTH_FILE, import_rule=COUNT_FILE))

        _, proof = self.piece("tdd_red")
        tests = {test["id"]: test for test in proof["tests"]}
        self.assertEqual({COUNT_ID: ("library", "import_rule"), HEALTH_ID: ("http", "black_box")},
                         {test_id: (test["seam"], test["seam_mode"]) for test_id, test in tests.items()})
        # Black box: the entry point the test asked. Import rule: none is recorded.
        self.assertEqual(["GET /health"], tests[HEALTH_ID]["entry_points"])
        self.assertNotIn("entry_points", tests[COUNT_ID])
        self.assertEqual("black_box+import_rule", proof["seam_mode"])

    def test_red_applies_the_import_rule_to_the_tests_of_the_import_rule_seam_only(self):
        """The same tests, the modes exchanged: the test that asks the
        product over http is now held to the import rule, and fails it; the
        rule is not applied to the test of the black-box seam."""
        self.commit_tests({COUNT_FILE: IMPORT_TEST})

        error = self.red_refused(profile=self.two_seams(black_box=COUNT_FILE, import_rule=HEALTH_FILE))

        self.assertIn(f"aucun point d'entrée du produit : {HEALTH_ID} (règle d'import", error)
        self.assertNotIn(f"{COUNT_ID} (règle d'import", error)

    def test_red_refuses_the_test_of_a_black_box_seam_that_asks_no_entry_point(self):
        silent = f"{HEALTH_FILE}::CountTest.test_count_is_shown"
        self.commit_tests({COUNT_FILE: IMPORT_TEST, HEALTH_FILE: COUNT_TEST_WITHOUT_THE_PRODUCT},
                          table=self.table({"1": [COUNT_ID], "2": [silent]}))

        error = self.red_refused(profile=self.two_seams(black_box=HEALTH_FILE, import_rule=COUNT_FILE))

        self.assertIn(f"aucun point d'entrée du produit : {silent} (seam http, boîte noire", error)
        self.assertNotIn(f"aucun point d'entrée du produit : {COUNT_ID}", error)

    def test_red_refuses_a_criterion_test_that_goes_through_no_declared_seam(self):
        self.commit_tests()
        profile = self.descriptor(seam_mode=None, seams=[
            {"name": "http", "mode": "black_box", "test_paths": [HEALTH_FILE]}])

        error = self.red_refused(profile=profile)

        self.assertIn(f"test hors de tout seam : {COUNT_ID}", error)

    def test_red_names_the_seam_and_the_mode_of_each_test_of_a_profile_with_one_seam_mode(self):
        self.commit_tests()

        self.red()

        _, proof = self.piece("tdd_red")
        self.assertEqual({("default", "black_box")}, {(test["seam"], test["seam_mode"]) for test in proof["tests"]})

    def test_red_refuses_a_black_box_test_that_reaches_the_code_without_an_entry_point(self):
        self.commit_tests({COUNT_FILE: COUNT_TEST_THROUGH_THE_CODE})

        error = self.red_refused()

        self.assertIn(f"aucun point d'entrée du produit : {COUNT_ID}", error)
        self.assertNotIn(f"point d'entrée du produit : {HEALTH_ID}", error)

    def test_red_refuses_a_black_box_test_that_asks_the_product_nothing(self):
        self.commit_tests({COUNT_FILE: COUNT_TEST_WITHOUT_THE_PRODUCT})

        error = self.red_refused()

        self.assertIn(f"aucun point d'entrée du produit : {COUNT_ID}", error)

    def test_red_refuses_an_import_outside_the_declared_entry_points(self):
        self.commit_tests({COUNT_FILE: IMPORT_TEST_OF_AN_INTERNAL},
                          table=self.table({"1": [COUNT_ID], "2": [COUNT_ID]}))
        rule = {"product_import": r"^\s*(?:import|from)\s+app\b", "entry_point_import": r"^import app$"}

        error = self.red_refused(profile=self.descriptor(seam_mode="import_rule", import_rule=rule))

        self.assertIn("règle d'import", error)
        self.assertIn(COUNT_FILE, error)
        self.assertIn("from app import FixtureHandler", error)

    # --- freeze -------------------------------------------------------------

    def test_freeze_records_the_fingerprints_of_tests_table_and_harness_outside_the_work_tree(self):
        head = self.commit_tests()
        self.red()
        self.reviewed()

        answer = self.ok("freeze")

        self.assertEqual(head, self.ticket_state()["tdd"]["freeze"]["commit"])
        registry = Path(answer["registry"])
        self.assertEqual(self.store / SPEC / SLICE / "tdd_freeze.json", registry)
        self.assertNotIn(self.repo, registry.parents)
        _, frozen = self.piece("tdd_freeze")
        self.assertEqual(
            sorted([COUNT_FILE, HEALTH_FILE, TABLE, f"{TESTS}/conftest.py", f"{TESTS}/harness.py"]),
            sorted(frozen["files"]))
        self.assertEqual(sha256_of(self.repo / COUNT_FILE), frozen["files"][COUNT_FILE])
        self.assertEqual({"tdd_red", "tdd_freeze"}, self.verified())

    def test_freeze_refused_without_a_red_proof(self):
        self.commit_tests()

        self.assertIn("rouge", self.refused("freeze"))

    def test_freeze_refused_when_a_commit_was_added_after_the_red_proof(self):
        self.commit_tests()
        self.red()
        self.commit("test affaibli", {HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})

        self.assertIn("rouge", self.refused("freeze"))

    def test_freeze_refused_without_a_review_of_the_criterion_tests(self):
        """T13: the freeze follows a favorable verdict of the test reviewer."""
        self.commit_tests()
        self.red()

        error = self.refused("freeze")

        self.assertIn("relecture", error)
        self.assertIn("aucun verdict", error)

    def test_freeze_refused_when_the_review_refuses_a_criterion_test(self):
        self.commit_tests()
        self.red()
        self.reviewed(refused={COUNT_ID: "le test ne vérifie qu'un statut 200"})

        error = self.refused("freeze")

        self.assertIn("relecture", error)
        self.assertIn(COUNT_ID, error)
        self.assertIn("statut 200", error)

    def test_freeze_refused_when_the_verdict_is_bound_to_other_fingerprints_of_tests(self):
        """A verdict given on other tests than the ones about to be frozen."""
        self.commit_tests()
        self.red()
        self.reviewed(files={COUNT_FILE: "sha256:" + "0" * 64})

        error = self.refused("freeze")

        self.assertIn("empreintes", error)
        self.assertIn(COUNT_FILE, error)
        self.assertNotIn(HEALTH_FILE, error)

    def test_freeze_refused_when_the_tests_changed_since_their_review(self):
        self.commit_tests()
        self.red()
        self.reviewed()
        self.commit_tests({COUNT_FILE: COUNT_TEST.replace("fixture-count", "fixture-total")})
        self.red()

        self.assertIn("relecture", self.refused("freeze"))

    def test_freeze_refused_when_the_registry_would_sit_in_a_work_tree(self):
        """The registry of fingerprints is never a file of the branch."""
        self.commit_tests()
        self.red()
        self.reviewed()

        error = self.refused("freeze", env={**self.env, "EVIDENCE_STORE_DIR": str(self.repo / "registre")})

        self.assertIn("dépôt Git", error)

    # --- green step ---------------------------------------------------------

    def test_green_passes_when_the_frozen_tests_pass_k_times(self):
        self.frozen()
        head = self.commit("code du ticket", {APP: self.green_app()})

        answer = self.ok("green")

        self.assertEqual(("green", head), (answer["step"], answer["commit"]))
        self.assertEqual(head, self.ticket_state()["tdd"]["green"]["commit"])
        _, proof = self.piece("tdd_green")
        self.assertEqual(("green", 3), (proof["verdict"], proof["k"]))
        self.assertEqual({COUNT_ID: ["passed"] * 3, HEALTH_ID: ["passed"] * 3},
                         {test["id"]: test["runs"] for test in proof["tests"]})
        self.assertEqual({"tdd_red", "tdd_freeze", "tdd_green"}, self.verified())

    def test_green_runs_the_tests_3_times_when_the_profile_declares_no_k(self):
        self.frozen()
        self.commit("code du ticket", {APP: self.green_app()})

        self.ok("green", profile=self.descriptor(k=None))

        _, proof = self.piece("tdd_green")
        self.assertEqual(3, proof["k"])
        self.assertEqual({COUNT_ID: ["passed"] * 3, HEALTH_ID: ["passed"] * 3},
                         {test["id"]: test["runs"] for test in proof["tests"]})

    def test_green_runs_the_tests_as_many_times_as_the_k_the_profile_declares(self):
        self.frozen()
        self.commit("code du ticket", {APP: self.green_app()})

        self.ok("green", profile=self.descriptor(k=2))

        _, proof = self.piece("tdd_green")
        self.assertEqual(2, proof["k"])
        self.assertEqual({COUNT_ID: ["passed"] * 2, HEALTH_ID: ["passed"] * 2},
                         {test["id"]: test["runs"] for test in proof["tests"]})
        self.assertEqual({("default", "black_box")}, {(test["seam"], test["seam_mode"]) for test in proof["tests"]})

    def test_green_refused_without_a_freeze(self):
        self.commit_tests()
        self.red()

        self.assertIn("gel", self.refused("green"))

    def test_green_refuses_a_frozen_test_that_was_modified(self):
        self.frozen()
        self.commit("code et test affaibli", {APP: self.green_app(), HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})

        error = self.refused("green")

        self.assertIn(f"fichier gelé modifié : {HEALTH_FILE}", error)
        self.assertNotIn(COUNT_FILE, error)

    def test_green_refuses_a_frozen_test_that_was_deleted(self):
        self.frozen()
        self.commit("code sans le test", {APP: self.green_app()}, remove=[HEALTH_FILE])

        self.assertIn(f"fichier gelé supprimé ou déplacé : {HEALTH_FILE}", self.refused("green"))

    def test_green_refuses_a_frozen_test_that_was_set_aside(self):
        self.frozen()
        self.commit("code", {APP: self.green_app()})
        self.git("mv", HEALTH_FILE, f"{TESTS}/attente_health.py")
        self.commit("test mis à l'écart")

        self.assertIn(f"fichier gelé supprimé ou déplacé : {HEALTH_FILE}", self.refused("green"))

    def test_green_refuses_a_criterion_test_left_out_of_the_table(self):
        self.frozen()
        self.commit("code et table réduite", {APP: self.green_app(), TABLE: self.table({"1": [COUNT_ID], "2": [COUNT_ID]})})

        self.assertIn(f"fichier gelé modifié : {TABLE}", self.refused("green"))

    def test_green_refuses_a_frozen_harness_file_that_was_modified(self):
        self.frozen()
        harness = f"{TESTS}/harness.py"
        self.commit("code et harnais", {APP: self.green_app(),
                                        harness: (self.repo / harness).read_text() + "\n# tout passe\n"})

        self.assertIn(f"fichier gelé modifié : {harness}", self.refused("green"))

    def test_green_refuses_a_registry_that_was_altered(self):
        """The fingerprints are compared with the registry the freeze sealed:
        rewriting the registry does not make a modified test acceptable."""
        self.frozen()
        self.commit("code et test affaibli", {APP: self.green_app(), HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})
        registry = self.store / SPEC / SLICE / "tdd_freeze.json"
        record = json.loads(registry.read_text())
        fingerprints = json.loads(record["output"])
        fingerprints["files"][HEALTH_FILE] = sha256_of(self.repo / HEALTH_FILE)
        record["output"] = json.dumps(fingerprints)
        registry.write_text(json.dumps(record))

        error = self.refused("green")

        self.assertIn("tdd_freeze", error)
        self.assertIn("empreinte", error)

    def test_green_refuses_a_test_that_still_fails(self):
        self.frozen()
        self.commit("code partiel", {APP: self.green_app().replace('"dataset": self.dataset.get("state")', '"dataset": None')})

        error = self.refused("green")

        self.assertIn(f"test en échec : {HEALTH_ID}", error)
        self.assertNotIn(COUNT_ID, error)

    def test_green_fails_on_a_mixed_result_and_names_the_unstable_test(self):
        """The health probe names the dataset on every other request only."""
        self.frozen()
        flaky = self.green_app().replace(
            "    dataset: dict = {}\n", "    dataset: dict = {}\n    hits: list = []\n",
        ).replace(
            '{"status": "ok", "dataset": self.dataset.get("state")}',
            '{"status": "ok", "dataset": self.dataset.get("state") if len(self.hits) % 2 else None}',
        ).replace('        if self.path == "/health":\n', '        if self.path == "/health":\n            self.hits.append(1)\n')
        self.commit("code instable", {APP: flaky})

        error = self.refused("green")

        self.assertIn(f"test instable : {HEALTH_ID}", error)
        self.assertNotIn(COUNT_ID, error)

    # --- amendment ----------------------------------------------------------

    AMENDED_HEALTH_TEST = HEALTH_TEST.replace('"content", body.get("dataset")', '"content", body.get("dataset_name")')

    def amended_app(self):
        return self.green_app().replace('"dataset": self.dataset', '"dataset_name": self.dataset')

    def test_first_amendment_demands_a_new_red_refreezes_and_records_the_deviation_with_its_diff(self):
        self.frozen()
        head = self.commit("code et test corrigé", {APP: self.amended_app(), HEALTH_FILE: self.AMENDED_HEALTH_TEST})

        answer = self.ok("amend", SLICE, "--reason", "le champ s'appelle dataset_name dans la Spec")

        self.assertEqual(("amend", head), (answer["step"], answer["commit"]))
        state = self.ticket_state()
        self.assertEqual(head, state["tdd"]["amendment"]["commit"])
        self.assertEqual("le champ s'appelle dataset_name dans la Spec", state["tdd"]["amendment"]["reason"])
        self.assertEqual((head, self.base), (state["tdd"]["red"]["commit"], state["tdd"]["red"]["base"]))
        self.assertEqual(head, state["tdd"]["freeze"]["commit"])
        record, proof = self.piece("tdd_amendment")
        self.assertIn("le champ s'appelle dataset_name dans la Spec", record["command"])
        self.assertEqual("red", proof["verdict"])
        self.assertIn('-        self.assertEqual("content", body.get("dataset"))', proof["amendment"]["diff"])
        self.assertIn('+        self.assertEqual("content", body.get("dataset_name"))', proof["amendment"]["diff"])
        self.assertNotIn("fixture-count", proof["amendment"]["diff"])
        _, frozen = self.piece("tdd_freeze")
        self.assertEqual(sha256_of(self.repo / HEALTH_FILE), frozen["files"][HEALTH_FILE])
        self.ok("green")

    def test_second_amendment_on_the_same_ticket_is_refused_and_stops_the_ticket(self):
        self.frozen()
        self.commit("code et test corrigé", {APP: self.amended_app(), HEALTH_FILE: self.AMENDED_HEALTH_TEST})
        self.ok("amend", SLICE, "--reason", "le champ s'appelle dataset_name dans la Spec")
        self.commit("second changement de test", {COUNT_FILE: COUNT_TEST.replace(">3<", "> 3 <")})
        store_before = self.store_files()
        before = self.ticket_state()["tdd"]

        proc = self.run_tool("amend", SLICE, "--reason", "autre erreur de test")

        self.assertEqual(EXIT_STOPPED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("un seul amendement par ticket", json.loads(proc.stdout)["error"])
        state = self.ticket_state()
        self.assertEqual(before, state["tdd"])
        self.assertEqual("amendment_exhausted", state["stop"]["reason"])
        self.assertEqual(store_before, self.store_files())

    def test_amendment_refused_without_a_reason(self):
        self.frozen()
        self.commit("code et test corrigé", {APP: self.amended_app(), HEALTH_FILE: self.AMENDED_HEALTH_TEST})

        self.assertIn("raison", self.refused("amend", SLICE, "--reason", "  "))

    def test_amendment_refused_when_the_amended_test_is_not_red_at_the_start_commit(self):
        self.frozen()
        self.commit("code et test affaibli", {APP: self.green_app(), HEALTH_FILE: HEALTH_TEST_ALREADY_GREEN})

        error = self.refused("amend", SLICE, "--reason", "test trop strict")

        self.assertIn(HEALTH_ID, error)
        self.assertIn("vert", error)

    def test_amendment_refused_when_no_frozen_file_changed(self):
        self.frozen()
        self.commit("code", {APP: self.green_app()})

        self.assertIn("aucun fichier gelé", self.refused("amend", SLICE, "--reason", "rien"))

    def test_amendment_refused_before_the_freeze(self):
        self.commit_tests()
        self.red()

        self.assertIn("gel", self.refused("amend", SLICE, "--reason", "trop tôt"))

    # --- prefactoring -------------------------------------------------------

    def refactored_app(self):
        return self.base_app.replace("items_html", "rendered_items")

    def test_prefactoring_runs_the_regression_command_before_and_after_and_demands_no_red_step(self):
        head = self.commit("rendu rangé", {
            APP: self.refactored_app(),
            f"{TESTS}/test_caracterisation.py": "import unittest\n",
        })

        answer = self.ok("prefactoring", PREFACTORING, "--base", self.base)

        self.assertEqual(("prefactoring", head), (answer["step"], answer["commit"]))
        state = self.ticket_state(PREFACTORING)
        self.assertEqual((head, self.base), (state["tdd"]["prefactoring"]["commit"], state["tdd"]["prefactoring"]["base"]))
        self.assertNotIn("red", state["tdd"])
        _, proof = self.piece("tdd_prefactoring", PREFACTORING)
        self.assertEqual("unchanged", proof["verdict"])
        self.assertEqual([(self.base, 0), (head, 0)],
                         [(run["commit"], run["exit_code"]) for run in proof["regression"]])

    def test_prefactoring_refuses_an_existing_test_that_was_modified(self):
        conftest = f"{TESTS}/conftest.py"
        self.commit("rendu rangé", {APP: self.refactored_app(), conftest: "# vidé\n"})

        error = self.refused("prefactoring", PREFACTORING, "--base", self.base)

        self.assertIn(f"test existant modifié : {conftest}", error)

    def test_prefactoring_refuses_a_change_that_breaks_the_regression_command(self):
        self.commit("ancre renommée", {APP: self.base_app.replace("fixture-items", "fixture-list")})

        error = self.refused("prefactoring", PREFACTORING, "--base", self.base)

        self.assertIn("commande de régression", error)
        self.assertIn("après", error)

    # A project whose regression command has nothing to run at the start
    # commit: only the frozen harness sits in its test perimeter.

    def start_without_tests(self):
        self.characterization = (self.repo / REGRESSION_FILE).read_text()
        return self.commit("départ sans test", remove=[REGRESSION_FILE])

    def test_prefactoring_refuses_to_start_when_no_test_runs_at_the_start_commit(self):
        start = self.start_without_tests()
        self.commit("rendu rangé", {APP: self.refactored_app()})

        error = self.refused("prefactoring", PREFACTORING, "--base", start)

        self.assertIn("tests de caractérisation", error)
        self.assertNotIn("prefactoring", self.ticket_state(PREFACTORING).get("tdd", {}))

    def test_prefactoring_refuses_characterization_tests_committed_with_the_change(self):
        start = self.start_without_tests()
        self.commit("rendu rangé et tests", {APP: self.refactored_app(), REGRESSION_FILE: self.characterization})

        error = self.refused("prefactoring", PREFACTORING, "--base", start)

        self.assertIn("tests de caractérisation", error)

    def test_prefactoring_accepted_once_a_commit_adds_only_characterization_tests(self):
        start = self.start_without_tests()
        tests = self.commit("tests de caractérisation", {REGRESSION_FILE: self.characterization})

        answer = self.ok("prefactoring", PREFACTORING, "--base", start)

        self.assertEqual(("prefactoring", tests), (answer["step"], answer["commit"]))
        _, proof = self.piece("tdd_prefactoring", PREFACTORING)
        self.assertEqual((start, tests), (proof["base"], proof["characterization"]))
        self.assertEqual([(tests, 0), (tests, 0)], [(run["commit"], run["exit_code"]) for run in proof["regression"]])

    def test_prefactoring_runs_the_characterization_tests_before_and_after_the_change(self):
        start = self.start_without_tests()
        tests = self.commit("tests de caractérisation", {REGRESSION_FILE: self.characterization})
        head = self.commit("rendu rangé", {APP: self.refactored_app()})

        self.ok("prefactoring", PREFACTORING, "--base", start)

        _, proof = self.piece("tdd_prefactoring", PREFACTORING)
        self.assertEqual([(tests, 0), (head, 0)], [(run["commit"], run["exit_code"]) for run in proof["regression"]])

    def test_prefactoring_refuses_a_characterization_test_touched_by_the_change(self):
        start = self.start_without_tests()
        self.commit("tests de caractérisation", {REGRESSION_FILE: self.characterization})
        self.commit("rendu rangé", {APP: self.refactored_app(), REGRESSION_FILE: self.characterization + "# retouché\n"})

        error = self.refused("prefactoring", PREFACTORING, "--base", start)

        self.assertIn(f"test existant modifié : {REGRESSION_FILE}", error)

    def test_prefactoring_refuses_characterization_tests_that_fail_at_the_start_commit(self):
        start = self.start_without_tests()
        self.commit("tests de caractérisation", {REGRESSION_FILE: self.characterization.replace("fixture-items", "fixture-list")})

        error = self.refused("prefactoring", PREFACTORING, "--base", start)

        self.assertIn("commande de régression", error)
        self.assertIn("avant", error)

    def test_red_step_refused_on_a_prefactoring(self):
        self.commit_tests()

        self.assertIn("prefactoring", self.red_refused(PREFACTORING))

    def test_prefactoring_regime_refused_on_a_slice(self):
        self.commit("rendu rangé", {APP: self.refactored_app()})

        self.assertIn("vertical_slice", self.refused("prefactoring", SLICE, "--base", self.base))

    # --- opt-in and command line --------------------------------------------

    def test_a_convoy_without_the_mark_is_not_touched(self):
        self.commit_tests()

        message = self.refused("red", PLAIN_TICKET, "--base", self.base, "--table", TABLE,
                               convoy=PLAIN_CONVOY, status=EXIT_NOT_NEW_FLOW)

        self.assertIn("pas un convoi du nouveau flux", message)

    def test_red_refused_when_the_work_tree_differs_from_its_commit(self):
        self.commit_tests()
        (self.repo / COUNT_FILE).write_text(COUNT_TEST + "\n# pas commité\n")

        self.assertIn("non commitées", self.red_refused())

    def test_red_refused_when_the_profile_test_command_writes_no_report(self):
        self.commit_tests()

        error = self.red_refused(profile=self.descriptor(test_command="python3 {test} -q"))

        self.assertIn("{report}", error)


if __name__ == "__main__":
    unittest.main()
