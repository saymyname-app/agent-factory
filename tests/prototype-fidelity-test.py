#!/usr/bin/env python3
"""bin/prototype-fidelity on a fake tracker state (T16, af-622nya; Spec
af-wf4w5r §3, §7, §9, Testing Decisions seam 2): one test per pass and per
refusal. Only command lines are exercised. The product is a copy of the
Delivery Fixture City in a throwaway repository, launched for real by
bin/project-launch at the commit under test; the Validated Prototype is a
copy of the fixture's; the browser is a fake that fetches the pages it is
given (the real Chromium is driven by
tests/prototype-fidelity-demonstration-test.sh, local-only)."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "prototype-fidelity"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
EXIT_TOOL = ROOT / "bin" / "ticket-exit"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = "tests/fixtures/delivery-fixture-city"
APP = f"{FIXTURE}/app.py"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_BROWSER = ROOT / "tests" / "fixtures" / "prototype-fidelity" / "browser"

CONVOY, SPEC, T1, T2 = "fx-convoy", "fx-spec", "fx-t1", "fx-t2"
PLAIN_CONVOY, P1 = "fx-plain", "fx-p1"
STATES = ("empty", "content")
VIEWPORTS = ("desktop", "narrow")
ANCHORS = ("fixture-state", "fixture-generated-at", "fixture-items")

EXIT_RED = 1
EXIT_REFUSED = 2
EXIT_NOT_NEW_FLOW = 4
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Tokens and rules added to both sides by `styled`: the fixture's own pages
# carry no style sheet.
STYLE = ("<style>:root{--fixture-accent:#0b5fff;--fixture-gap:12px}"
         "h1{color:var(--fixture-accent);font-size:28px}ul{padding:var(--fixture-gap)}</style>")
SESSION_IDENTITY = ("GC_SESSION_NAME", "GC_SESSION_ID", "GC_AGENT", "BEADS_ACTOR", "GC_BEAD_ID")


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PrototypeFidelityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prototype-fidelity-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.prototype = self.tmp / "prototype"
        self.descriptor = self.repo / FIXTURE / "descriptor.json"
        self.browser_log = self.tmp / "browser.log"
        self.root = self.tmp / "root"
        (self.root / "config").mkdir(parents=True)
        (self.tmp / "proposal-door").write_text("#!/bin/sh\necho 0\n")
        (self.tmp / "proposal-door").chmod(0o755)
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.store),
            "EVIDENCE_CAPTURE_BROWSER": str(FAKE_BROWSER),
            "EVIDENCE_FAKE_BROWSER_LOG": str(self.browser_log),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for name in ("FIDELITY_FAKE_BROWSER_MODE", "EVIDENCE_FAKE_BROWSER_MODE", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.seed_tracker()
        shutil.copytree(ROOT / FIXTURE / "prototype", self.prototype)
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE)
        self.git("init", "-q", "-b", "main")
        self.head = self.commit("produit conforme")
        # The ticket's branch is the one the product is committed on: a
        # verdict is valid while its commit is the tip of that branch.
        self.state("set-branch", CONVOY, T1, "--branch", "main")

    # --- harness ------------------------------------------------------------

    def seed_tracker(self):
        """A marked convoy of two tickets, and a convoy without the mark."""
        def convoy(spec, tickets):
            return {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                    "metadata": {"gc.spec_id": spec}, "tracks": tickets}

        def ticket():
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "metadata": {"gc.ticket_kind": "prefactoring"}}

        beads = {CONVOY: convoy(SPEC, [T1, T2]), T1: ticket(), T2: ticket(),
                 PLAIN_CONVOY: convoy("fx-spec3", [P1]), P1: ticket()}
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY)

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def edit_product(self, old, new, message):
        """Change the delivered page and commit; return the new commit."""
        app = self.repo / APP
        source = app.read_text()
        self.assertIn(old, source)
        app.write_text(source.replace(old, new))
        self.head = self.commit(message)
        return self.head

    def styled(self):
        """The same style sheet, with its tokens, on both sides."""
        for page in sorted((self.prototype / "states").glob("*.html")):
            page.write_text(page.read_text().replace("</head>", STYLE + "\n</head>"))
        self.edit_product("</title></head>", "</title>" + STYLE + "</head>", "feuille de style")

    def state(self, *args):
        proc = subprocess.run((str(STATE_TOOL), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket=T1):
        return next(t for t in self.state("show", CONVOY, "--repo", self.repo)["tickets"] if t["id"] == ticket)

    def check(self, *args, env=None, descriptor=None, commit=None):
        return subprocess.run(
            (str(TOOL), "check", str(descriptor or self.descriptor), "--repo-root", str(self.repo),
             "--commit", commit or self.head, "--prototype", str(self.prototype), *[str(a) for a in args]),
            env=env or self.env, text=True, capture_output=True, cwd=self.tmp,
        )

    def green(self, *args, **kwargs):
        proc = self.check(*args, **kwargs)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def red(self, *args, **kwargs):
        proc = self.check(*args, **kwargs)
        self.assertEqual(EXIT_RED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertEqual("rouge", answer["result"])
        return answer

    def refused(self, *args, status=EXIT_REFUSED, **kwargs):
        """A refusal: nothing was compared to the end, and neither the
        tracker nor the evidence store changed."""
        tracker_before, store_before = self.tracker.read_text(), self.store_files()
        proc = self.check(*args, **kwargs)
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertNotIn("result", answer)
        self.assertEqual(tracker_before, self.tracker.read_text(), "un refus a écrit dans le tracker")
        self.assertEqual(store_before, self.store_files(), "un refus a écrit dans le magasin de preuves")
        return answer.get("error") or answer.get("message")

    def store_files(self):
        if not self.store.exists():
            return {}
        return {str(path.relative_to(self.store)): sha256_of(path)
                for path in sorted(self.store.rglob("*")) if path.is_file() and path.name != ".seal-key"}

    def named(self, deviations, **fields):
        return [d for d in deviations if all(d.get(key) == value for key, value in fields.items())]

    def descriptor_with_screens(self, screens):
        descriptor = json.loads(self.descriptor.read_text())
        descriptor["launch"]["screens"] = screens
        path = self.tmp / "descriptor.json"
        path.write_text(json.dumps(descriptor))
        return path

    # --- AC1: the conforming fixture is green, one record per anchor and state --

    def test_conforming_fixture_is_green_with_one_record_per_anchor_and_prototyped_state(self):
        answer = self.green()

        self.assertTrue(answer["ok"])
        self.assertEqual("vert", answer["result"])
        self.assertEqual(self.head, answer["commit"])
        self.assertEqual([], answer["deviations"])
        self.assertEqual(sorted(STATES), sorted(answer["states"]))
        for state in STATES:
            records = answer["states"][state]["records"]
            self.assertEqual(
                sorted((viewport, anchor) for viewport in VIEWPORTS for anchor in ANCHORS),
                sorted((record["viewport"], record["anchor"]) for record in records), state)
            self.assertEqual({"identique"}, {record["verdict"] for record in records}, state)

    def test_both_sides_are_rendered_at_comparison_time_for_every_state_and_viewport(self):
        self.green()

        fetched = self.browser_log.read_text().split()
        prototype_pages = [url for url in fetched if "/states/" in url]
        delivered_pages = [url for url in fetched if "/states/" not in url]
        self.assertEqual(len(STATES) * len(VIEWPORTS), len(prototype_pages))
        self.assertEqual(len(STATES) * len(VIEWPORTS), len(delivered_pages))
        # The delivered page is the one served at its real address: the path
        # the profile declares for the screen, on the launched product.
        self.assertTrue(all(url.endswith("/") for url in delivered_pages), delivered_pages)

    def test_styled_fixture_is_green_and_its_tokens_are_compared_on_the_sources(self):
        self.styled()

        answer = self.green()

        for state in STATES:
            self.assertEqual(2, answer["states"][state]["tokens"]["compared"], state)

    # --- AC2: an absent anchor, a changed token, a computed style: red, named --

    def test_anchor_absent_from_the_delivered_page_is_red_and_names_anchor_and_state(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")

        answer = self.red()

        for state in STATES:
            for viewport in VIEWPORTS:
                found = self.named(answer["deviations"], state=state, viewport=viewport, anchor="fixture-items")
                self.assertEqual([("absent", "présence")], [(d["kind"], d["property"]) for d in found], (state, viewport))
        self.assertEqual({"fixture-items"}, {d["anchor"] for d in answer["deviations"]})
        absent = [r for r in answer["states"]["empty"]["records"] if r["anchor"] == "fixture-items"]
        self.assertEqual({"absente"}, {r["verdict"] for r in absent})

    def test_changed_token_is_red_and_names_token_and_state(self):
        self.styled()
        self.edit_product("--fixture-gap:12px", "--fixture-gap:16px", "token modifié")

        answer = self.red()

        for state in STATES:
            found = self.named(answer["deviations"], state=state, kind="token", property="--fixture-gap")
            self.assertEqual(1, len(found), state)
            self.assertEqual(("12px", "16px"), (found[0]["prototype"], found[0]["delivered"]))
        # The anchor that uses the token is named too, with the property it changes.
        self.assertTrue(self.named(answer["deviations"], state="content", viewport="desktop",
                                   anchor="fixture-items", kind="style", property="padding"))

    def test_computed_style_differing_on_an_anchor_is_red_and_names_anchor_state_and_property(self):
        self.styled()
        self.edit_product("font-size:28px", "font-size:30px", "taille du titre")

        answer = self.red()

        for state in STATES:
            for viewport in VIEWPORTS:
                found = self.named(answer["deviations"], state=state, viewport=viewport, anchor="fixture-state")
                self.assertEqual([("style", "font-size", "28px", "30px")],
                                 [(d["kind"], d["property"], d["prototype"], d["delivered"]) for d in found])
        self.assertEqual({"fixture-state"}, {d["anchor"] for d in answer["deviations"]})

    def test_structure_differing_on_an_anchor_is_red_and_named(self):
        self.edit_product('<h1 data-anchor="fixture-state">{state}</h1>',
                          '<h2 data-anchor="fixture-state">{state}</h2>', "balise du titre")

        answer = self.red()

        found = self.named(answer["deviations"], state="empty", viewport="desktop", anchor="fixture-state", kind="structure")
        self.assertEqual([("tag", "h1", "h2")], [(d["property"], d["prototype"], d["delivered"]) for d in found])

    def test_never_green_on_a_state_it_did_not_compare(self):
        # A prototyped state the prototype does not hold.
        message = self.refused("--states", "empty,content,error")
        self.assertIn("error", message)
        # A prototyped state no screen of the profile serves.
        partial = self.descriptor_with_screens([{"name": "accueil", "path": "/", "states": ["empty"]}])
        message = self.refused(descriptor=partial)
        self.assertIn("content", message)
        # A browser that measured nothing.
        message = self.refused(env={**self.env, "FIDELITY_FAKE_BROWSER_MODE": "no-measure"})
        self.assertIn("mesure", message)

    def test_profile_without_screens_is_refused(self):
        descriptor = json.loads(self.descriptor.read_text())
        del descriptor["launch"]["screens"]
        path = self.tmp / "descriptor.json"
        path.write_text(json.dumps(descriptor))

        self.assertIn("screens", self.refused(descriptor=path))

    def test_prototype_that_is_not_a_validated_prototype_is_refused(self):
        (self.prototype / "validated-prototype.json").unlink()

        self.assertIn("validated-prototype.json", self.refused())

    def test_delivered_file_with_the_digest_of_a_prototype_file_is_refused_and_named(self):
        """T46 (af-lb9zkz): the prototype file is not promoted as is."""
        self.edit_product(
            "self._respond_html(200, self._render_page())",
            'self._respond_html(200, (Path(__file__).parent / "prototype" / "states" / '
            '(self.dataset["state"] + ".html")).read_text(encoding="utf-8"))',
            "le fichier du prototype servi tel quel",
        )

        error = self.refused()

        for fragment in ("states/content.html", "states/empty.html", "même empreinte", "promu tel quel"):
            self.assertIn(fragment, error)

    def test_named_ticket_serving_a_prototype_file_as_is_is_refused_before_anything_is_filed(self):
        self.edit_product(
            "self._respond_html(200, self._render_page())",
            'self._respond_html(200, (Path(__file__).parent / "prototype" / "states" / '
            '(self.dataset["state"] + ".html")).read_text(encoding="utf-8"))',
            "le fichier du prototype servi tel quel",
        )

        self.assertIn("promu tel quel", self.refused("--convoy", CONVOY, "--ticket", T1))

    # --- AC3: side-by-side captures and a difference image, never a threshold --

    def test_named_ticket_files_side_by_side_and_difference_captures_per_state(self):
        answer = self.green("--convoy", CONVOY, "--ticket", T1)

        evidence = self.shown()["evidence"]
        for state in STATES:
            for viewport in VIEWPORTS:
                piece = f"fidelity.{state}.{viewport}"
                capture = answer["states"][state]["captures"][viewport]
                self.assertEqual(piece, capture["piece"])
                record = json.loads((self.store / SPEC / T1 / f"{piece}.json").read_text())
                self.assertEqual("comparison", record["kind"])
                self.assertEqual(self.head, record["commit"])
                self.assertIn(f"/states/{state}.html", record["reference"])
                for name, digest in ((record["image"], record["image_digest"]),
                                     (record["difference"], record["difference_digest"])):
                    image = self.store / SPEC / T1 / name
                    self.assertTrue(image.read_bytes().startswith(PNG_MAGIC), name)
                    self.assertEqual(sha256_of(image), digest)
                self.assertEqual(sha256_of(self.store / SPEC / T1 / f"{piece}.json"), evidence[piece]["digest"])
        proc = subprocess.run((str(CAPTURE_TOOL), "verify", CONVOY, T1), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_one_launched_product_at_a_time_while_measuring_and_capturing(self):
        # af-6xjghg: 24 states launched together saturated the host. A
        # browser that counts the product copies (one worktree each, next to
        # the main one) every time it renders a page.
        copies = self.tmp / "copies.log"
        browser = self.tmp / "counting-browser"
        browser.write_text(
            "#!/bin/sh\n"
            f"git -C '{self.repo}' worktree list --porcelain | grep -c '^worktree ' >> '{copies}'\n"
            f"exec '{FAKE_BROWSER}' \"$@\"\n")
        browser.chmod(0o755)

        self.green("--convoy", CONVOY, "--ticket", T1, env={**self.env, "EVIDENCE_CAPTURE_BROWSER": str(browser)})

        seen = [int(count) - 1 for count in copies.read_text().split()]
        self.assertTrue(seen, "aucune page rendue")
        self.assertEqual({1}, set(seen), seen)

    def test_no_pixel_threshold_fails_the_command(self):
        # The fake browser draws each page from its bytes: the prototype page
        # and the delivered page differ on every pixel, and the command is green.
        answer = self.green("--convoy", CONVOY, "--ticket", T1)

        capture = answer["states"]["content"]["captures"]["desktop"]
        self.assertGreater(capture["differing_pixels"], 0)
        self.assertEqual(capture["pixels"], capture["differing_pixels"])
        self.assertEqual("vert", answer["result"])

    # --- AC4: a named ticket: its screen only, the result on the ticket --------

    def test_named_ticket_records_the_result_on_the_ticket_tied_to_the_commit(self):
        self.green("--convoy", CONVOY, "--ticket", T1)

        ticket = self.shown()
        fidelity = ticket["fidelity"]
        self.assertEqual((self.head, "favorable", "vert"), (fidelity["commit"], fidelity["verdict"], fidelity["state"]))
        self.assertEqual(["accueil"], fidelity["screens"])
        self.assertEqual(sorted(STATES), sorted(fidelity["states"]))
        self.assertEqual(sorted(ANCHORS), sorted(fidelity["states"]["empty"]["anchors"]))
        self.assertEqual([], fidelity["deviations"])
        verdict = ticket["verdicts"]["fidelity"]
        self.assertEqual(("favorable", self.head), (verdict["state"], verdict["commit"]))
        # The record is a piece of the evidence store, at the same commit.
        self.assertEqual(self.head, ticket["evidence"]["fidelity"]["commit"])
        proc = subprocess.run((str(CAPTURE_TOOL), "verify", CONVOY, T1, "--piece", "fidelity"),
                              env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIsNone(self.shown(T2)["fidelity"])

    def test_red_result_is_recorded_on_the_ticket_with_the_anchor_state_and_property(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")

        self.red("--convoy", CONVOY, "--ticket", T1)

        ticket = self.shown()
        fidelity = ticket["fidelity"]
        self.assertEqual((self.head, "unfavorable", "rouge"), (fidelity["commit"], fidelity["verdict"], fidelity["state"]))
        self.assertTrue(self.named(fidelity["deviations"], state="empty", viewport="desktop",
                                   anchor="fixture-items", kind="absent", status="ouvert"))
        self.assertEqual("unfavorable", ticket["verdicts"]["fidelity"]["state"])

    def test_named_ticket_compares_only_the_anchors_of_the_screen_it_touches(self):
        two_screens = self.descriptor_with_screens([
            {"name": "accueil-vide", "path": "/", "states": ["empty"]},
            {"name": "accueil-contenu", "path": "/", "states": ["content"]},
        ])
        # The other screen is broken: it is not this ticket's to compare.
        app = self.repo / APP
        app.write_text(app.read_text().replace(
            'items_html = "".join(', 'anchor = "autre" if items else "fixture-items"\n        items_html = "".join('))
        self.edit_product('<ul data-anchor="fixture-items">', '<ul data-anchor="{anchor}">', "autre écran modifié")
        self.assertEqual({"content"}, {d["state"] for d in self.red(descriptor=two_screens)["deviations"]})
        self.browser_log.unlink()

        answer = self.green("--convoy", CONVOY, "--ticket", T1, "--screen", "accueil-vide", descriptor=two_screens)

        self.assertEqual(["empty"], sorted(answer["states"]))
        self.assertEqual(["accueil-vide"], answer["screens"])
        fidelity = self.shown()["fidelity"]
        self.assertEqual((["accueil-vide"], ["empty"]), (fidelity["screens"], sorted(fidelity["states"])))
        self.assertFalse([url for url in self.browser_log.read_text().split() if "content" in url])

    def test_named_ticket_must_name_its_screen_when_the_profile_has_several(self):
        two_screens = self.descriptor_with_screens([
            {"name": "accueil-vide", "path": "/", "states": ["empty"]},
            {"name": "accueil-contenu", "path": "/", "states": ["content"]},
        ])

        self.assertIn("--screen", self.refused("--convoy", CONVOY, "--ticket", T1, descriptor=two_screens))
        self.assertIn("inconnu", self.refused("--convoy", CONVOY, "--ticket", T1, "--screen", "ailleurs",
                                              descriptor=two_screens))

    def test_unmarked_convoy_is_not_touched(self):
        message = self.refused("--convoy", PLAIN_CONVOY, "--ticket", P1, status=EXIT_NOT_NEW_FLOW)

        self.assertIn("pas un convoi du nouveau flux", message)
        self.assertFalse(self.browser_log.exists(), "rien ne doit être comparé sur un convoi sans marque")

    def test_ticket_outside_the_convoy_is_refused_before_anything_runs(self):
        self.assertIn(P1, self.refused("--convoy", CONVOY, "--ticket", P1))
        self.assertIn("--convoy", self.refused("--ticket", T1))
        self.assertFalse(self.browser_log.exists())

    # --- AC5: a declared deviation stays red; only a resolved Planning Exception accepts it --

    def start_ticket(self):
        self.state("record-gate", CONVOY, T1, "--gate", "dispatch")
        data = json.loads(self.tracker.read_text())
        data["beads"][T1]["status"] = "in_progress"
        self.tracker.write_text(json.dumps(data))

    def run_door(self, tool, *args):
        proc = subprocess.run((str(tool), *[str(a) for a in args]), env=self.env, text=True, capture_output=True,
                              cwd=self.tmp)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout

    def raise_planning_exception(self, *anchors):
        args = [arg for anchor in anchors for arg in ("--anchor", anchor)]
        # The deviation is written in the Ticket Handoff first (T41), anchor by anchor.
        handoff = self.tmp / "handoff-exception.json"
        handoff.write_text(json.dumps({
            "done": "aucun", "not_done": "aucun", "out_of_ticket": "aucun",
            "deviations": [f"L'ancre {anchor} s'écarte du prototype." for anchor in anchors] or "aucun"}))
        self.run_door(EXIT_TOOL, "exit", CONVOY, T1, "--exit", "planning_exception", "--kind", "semantic",
                      "--repo", self.repo, "--handoff", handoff,
                      "--summary", "La liste est livrée sans sa région, le prototype la montre", *args)

    def accept_letter(self):
        return self.shown()["planning_exceptions"][-1]["accept_option"]

    def test_deviation_declared_in_the_handoff_stays_red(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")
        self.start_ticket()
        handoff = self.tmp / "handoff.json"
        handoff.write_text(json.dumps({
            "sections": {"deviations": ["L'ancre fixture-items n'est pas livrée : écart voulu."]},
            "partial": True, "commit": self.head}))
        self.state("set-handoff", CONVOY, T1, "--file", handoff)

        answer = self.red("--convoy", CONVOY, "--ticket", T1)

        self.assertEqual({"ouvert"}, {d["status"] for d in answer["deviations"]})
        self.assertEqual("rouge", self.shown()["fidelity"]["state"])

    def test_resolved_planning_exception_naming_the_anchor_turns_it_accepted_by_benjamin(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")
        self.start_ticket()
        self.red("--convoy", CONVOY, "--ticket", T1)
        self.raise_planning_exception("fixture-items")
        # Raised and not answered: still red.
        self.assertEqual("rouge", self.shown()["fidelity"]["state"])
        self.red("--convoy", CONVOY, "--ticket", T1)

        self.run_door(ESCALATION_TOOL, "repondre", T1, self.accept_letter())

        fidelity = self.shown()["fidelity"]
        self.assertEqual("accepté par Benjamin", fidelity["state"])
        self.assertEqual({"accepté par Benjamin"}, {d["status"] for d in fidelity["deviations"]})
        # The stored verdict is not rewritten: the deviation is still one.
        self.assertEqual("unfavorable", fidelity["verdict"])
        answer = self.green("--convoy", CONVOY, "--ticket", T1)
        self.assertEqual("accepté par Benjamin", answer["result"])
        self.assertEqual({"accepté par Benjamin"}, {d["status"] for d in answer["deviations"]})

    def test_planning_exception_answered_otherwise_or_naming_another_anchor_leaves_it_red(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")
        self.start_ticket()
        self.raise_planning_exception("fixture-state")
        self.run_door(ESCALATION_TOOL, "repondre", T1, self.accept_letter())

        # Accepted on another anchor than the one that deviates.
        answer = self.red("--convoy", CONVOY, "--ticket", T1)
        self.assertEqual({"ouvert"}, {d["status"] for d in answer["deviations"]})

        self.raise_planning_exception("fixture-items")
        self.assertNotEqual("a", self.accept_letter())
        self.run_door(ESCALATION_TOOL, "repondre", T1, "a")

        # Answered, but not by the option that accepts the deviation.
        self.assertEqual("rouge", self.shown()["fidelity"]["state"])
        self.red("--convoy", CONVOY, "--ticket", T1)

    def test_no_option_of_the_command_lifts_a_red(self):
        self.edit_product('<ul data-anchor="fixture-items">', "<ul>", "ancre retirée")

        for option in ("--accept", "--accepted", "--waive", "--ignore-anchor", "--allow"):
            proc = self.check("--convoy", CONVOY, "--ticket", T1, option, "fixture-items")
            self.assertEqual(2, proc.returncode, option)
            self.assertIn("unrecognized arguments", proc.stderr, option)
        self.assertIsNone(self.shown()["fidelity"])


if __name__ == "__main__":
    unittest.main()
