#!/usr/bin/env python3
"""bin/acceptance-session and the acceptance records of bin/convoy-state
(T28, Spec §11), on a fake tracker state and on the launchable product of
the delivery fixture: one test per pass and per refusal, each refusal
re-reading the tracker, the Evidence Packs and the session records to
prove nothing was written. The product is really launched, on loopback."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import socket
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "acceptance-session"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


packs = load("evidence-pack-test.py")
gate = packs.gate
CONVOY, PLAIN_CONVOY, INTEGRATION, SLICE = packs.CONVOY, packs.PLAIN_CONVOY, packs.INTEGRATION, packs.SLICE
EXIT_REFUSED, EXIT_NOT_NEW_FLOW = 1, 4
ISSUES = ["relancer", "planification", "abandon"]
STOP_DETAIL = "2 tour(s) de réparation consommé(s) (borne : 2), et la fin de Spec est encore refusée"


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def answers(address):
    try:
        with urllib.request.urlopen(address + "/health", timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


class AcceptanceSessionTest(packs.EvidencePackTest):
    def setUp(self):
        super().setUp()
        self.sessions = self.tmp / "sessions"
        self.env["ACCEPTANCE_SESSION_STATE_DIR"] = str(self.sessions)
        self.addCleanup(self.close_quietly)

    # --- harness ------------------------------------------------------------

    def close_quietly(self):
        if TOOL.is_file():
            self.run_cmd(TOOL, "close", CONVOY)

    def acc(self, command, *args, convoy=CONVOY, env=None):
        proc = self.run_cmd(TOOL, command, convoy, *args, env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def open_session(self, *args):
        return self.acc("open", "--repo", self.repo, "--profile", self.profile, *args)

    def session_opened(self):
        status, answer = self.open_session()
        self.assertEqual(0, status, answer)
        return answer

    def session_files(self):
        return {str(path.relative_to(self.sessions)): path.read_bytes()
                for path in sorted(self.sessions.rglob("*")) if path.is_file()} if self.sessions.is_dir() else {}

    def everything(self):
        return (super().everything(), self.session_files())

    def acceptance(self):
        return self.show()["convoy"]["acceptance"]

    def delivered_outcome(self):
        """The fixture whose Outcome is Delivered. Returns its commit."""
        def build():
            commit = self.ready()
            self.generate()
            status, answer = self.run_gate()
            self.assertEqual((0, True), (status, answer["delivered"]), answer)
            return commit
        return self.stage("acceptance-delivered", build)

    def non_conforme(self):
        """The fixture whose rounds of the end are stopped and whose
        « non conforme » request reached the operator. Returns the commit
        of its Evidence Pack."""
        def build():
            commit = self.verified()
            self.edit(CONVOY, **{"gc.flow.end_stop": json.dumps({
                "reason": "end_rounds_exhausted", "detail": STOP_DETAIL, "commit": commit,
                "source": "outcome_evaluation", "rounds": 2, "at": "2026-10-08T10:00:00Z"})})
            pack = self.generate()
            self.door("benjamin", CONVOY, json.dumps({
                "quoi": "Demande « non conforme » — tours de réparation épuisés", "pourquoi": STOP_DETAIL,
                "que_faire": [{"option": "Relancer un tour de réparation", "consequence": "La fin de Spec est rejouée."},
                              {"option": "Retourner à la planification", "consequence": "Le convoi reste arrêté."},
                              {"option": "Abandonner", "consequence": "Rien n'est fusionné."}],
                "langue": "fr", "bloquant": True, "lien": pack["page"]}, ensure_ascii=False))
            self.state("end-stop-raised", CONVOY, "--bead", CONVOY)
            return pack["commit"]
        return self.stage("acceptance-non-conforme", build)

    def broken_profile(self):
        """The profile of the project, whose recipe exits at once."""
        profile = json.loads(Path(self.profile).read_text(encoding="utf-8"))
        profile["launch"]["recipe"] = ["{python}", "-c", "import sys; sys.exit(3)"]
        path = self.tmp / "broken-descriptor.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        return path

    def profile_without_dataset(self):
        """The profile of the project with no dataset declared; its recipe
        names the file of one, so that it would start if it were launched."""
        profile = json.loads(Path(self.profile).read_text(encoding="utf-8"))
        launch = profile["launch"]
        content = launch["datasets"]["content"]
        launch["recipe"] = [content if token == "{dataset}" else token for token in launch["recipe"]]
        launch["datasets"] = {}
        launch.pop("screens", None)
        path = self.tmp / "descriptor-without-dataset.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        return path

    def refused(self, command, *args, status=EXIT_REFUSED):
        before = self.everything()
        code, answer = self.acc(command, *args)
        self.assertEqual(status, code, answer)
        self.assertEqual(before, self.everything())
        return answer

    # --- the Acceptance Request noted on the convoy (bin/convoy-state) -----------------------

    def test_acceptance_request_is_noted_once_on_the_delivered_outcome_with_the_page_of_its_pack(self):
        commit = self.delivered_outcome()
        pack = self.show()["convoy"]["evidence_pack"]
        self.assertIsNone(self.acceptance())

        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)

        record = self.acceptance()
        self.assertEqual((commit, pack["digest"], CONVOY, str(Path(pack["path"]) / "index.html")),
                         (record["commit"], record["pack"], record["request"]["bead"], record["request"]["page"]))
        # The same request again writes nothing.
        before = self.everything()
        self.assertEqual({}, self.state("acceptance-requested", CONVOY, "--bead", CONVOY)["written"])
        self.assertEqual(before, self.everything())
        self.assertFalse(self.show()["convoy"]["unruled"])

    def test_acceptance_request_is_refused_on_a_convoy_that_is_not_delivered(self):
        self.ready()
        before = self.everything()

        proc = self.run_cmd(gate.STATE_TOOL, "acceptance-requested", CONVOY, "--bead", CONVOY)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("Delivered", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.everything())

    def test_acceptance_request_noted_on_another_bead_than_the_first_is_refused(self):
        self.delivered_outcome()
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        before = self.everything()

        proc = self.run_cmd(gate.STATE_TOOL, "acceptance-requested", CONVOY, "--bead", SLICE)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.everything())

    def test_recording_delivered_again_keeps_the_acceptance_request(self):
        self.delivered_outcome()
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        before = self.everything()

        status, answer = self.run_gate()

        self.assertEqual((0, True), (status, answer["delivered"]))
        self.assertEqual(before, self.everything())

    # --- opening the session -----------------------------------------------------------------

    def test_open_launches_the_product_at_the_commit_of_the_pack_and_returns_its_address(self):
        commit = self.delivered_outcome()
        pack = self.show()["convoy"]["evidence_pack"]
        tracker = self.snapshot()

        answer = self.session_opened()

        self.assertEqual((True, "acceptance", commit, pack["digest"]),
                         (answer["ok"], answer["kind"], answer["commit"], answer["digest"]))
        self.assertEqual(str(Path(pack["path"]) / "index.html"), answer["page"])
        self.assertEqual(["content", "empty"], [product["dataset"] for product in answer["products"]])
        self.assertEqual(answer["products"][0]["address"], answer["address"])
        for product in answer["products"]:
            self.assertTrue(answers(product["address"]), product)
        # The product runs from a copy of the commit of the pack, not from the repository.
        for record in self.sessions.rglob("*.json"):
            launch = json.loads(record.read_text())
            if "worktree" in launch:
                self.assertEqual(commit, self.git("rev-parse", "HEAD", cwd=launch["worktree"]))
        # Opening judges nothing: the tracker, the store and the branches are as they were.
        self.assertEqual(tracker, self.snapshot())
        self.assertNotIn("accept", json.dumps(answer.get("issues", [])).lower())

    def test_close_stops_the_product_and_frees_its_port(self):
        self.delivered_outcome()
        answer = self.session_opened()
        ports = [int(product["address"].rsplit(":", 1)[1]) for product in answer["products"]]

        status, closed = self.acc("close")

        self.assertEqual((0, True), (status, closed["closed"]), closed)
        self.assertEqual(sorted(ports), sorted(entry["port"] for entry in closed["stopped"]))
        for product in answer["products"]:
            self.assertFalse(answers(product["address"]), product)
        for port in ports:
            self.assertTrue(port_is_free(port), port)
        self.assertEqual({}, self.session_files())
        # A session closed can be opened again.
        self.assertTrue(answers(self.session_opened()["address"]))

    def test_close_without_an_open_session_is_refused(self):
        self.delivered_outcome()

        answer = self.refused("close")

        self.assertIn("aucune Acceptance Session", answer["error"])

    def test_open_while_a_session_is_open_is_refused_and_leaves_the_product_running(self):
        self.delivered_outcome()
        first = self.session_opened()

        answer = self.refused("open", "--repo", self.repo, "--profile", self.profile)

        self.assertIn("déjà ouverte", answer["error"])
        self.assertTrue(answers(first["address"]))

    def test_a_trial_launches_one_product_and_answers_it_again_while_the_session_is_open(self):
        commit = self.delivered_outcome()

        status, first = self.open_session("--trial")

        self.assertEqual(0, status, first)
        self.assertEqual(commit, first["commit"])
        self.assertEqual(["content"], [product["dataset"] for product in first["products"]])
        self.assertTrue(answers(first["address"]))
        status, again = self.open_session("--trial")
        self.assertEqual(0, status, again)
        self.assertEqual(first["address"], again["address"])
        self.assertTrue(answers(again["address"]))

    def test_open_on_an_outdated_pack_is_refused_and_launches_nothing(self):
        self.delivered_outcome()
        self.note(INTEGRATION)

        answer = self.refused("open", "--repo", self.repo, "--profile", self.profile)

        self.assertIn("périmé", answer["error"])
        self.assertNotIn("address", answer)

    def test_open_on_a_convoy_neither_delivered_nor_stopped_is_refused(self):
        self.ready()
        self.generate()

        answer = self.refused("open", "--repo", self.repo, "--profile", self.profile)

        self.assertIn("Delivered", answer["error"])

    def test_open_on_a_convoy_without_the_mark_is_not_touched(self):
        self.delivered_outcome()
        before = self.everything()

        status, answer = self.acc("open", "--repo", self.repo, "--profile", self.profile, convoy=PLAIN_CONVOY)
        self.assertEqual(EXIT_NOT_NEW_FLOW, status, answer)
        self.assertEqual(before, self.everything())

    def test_open_on_a_project_without_a_named_dataset_is_refused_and_launches_nothing(self):
        """T38 (af-8o4jcp): refused, not an outage of the product."""
        self.delivered_outcome()

        answer = self.refused("open", "--repo", self.repo, "--profile", self.profile_without_dataset())

        self.assertIn("aucun jeu de données", answer["error"])
        self.assertNotIn("outage", answer)
        self.assertNotIn("address", answer)
        self.assertEqual({}, self.session_files())

    # --- a product that does not start -------------------------------------------------------

    def test_open_on_a_product_that_does_not_start_says_so_opens_no_judgment_and_records_the_outage(self):
        commit = self.delivered_outcome()

        status, answer = self.acc("open", "--repo", self.repo, "--profile", self.broken_profile())

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual((False, True), (answer["ok"], answer["outage"]))
        self.assertIn("ne démarre pas", answer["error"])
        self.assertIn("repair", answer["error"])
        self.assertNotIn("address", answer)
        self.assertEqual({}, self.session_files())
        outage = self.acceptance()
        self.assertEqual(commit, outage["commit"])
        self.assertTrue(outage["panne"]["detail"])
        self.assertNotIn("ticket", outage["panne"])
        # The Outcome is still Delivered: an outage is no judgment.
        self.assertEqual(commit, self.outcome_delivered()["commit"])
        self.assertFalse(self.show()["convoy"]["unruled"])

    def test_open_is_refused_while_the_outage_of_this_commit_waits_for_its_repair(self):
        self.delivered_outcome()
        self.acc("open", "--repo", self.repo, "--profile", self.broken_profile())

        answer = self.refused("open", "--repo", self.repo, "--profile", self.profile)

        self.assertIn("ne démarre pas", answer["error"])

    def test_outage_keeps_the_acceptance_request_and_takes_one_repair_of_the_convoy(self):
        commit = self.delivered_outcome()
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        self.state("acceptance-launch-failed", CONVOY, "--commit", commit, "--detail", "le produit sort avec le code 3")
        self.assertEqual(CONVOY, self.acceptance()["request"]["bead"])
        before = self.everything()

        # A ticket that is not a repair is refused.
        proc = self.run_cmd(gate.STATE_TOOL, "set-acceptance-repair", CONVOY, "--ticket", SLICE)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.everything())

    def test_outage_is_refused_at_a_commit_that_is_not_the_one_of_the_dossier(self):
        self.delivered_outcome()
        before = self.everything()

        proc = self.run_cmd(gate.STATE_TOOL, "acceptance-launch-failed", CONVOY, "--commit", "0" * 40,
                            "--detail", "le produit sort avec le code 3")

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.everything())

    # --- the « non conforme » request: same session, three issues ----------------------------

    def test_open_on_a_non_conforme_request_launches_the_product_and_offers_three_issues_without_accepted(self):
        commit = self.non_conforme()

        answer = self.session_opened()

        self.assertEqual(("non_conforme", commit), (answer["kind"], answer["commit"]))
        self.assertTrue(answers(answer["address"]))
        self.assertEqual(ISSUES, [issue["response"] for issue in answer["issues"]])

    def test_record_refuses_accepted_on_a_non_conforme_request_and_writes_nothing(self):
        self.non_conforme()

        for word in ("accepte", "accepté"):
            answer = self.refused("record", "--repo", self.repo, "--response", word)
            self.assertIn("« accepté »", answer["error"])
            self.assertIn("non conforme", answer["error"])
        self.assertNotIn("gc.escalation_response_option", self.metadata(CONVOY))

    def test_record_takes_one_of_the_three_issues_of_a_non_conforme_request_through_the_escalation_door(self):
        self.non_conforme()

        status, answer = self.acc("record", "--repo", self.repo, "--response", "planification", "--actor", "benjamin")

        self.assertEqual((0, True, "planification"), (status, answer["ok"], answer["response"]), answer)
        metadata = self.metadata(CONVOY)
        self.assertEqual(("b", "Retourner à la planification"), (metadata["gc.escalation_response_option"], answer["option"]))
        self.assertEqual("benjamin", metadata["gc.escalation_response_actor"])
        # The stop stays: acting on the answer is not this command's.
        self.assertIn("request", self.show()["convoy"]["end_stop"])

    def test_record_is_refused_on_a_delivered_outcome(self):
        self.delivered_outcome()

        answer = self.refused("record", "--repo", self.repo, "--response", "relancer")

        self.assertIn("non conforme", answer["error"])


# The suite of the Evidence Pack is the harness here, not tests to run again.
for inherited in dir(packs.EvidencePackTest):
    if inherited.startswith("test_") and inherited not in vars(AcceptanceSessionTest):
        setattr(AcceptanceSessionTest, inherited, None)


if __name__ == "__main__":
    unittest.main()
