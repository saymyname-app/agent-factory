#!/usr/bin/env python3
# ci: every-run — it asks Git for the state of the whole Factory repository
# (the tool must write nothing there), which reads docs/ and the Cockpit: it
# cannot be left out of a run that changes only those (bin/ci-run-tests).
"""bin/evidence-capture on a fake tracker state (T09, af-pvcg6t; Spec
af-wf4w5r §9, Testing Decisions seam 2): one test per pass and per refusal,
each refusal re-reading the tracker and the evidence store to prove nothing
was written. Only command lines are exercised. The product is the Delivery
Fixture City, launched for real by bin/project-launch; the browser is a fake
that fetches the page it is given (the real Chromium is driven by
tests/evidence-capture-real-browser-test.sh, local-only)."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "evidence-capture"
STATE_TOOL = ROOT / "bin" / "convoy-state"
LAUNCH_TOOL = ROOT / "bin" / "project-launch"
DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_BROWSER = ROOT / "tests" / "fixtures" / "evidence-capture" / "browser"

CONVOY, SPEC, T1, T2 = "fx-convoy", "fx-spec", "fx-t1", "fx-t2"
OTHER_CONVOY, OTHER_SPEC, U1 = "fx-other", "fx-spec2", "fx-u1"
PLAIN_CONVOY, P1 = "fx-plain", "fx-p1"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EvidenceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="evidence-capture-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.browser_log = self.tmp / "browser.log"
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "EVIDENCE_STORE_DIR": str(self.store),
            "EVIDENCE_CAPTURE_BROWSER": str(FAKE_BROWSER),
            "EVIDENCE_FAKE_BROWSER_LOG": str(self.browser_log),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.seed()
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "README").write_text("produit synthétique\n")
        self.git("add", "README")
        self.git("commit", "-q", "-m", "base")
        self.head = self.git("rev-parse", "HEAD")

    # --- harness ------------------------------------------------------------

    def seed(self):
        """Two marked convoys of two Specs, and one convoy without the mark."""
        def convoy(spec, tickets):
            return {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                    "metadata": {"gc.spec_id": spec}, "tracks": tickets}

        def ticket():
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "metadata": {"gc.ticket_kind": "prefactoring"}}

        beads = {
            CONVOY: convoy(SPEC, [T1, T2]), T1: ticket(), T2: ticket(),
            OTHER_CONVOY: convoy(OTHER_SPEC, [U1]), U1: ticket(),
            PLAIN_CONVOY: convoy("fx-spec3", [P1]), P1: ticket(),
        }
        self.tracker.write_text(json.dumps({"beads": beads}))
        for marked in (CONVOY, OTHER_CONVOY):
            proc = subprocess.run((str(STATE_TOOL), "mark", marked), env=self.env, text=True, capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def run_tool(self, *args, env=None):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), env=env or self.env, text=True, capture_output=True,
            cwd=self.tmp,
        )

    def ok(self, *args, env=None):
        proc = self.run_tool(*args, env=env)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def refused(self, *args, env=None, status=EXIT_REFUSED):
        """A refusal: the expected exit status, one JSON answer, and neither
        the tracker nor the evidence store changed."""
        tracker_before, store_before = self.tracker.read_text(), self.store_files()
        proc = self.run_tool(*args, env=env)
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertEqual(tracker_before, self.tracker.read_text(), "un refus a écrit dans le tracker")
        self.assertEqual(store_before, self.store_files(), "un refus a écrit dans le magasin de preuves")
        return answer.get("error") or answer.get("message")

    def store_files(self):
        """Every piece file of the store with its fingerprint (the store's
        own seal key is not a piece)."""
        if not self.store.exists():
            return {}
        return {
            str(path.relative_to(self.store)): sha256_of(path)
            for path in sorted(self.store.rglob("*")) if path.is_file() and path.name != ".seal-key"
        }

    def tracked_evidence(self, convoy=CONVOY, ticket=T1):
        proc = subprocess.run((str(STATE_TOOL), "show", convoy), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        shown = json.loads(proc.stdout)
        return next(t for t in shown["tickets"] if t["id"] == ticket)["evidence"]

    def record(self, piece, spec=SPEC, ticket=T1):
        return json.loads((self.store / spec / ticket / f"{piece}.json").read_text())

    def capture_command(self, piece="demo.commande", convoy=CONVOY, ticket=T1, command=("sh", "-c", "echo bonjour")):
        return self.ok("command", convoy, ticket, "--piece", piece, "--repo", self.repo, "--", *command)

    def launch(self):
        """The Delivery Fixture City, launched by the launcher of the flow."""
        state_file = self.tmp / f"launch-{uuid.uuid4().hex}.json"
        proc = subprocess.run(
            (str(LAUNCH_TOOL), "start", str(DESCRIPTOR), "--dataset", "content", "--state-file", str(state_file)),
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.addCleanup(self.stop, state_file)
        return state_file, json.loads(state_file.read_text())

    def stop(self, state_file):
        if state_file.exists():
            subprocess.run((str(LAUNCH_TOOL), "stop", "--state-file", str(state_file)),
                           cwd=ROOT, text=True, capture_output=True, check=True)

    # --- command mode -------------------------------------------------------

    def test_command_piece_holds_command_real_output_exit_code_time_and_commit(self):
        answer = self.ok(
            "command", CONVOY, T1, "--piece", "demo.commande", "--repo", self.repo,
            "--", "sh", "-c", "echo sortie; echo erreur >&2; exit 3",
        )

        path = self.store / SPEC / T1 / "demo.commande.json"
        self.assertEqual(str(path), answer["path"])
        record = self.record("demo.commande")
        self.assertEqual("command", record["kind"])
        self.assertEqual(["sh", "-c", "echo sortie; echo erreur >&2; exit 3"], record["command"])
        self.assertEqual("sortie\nerreur\n", record["output"])
        self.assertEqual(3, record["exit_code"])
        self.assertEqual(self.head, record["commit"])
        self.assertRegex(record["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual((SPEC, CONVOY, T1, "demo.commande"),
                         (record["spec"], record["convoy"], record["ticket"], record["piece"]))

    def test_command_piece_fingerprint_is_written_on_the_ticket_in_the_tracker(self):
        self.capture_command()

        evidence = self.tracked_evidence()
        self.assertEqual(["demo.commande"], sorted(evidence))
        self.assertEqual(sha256_of(self.store / SPEC / T1 / "demo.commande.json"), evidence["demo.commande"]["digest"])
        self.assertEqual(self.head, evidence["demo.commande"]["commit"])
        self.assertEqual({}, self.tracked_evidence(ticket=T2))

    def test_recorded_output_comes_from_the_execution(self):
        """The output is whatever the command printed when the tool ran it:
        here a value that does not exist before the run."""
        witness = self.tmp / "witness"
        nonce = uuid.uuid4().hex
        self.capture_command(command=("sh", "-c", f"echo {nonce} > {witness}; cat {witness}"))

        self.assertEqual(nonce + "\n", self.record("demo.commande")["output"])
        self.assertEqual(nonce + "\n", witness.read_text())

    def test_caller_cannot_supply_the_output(self):
        """No option and no input channel carries an output: one is refused
        and the other is not read."""
        proc = self.run_tool("command", CONVOY, T1, "--piece", "p", "--repo", self.repo,
                             "--output", "tout va bien", "--", "true")
        self.assertNotEqual(0, proc.returncode)
        self.assertEqual({}, self.store_files())
        self.assertEqual({}, self.tracked_evidence())

        proc = subprocess.run(
            (str(TOOL), "command", CONVOY, T1, "--piece", "p", "--repo", str(self.repo), "--", "sh", "-c", "cat; echo fin"),
            env=self.env, input="sortie fournie par l'appelant\n", text=True, capture_output=True, cwd=self.tmp,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("fin\n", self.record("p")["output"])

    def test_expected_exit_code_files_the_piece_when_the_command_exits_with_it(self):
        self.ok("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--expect-exit", "3",
                "--", "sh", "-c", "echo trois; exit 3")

        self.assertEqual((3, "trois\n"), (self.record("p")["exit_code"], self.record("p")["output"]))

    def test_another_exit_code_than_the_expected_one_is_refused_with_code_and_output(self):
        tracker_before, store_before = self.tracker.read_text(), self.store_files()

        proc = self.run_tool("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--expect-exit", "0",
                             "--", "sh", "-c", "echo pourquoi; exit 7")

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertIn("code de sortie 7", answer["error"])
        self.assertEqual((7, "pourquoi\n"), (answer["exit_code"], answer["output"]))
        self.assertEqual(tracker_before, self.tracker.read_text())
        self.assertEqual(store_before, self.store_files())

    def test_malformed_expected_exit_code_is_refused_before_running(self):
        marker = self.tmp / "exécutée"

        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--expect-exit", "zéro",
                             "--", "touch", marker)

        self.assertIn("--expect-exit", error)
        self.assertFalse(marker.exists())

    def test_command_refused_without_a_command_to_run(self):
        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo)
        self.assertIn("commande", error)

    def test_command_refused_when_it_cannot_be_executed(self):
        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo,
                             "--", str(self.tmp / "commande-absente"))
        self.assertIn("commande-absente", error)

    def test_command_refused_when_the_work_tree_differs_from_its_commit(self):
        """A piece is tied to a commit: output produced by uncommitted code
        would be tied to none."""
        (self.repo / "README").write_text("modifié sans commit\n")
        witness = self.tmp / "ran"
        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--", "touch", witness)
        self.assertIn("non commit", error)
        self.assertFalse(witness.exists(), "la commande a été exécutée malgré le refus")

    def test_command_refused_outside_a_repository(self):
        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.tmp / "nulle-part", "--", "true")
        self.assertIn("commit", error)

    def test_piece_name_outside_the_tracker_alphabet_is_refused_before_running(self):
        witness = self.tmp / "ran"
        for name in ("demo-commande", "../evasion", "a/b", ""):
            error = self.refused("command", CONVOY, T1, "--piece", name, "--repo", self.repo, "--", "touch", witness)
            self.assertIn("nom de pièce", error)
        self.assertFalse(witness.exists(), "la commande a été exécutée malgré le refus")

    def test_unmarked_convoy_is_not_touched(self):
        witness = self.tmp / "ran"
        message = self.refused("command", PLAIN_CONVOY, P1, "--piece", "p", "--repo", self.repo,
                               "--", "touch", witness, status=EXIT_NOT_NEW_FLOW)
        self.assertIn("pas un convoi du nouveau flux", message)
        self.assertFalse(witness.exists(), "la commande a été exécutée sur un convoi sans marque")

    def test_ticket_of_another_convoy_is_refused_before_running(self):
        witness = self.tmp / "ran"
        error = self.refused("command", CONVOY, U1, "--piece", "p", "--repo", self.repo, "--", "touch", witness)
        self.assertIn(U1, error)
        self.assertFalse(witness.exists(), "la commande a été exécutée malgré le refus")

    def test_nothing_stays_in_the_store_when_the_tracker_refuses_the_fingerprint(self):
        failing_gc = self.tmp / "gc-refusing-writes"
        failing_gc.write_text(
            "#!/bin/sh\n"
            # A leading `--city DIR` is accepted, as gc does (af-2o6oyl).
            'if [ "$1" = "--city" ]; then shift 2; fi\n'
            'if [ "$1 $2" = "bd update" ]; then echo "tracker indisponible" >&2; exit 1; fi\n'
            f'exec "{FAKE_GC}" "$@"\n'
        )
        failing_gc.chmod(0o755)
        error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--", "true",
                             env={**self.env, "GC_BIN": str(failing_gc)})
        self.assertIn("tracker indisponible", error)

    def test_capturing_a_piece_again_replaces_it(self):
        self.capture_command(command=("echo", "premier"))
        self.capture_command(command=("echo", "second"))

        self.assertEqual("second\n", self.record("demo.commande")["output"])
        self.assertEqual(sha256_of(self.store / SPEC / T1 / "demo.commande.json"),
                         self.tracked_evidence()["demo.commande"]["digest"])
        self.ok("verify", CONVOY, T1)

    def test_command_piece_replacing_a_screenshot_piece_leaves_no_image(self):
        state_file, _ = self.launch()
        self.ok("screenshot", CONVOY, T1, "--piece", "demo", "--launch-state", state_file, "--path", "/")
        self.capture_command(piece="demo")

        self.assertEqual([f"{SPEC}/{T1}/demo.json"], sorted(self.store_files()))
        self.ok("verify", CONVOY, T1)

    # --- screenshot mode ----------------------------------------------------

    def test_screenshot_piece_holds_image_address_time_and_commit_of_the_launched_product(self):
        state_file, launch = self.launch()

        answer = self.ok("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file, "--path", "/")

        record = self.record("demo.page")
        self.assertEqual("screenshot", record["kind"])
        self.assertEqual(launch["address"] + "/", record["address"])
        self.assertEqual(launch["commit"], record["commit"])
        self.assertRegex(record["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        image = self.store / SPEC / T1 / record["image"]
        self.assertEqual(str(image), answer["image"])
        self.assertTrue(image.read_bytes().startswith(PNG_MAGIC))
        self.assertEqual(sha256_of(image), record["image_digest"])
        self.assertEqual([launch["address"] + "/"], self.browser_log.read_text().split())

        evidence = self.tracked_evidence()["demo.page"]
        self.assertEqual(sha256_of(self.store / SPEC / T1 / "demo.page.json"), evidence["digest"])
        self.assertEqual(launch["commit"], evidence["commit"])
        self.ok("verify", CONVOY, T1, "--piece", "demo.page")

    def test_command_on_the_launched_product_records_its_address_and_commit(self):
        state_file, launch = self.launch()

        self.ok("command", CONVOY, T1, "--piece", "demo.sonde", "--launch-state", state_file,
                "--", "python3", "-c",
                f"import urllib.request; print(urllib.request.urlopen('{launch['address']}/health').read().decode())")

        record = self.record("demo.sonde")
        self.assertEqual({"status": "ok"}, json.loads(record["output"]))
        self.assertEqual(launch["address"], record["address"])
        self.assertEqual(launch["commit"], record["commit"])

    def test_screenshot_refused_when_the_product_is_not_running(self):
        state_file, _ = self.launch()
        stopped = self.tmp / "stopped.json"
        shutil.copy(state_file, stopped)
        self.stop(state_file)

        error = self.refused("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", stopped, "--path", "/")
        self.assertIn("ne répond pas", error)
        self.assertFalse(self.browser_log.exists(), "le navigateur a été lancé sur un produit arrêté")

    def test_screenshot_refused_on_an_address_outside_the_launched_product(self):
        state_file, _ = self.launch()
        for path in ("http://example.invalid/", "//example.invalid/", "page"):
            error = self.refused("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file,
                                 "--path", path)
            self.assertIn("--path", error)

    def test_screenshot_refused_without_a_launch_record(self):
        error = self.refused("screenshot", CONVOY, T1, "--piece", "demo.page",
                             "--launch-state", self.tmp / "absent.json", "--path", "/")
        self.assertIn("absent.json", error)

    def test_screenshot_refused_when_the_browser_writes_no_image(self):
        state_file, _ = self.launch()
        for mode in ("no-file", "not-png"):
            error = self.refused("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file,
                                 "--path", "/", env={**self.env, "EVIDENCE_FAKE_BROWSER_MODE": mode})
            self.assertIn("image", error)

    def test_screenshot_refused_without_a_browser(self):
        state_file, _ = self.launch()
        error = self.refused("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file,
                             "--path", "/", env={**self.env, "EVIDENCE_CAPTURE_BROWSER": str(self.tmp / "absent")})
        self.assertIn("navigateur", error)

    # --- comparison mode (T16, af-622nya) --------------------------------------

    def reference(self, body="<!doctype html><title>prototype</title><p>référence</p>"):
        """A reference page served on this host, as bin/prototype-fidelity
        serves a state of the Validated Prototype."""
        root = self.tmp / f"reference-{uuid.uuid4().hex}"
        root.mkdir()
        (root / "state.html").write_text(body)
        port_file = root / "port"
        server = subprocess.Popen(
            ("python3", "-c",
             "import functools, http.server, sys\n"
             "handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=sys.argv[1])\n"
             "server = http.server.HTTPServer(('127.0.0.1', 0), handler)\n"
             "open(sys.argv[2], 'w').write(str(server.server_address[1]))\n"
             "server.serve_forever()\n", str(root), str(port_file)),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(server.wait)
        self.addCleanup(server.kill)
        for _ in range(100):
            if port_file.exists() and port_file.read_text():
                break
            time.sleep(0.05)
        return f"http://127.0.0.1:{port_file.read_text()}/state.html"

    def test_comparison_piece_holds_both_sides_captured_now_and_their_difference(self):
        state_file, launch = self.launch()
        reference = self.reference()

        answer = self.ok("comparison", CONVOY, T1, "--piece", "fidelite.contenu", "--launch-state", state_file,
                         "--path", "/", "--reference-url", reference)

        record = self.record("fidelite.contenu")
        self.assertEqual(("comparison", launch["address"] + "/", reference, launch["commit"]),
                         (record["kind"], record["address"], record["reference"], record["commit"]))
        for field in ("image", "difference"):
            image = self.store / SPEC / T1 / record[field]
            self.assertEqual(str(image), answer[field])
            self.assertTrue(image.read_bytes().startswith(PNG_MAGIC))
            self.assertEqual(sha256_of(image), record[f"{field}_digest"])
        # Both sides were rendered by this capture: nothing stored earlier is compared.
        self.assertEqual(sorted([reference, launch["address"] + "/"]), sorted(self.browser_log.read_text().split()))
        # The two pages differ; the count is recorded and judges nothing.
        self.assertEqual((1, 1), (record["differing_pixels"], record["pixels"]))
        self.assertEqual(sha256_of(self.store / SPEC / T1 / "fidelite.contenu.json"),
                         self.tracked_evidence()["fidelite.contenu"]["digest"])
        self.ok("verify", CONVOY, T1)

    def test_comparison_of_a_page_with_itself_counts_no_differing_pixel(self):
        state_file, launch = self.launch()
        # The reference is the launched product's own page, on this host.
        answer = self.ok("comparison", CONVOY, T1, "--piece", "fidelite.meme", "--launch-state", state_file,
                         "--reference-url", launch["address"] + "/")

        self.assertEqual(0, answer["differing_pixels"])

    def test_comparison_refused_without_a_reference_served_on_this_host(self):
        state_file, _ = self.launch()
        base = ("comparison", CONVOY, T1, "--piece", "fidelite.contenu", "--launch-state", state_file)
        self.assertIn("--reference-url", self.refused(*base))
        self.assertIn("--reference-url", self.refused(*base, "--reference-url", "https://example.invalid/page"))
        self.assertIn("référence", self.refused(*base, "--reference-url", "http://127.0.0.1:9/absente.html"))
        self.assertIn("référence", self.refused(*base, "--reference-url", self.reference().replace("state.html", "absente.html")))
        self.assertFalse(self.browser_log.exists(), "rien ne doit être capturé avant le refus")

    def test_verify_fails_when_the_difference_image_was_replaced(self):
        state_file, _ = self.launch()
        self.ok("comparison", CONVOY, T1, "--piece", "fidelite.contenu", "--launch-state", state_file,
                "--reference-url", self.reference())
        difference = self.store / SPEC / T1 / self.record("fidelite.contenu")["difference"]
        difference.write_bytes(PNG_MAGIC + b"autre image")

        self.assertIn("image", self.refused("verify", CONVOY, T1, "--piece", "fidelite.contenu"))

    def test_screenshot_piece_replacing_a_comparison_piece_leaves_no_difference_image(self):
        state_file, _ = self.launch()
        self.ok("comparison", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file,
                "--reference-url", self.reference())

        self.ok("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file)

        self.assertEqual(["demo.page.json", "demo.page.png"], sorted(p.name for p in (self.store / SPEC / T1).iterdir()))
        self.ok("verify", CONVOY, T1)

    # --- verify -------------------------------------------------------------

    def test_verify_passes_on_pieces_the_tool_captured(self):
        self.capture_command()
        self.capture_command(piece="autre")

        answer = self.ok("verify", CONVOY, T1)
        self.assertEqual(["autre", "demo.commande"], sorted(piece["piece"] for piece in answer["pieces"]))
        self.assertEqual(["demo.commande"],
                         [piece["piece"] for piece in self.ok("verify", CONVOY, T1, "--piece", "demo.commande")["pieces"]])

    def test_verify_fails_when_the_store_file_no_longer_matches_the_tracker(self):
        self.capture_command()
        path = self.store / SPEC / T1 / "demo.commande.json"
        path.write_text(path.read_text().replace("bonjour", "au revoir"))

        error = self.refused("verify", CONVOY, T1, "--piece", "demo.commande")
        self.assertIn("empreinte", error)
        self.refused("verify", CONVOY, T1)

    def test_verify_fails_when_the_image_was_replaced(self):
        state_file, _ = self.launch()
        self.ok("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file, "--path", "/")
        image = self.store / SPEC / T1 / self.record("demo.page")["image"]
        image.write_bytes(PNG_MAGIC + b"autre image")

        error = self.refused("verify", CONVOY, T1, "--piece", "demo.page")
        self.assertIn("image", error)

    def test_verify_fails_when_the_piece_is_missing_from_the_store(self):
        self.capture_command()
        (self.store / SPEC / T1 / "demo.commande.json").unlink()

        error = self.refused("verify", CONVOY, T1, "--piece", "demo.commande")
        self.assertIn("absente du magasin", error)

    def test_hand_written_piece_is_refused_even_with_its_fingerprint_in_the_tracker(self):
        """A file written by hand, whose author also writes its fingerprint in
        the tracker: the fingerprint matches, the piece is still refused."""
        self.capture_command(piece="vraie")
        forged = dict(self.record("vraie"), piece="demo.redigee", output="tout est vert\n", exit_code=0)
        path = self.store / SPEC / T1 / "demo.redigee.json"
        path.write_text(json.dumps(forged, indent=2, sort_keys=True))
        proc = subprocess.run(
            (str(STATE_TOOL), "add-evidence", CONVOY, T1, "--piece", "demo.redigee",
             "--digest", sha256_of(path), "--commit", self.head),
            env=self.env, text=True, capture_output=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        error = self.refused("verify", CONVOY, T1, "--piece", "demo.redigee")
        self.assertIn("pas été produite par l'outil de capture", error)
        self.refused("verify", CONVOY, T1)

    def test_hand_written_piece_without_any_seal_is_refused(self):
        path = self.store / SPEC / T1 / "demo.redigee.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"kind": "command", "command": ["true"], "output": "ok", "exit_code": 0}))
        subprocess.run(
            (str(STATE_TOOL), "add-evidence", CONVOY, T1, "--piece", "demo.redigee",
             "--digest", sha256_of(path), "--commit", self.head),
            env=self.env, text=True, capture_output=True, check=True,
        )

        error = self.refused("verify", CONVOY, T1, "--piece", "demo.redigee")
        self.assertIn("pas été produite par l'outil de capture", error)

    def test_piece_moved_to_another_ticket_is_refused(self):
        """A genuine piece of one ticket, copied under another: its seal is
        intact, but it does not say this ticket."""
        self.capture_command()
        source = self.store / SPEC / T1 / "demo.commande.json"
        target = self.store / SPEC / T2 / "demo.commande.json"
        target.parent.mkdir(parents=True)
        shutil.copy(source, target)
        subprocess.run(
            (str(STATE_TOOL), "add-evidence", CONVOY, T2, "--piece", "demo.commande",
             "--digest", sha256_of(target), "--commit", self.head),
            env=self.env, text=True, capture_output=True, check=True,
        )

        error = self.refused("verify", CONVOY, T2, "--piece", "demo.commande")
        self.assertIn(T1, error)

    def test_store_file_without_a_fingerprint_fails_the_ticket(self):
        self.capture_command()
        (self.store / SPEC / T1 / "sans.empreinte.json").write_text("{}")

        error = self.refused("verify", CONVOY, T1)
        self.assertIn("sans.empreinte", error)

    def test_verify_of_a_piece_never_captured_is_refused(self):
        error = self.refused("verify", CONVOY, T1, "--piece", "jamais.capturee")
        self.assertIn("jamais.capturee", error)

    def test_verify_on_an_unmarked_convoy_reads_nothing(self):
        message = self.refused("verify", PLAIN_CONVOY, P1, status=EXIT_NOT_NEW_FLOW)
        self.assertIn("pas un convoi du nouveau flux", message)

    # --- outside Git history ------------------------------------------------

    def test_no_piece_reaches_the_git_history_of_the_product_or_the_factory(self):
        def snapshot(repo):
            def git(*args):
                return subprocess.run(("git", "-C", str(repo), *args), env=self.env, text=True,
                                      capture_output=True, check=True).stdout
            return git("status", "--porcelain", "--untracked-files=all"), git("rev-list", "--all", "--count")

        before = snapshot(self.repo), snapshot(ROOT)
        state_file, _ = self.launch()
        self.capture_command()
        self.ok("screenshot", CONVOY, T1, "--piece", "demo.page", "--launch-state", state_file, "--path", "/")

        self.assertEqual(before, (snapshot(self.repo), snapshot(ROOT)))
        self.assertEqual(3, len(self.store_files()))

    def test_store_inside_a_git_work_tree_is_refused(self):
        witness = self.tmp / "ran"
        for inside in (self.repo / "preuves", ROOT / "tmp" / "evidence-capture-test-store"):
            error = self.refused("command", CONVOY, T1, "--piece", "p", "--repo", self.repo, "--", "touch", witness,
                                 env={**self.env, "EVIDENCE_STORE_DIR": str(inside)})
            self.assertIn("dépôt Git", error)
            self.assertFalse(inside.exists(), "le magasin a été créé dans un dépôt Git")
        self.assertFalse(witness.exists(), "la commande a été exécutée malgré le refus")

    # --- purge --------------------------------------------------------------

    def test_purge_removes_the_pieces_of_that_spec_and_no_other(self):
        self.capture_command()
        self.capture_command(piece="t2.piece", ticket=T2)
        self.capture_command(piece="autre.spec", convoy=OTHER_CONVOY, ticket=U1)
        kept = {name: digest for name, digest in self.store_files().items() if name.startswith(OTHER_SPEC + "/")}
        self.assertEqual(1, len(kept))

        answer = self.ok("purge", "--spec", SPEC)

        self.assertEqual(2, answer["removed"])
        self.assertEqual(kept, self.store_files())
        self.assertFalse((self.store / SPEC).exists())
        self.ok("verify", OTHER_CONVOY, U1)
        self.assertIn("absente du magasin", self.refused("verify", CONVOY, T1))

    def test_purge_of_a_spec_without_pieces_removes_nothing(self):
        self.capture_command(piece="autre.spec", convoy=OTHER_CONVOY, ticket=U1)
        before = self.store_files()

        self.assertEqual(0, self.ok("purge", "--spec", SPEC)["removed"])
        self.assertEqual(before, self.store_files())

    def test_purge_refuses_a_name_that_is_not_a_spec(self):
        self.capture_command()
        for name in ("..", ".", "fx-spec/../fx-spec2", "", ".seal-key"):
            error = self.refused("purge", "--spec", name)
            self.assertTrue(re.search(r"Spec", error), error)


if __name__ == "__main__":
    unittest.main()
