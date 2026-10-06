#!/usr/bin/env python3

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fixture_prototype import FROZEN_COMMIT, PROTOTYPE_SOURCE, materialize  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-approve"
FIXTURES = ROOT / "tests" / "fixtures" / "spec-approve"
FAKE_BD = FIXTURES / "bd"
PROJECTS_CONFIG_DIR = FIXTURES / "projects"
# The smallest Spec body bd-approve accepts since T07 (af-tvda3w): numbered
# user stories, no interface story, so no Validated Prototype reference.
SPEC_BODY = "prose spec body\n\n## User Stories\n\n1. As an operator, I want a probe, so that I know it runs.\n"
FIXTURE_SPEC = (ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "spec.md").read_text(encoding="utf-8")


class SpecApproveBeadModeTest(unittest.TestCase):
    """W04: spec-approve approves a planning-plane Spec bead by id, with or
    without a map, against the live Beads/reservation/profile tools."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec-approve-bd-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()

    def invoke(self, *args, check=False):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "SPEC_APPROVE_BD_STATE": str(self.state_path),
        }
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), env=env, text=True, capture_output=True, check=check,
        )

    def seed(self, beads, next_id=1):
        self.state_path.write_text(json.dumps({"beads": beads, "next_id": next_id}))

    def bead(self, **kwargs):
        base = {
            "labels": [], "metadata": {}, "parent": None, "status": "open",
            "title": "", "description": SPEC_BODY,
        }
        base.update(kwargs)
        return base

    def current_state(self):
        return json.loads(self.state_path.read_text())

    def write_reservation(self, reserved_for):
        runtime_path = self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(json.dumps({
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "cleared_at": None,
        }))

    def bd_approve(self, spec_id, approved_by="benjamin", evidence="Benjamin's exact words, 2026-09-30 Paris", project="acme", check=False):
        return self.invoke(
            "bd-approve", "--spec", spec_id, "--approved-by", approved_by, "--evidence", evidence,
            "--project", project, "--repo-root", self.repo_root, "--config-dir", PROJECTS_CONFIG_DIR,
            check=check,
        )

    def mapped_spec_beads(self, target="A6b", map_finished=True):
        return {
            "spec-1": self.bead(id="spec-1", metadata={"planning_run_target": target, "planning_map": "map-1"}),
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="closed" if map_finished else "open",
                labels=["wayfinder:task"], metadata={"gc.plane": "planning"},
            ),
        }

    # --- refusals: Spec bead and map are left untouched ---------------------

    def test_bd_approve_refuses_wrong_target_while_reserved(self):
        self.seed(self.mapped_spec_beads(target="A6b"))
        self.write_reservation(reserved_for="C01")

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("C01", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_unfinished_map(self):
        self.seed(self.mapped_spec_beads(map_finished=False))

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("not finished", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_wrong_approver(self):
        self.seed(self.mapped_spec_beads())

        proc = self.bd_approve("spec-1", approved_by="someone-else")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("declared human approver", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_empty_evidence(self):
        self.seed(self.mapped_spec_beads())

        proc = self.bd_approve("spec-1", evidence="")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_no_map_and_no_no_fog_evidence(self):
        self.seed({
            "spec-1": self.bead(id="spec-1", metadata={"planning_run_target": "A6b", "planning_map": "none"}),
        })

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("No-fog", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    # --- success: mapped and unmapped ----------------------------------------

    def test_bd_approve_approves_valid_mapped_spec_records_digest_and_closes_map(self):
        beads = self.mapped_spec_beads()
        beads["spec-1"]["description"] = SPEC_BODY
        self.seed(beads)

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["map_closed"])
        self.assertEqual("APPROVED_SPEC", result["state"])

        expected_digest = "sha256:" + hashlib.sha256(SPEC_BODY.encode("utf-8")).hexdigest()
        self.assertEqual(expected_digest, result["digest"])

        state = self.current_state()
        spec_metadata = state["beads"]["spec-1"]["metadata"]
        self.assertEqual("APPROVED_SPEC", spec_metadata["spec_state"])
        self.assertEqual("benjamin", spec_metadata["approved_by"])
        self.assertEqual(expected_digest, spec_metadata["approved_digest"])
        self.assertEqual("closed", state["beads"]["map-1"]["status"])

    def test_bd_approve_approves_valid_unmapped_spec_with_no_fog_evidence(self):
        self.seed({
            "spec-1": self.bead(
                id="spec-1",
                metadata={
                    "planning_run_target": "A6b", "planning_map": "none",
                    "no_fog_evidence": "« pas de brouillard » (Benjamin, 2026-09-30 Paris)",
                },
                description=SPEC_BODY,
            ),
        })

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["map_closed"])
        self.assertIsNone(result["map"])

        state = self.current_state()
        self.assertEqual("APPROVED_SPEC", state["beads"]["spec-1"]["metadata"]["spec_state"])

    # --- project key: map to Spec (T05) --------------------------------------

    def test_bd_approve_sets_spec_project_key_from_its_map(self):
        beads = self.mapped_spec_beads()
        beads["map-1"]["metadata"]["gc.project_id"] = "fixture-project"
        self.seed(beads)

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])

        state = self.current_state()
        self.assertEqual("fixture-project", state["beads"]["spec-1"]["metadata"]["gc.project_id"])

    def test_bd_approve_refuses_a_spec_whose_project_key_contradicts_its_map(self):
        beads = self.mapped_spec_beads()
        beads["map-1"]["metadata"]["gc.project_id"] = "fixture-project"
        beads["spec-1"]["metadata"]["gc.project_id"] = "another-project"
        self.seed(beads)

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("contradicts", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    def test_bd_approve_keeps_an_unmapped_specs_own_project_key(self):
        self.seed({
            "spec-1": self.bead(
                id="spec-1",
                metadata={
                    "planning_run_target": "A6b", "planning_map": "none",
                    "no_fog_evidence": "« pas de brouillard » (Benjamin, 2026-09-30 Paris)",
                    "gc.project_id": "its-own-project",
                },
                description=SPEC_BODY,
            ),
        })

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])

        state = self.current_state()
        self.assertEqual("its-own-project", state["beads"]["spec-1"]["metadata"]["gc.project_id"])

    # --- status: an edit after approval voids it -----------------------------

    def test_bd_status_reports_void_after_spec_edited_post_approval(self):
        beads = self.mapped_spec_beads()
        self.seed(beads)
        self.assertTrue(json.loads(self.bd_approve("spec-1", check=True).stdout)["ok"])

        state = self.current_state()
        state["beads"]["spec-1"]["description"] = "edited after approval"
        self.state_path.write_text(json.dumps(state))

        proc = self.invoke("bd-status", "--spec", "spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["void"])

    def test_bd_status_reports_not_void_when_unchanged(self):
        beads = self.mapped_spec_beads()
        self.seed(beads)
        self.assertTrue(json.loads(self.bd_approve("spec-1", check=True).stdout)["ok"])

        proc = self.invoke("bd-status", "--spec", "spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["void"])


class SpecApproveEntryContractTest(unittest.TestCase):
    """T07 (af-tvda3w; spec af-wf4w5r sections 2 and 3): bd-approve refuses a
    Spec that cannot be sliced and verified -- no numbered user stories, an
    interface story without a complete Validated Prototype reference, a
    reference whose commit is not on the remote repository, a missing state
    inventory, or a Validated Prototype that is not conformant. Each refusal
    re-reads the fake tracker state to prove nothing was written."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec-approve-contract-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()
        self.remote = self.tmp / "remote.git"
        self.frozen_commit = materialize(self.remote)

    def seed_spec(self, description, metadata=None):
        base = {
            "planning_run_target": "D01", "planning_map": "none",
            "no_fog_evidence": "« pas de brouillard » (Benjamin, 2026-10-06 Paris)",
        }
        base.update(metadata or {})
        self.state_path.write_text(json.dumps({
            "beads": {
                "spec-1": {
                    "id": "spec-1", "labels": [], "metadata": base, "parent": None, "status": "open",
                    "title": "Spec de la Fixture City", "description": description,
                },
            },
            "next_id": 1,
        }))

    def current_state(self):
        return json.loads(self.state_path.read_text())

    def invoke(self, *args):
        env = {**os.environ, "BD_BIN": str(FAKE_BD), "SPEC_APPROVE_BD_STATE": str(self.state_path)}
        return subprocess.run((str(TOOL), *[str(a) for a in args]), env=env, text=True, capture_output=True)

    def bd_approve(self, remote=None, name_remote=True):
        return self.invoke(
            "bd-approve", "--spec", "spec-1", "--approved-by", "benjamin",
            "--evidence", "« J'approuve » (Benjamin, 2026-10-06 Paris)",
            "--project", "delivery-fixture-city", "--repo-root", self.repo_root,
            "--config-dir", PROJECTS_CONFIG_DIR,
            *(("--prototype-remote", remote or self.remote) if name_remote else ()),
        )

    def assert_refused_untouched(self, description, *expected, metadata=None, remote=None):
        self.seed_spec(description, metadata)
        before = self.current_state()
        proc = self.bd_approve(remote)
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        for fragment in expected:
            self.assertIn(fragment, error["error"])
        self.assertEqual(before, self.current_state())
        return error["error"]

    def assert_approved(self, description):
        self.seed_spec(description)
        proc = self.bd_approve()
        self.assertEqual(0, proc.returncode, proc.stdout)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        metadata = self.current_state()["beads"]["spec-1"]["metadata"]
        self.assertEqual("APPROVED_SPEC", metadata["spec_state"])
        self.assertEqual("sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest(), metadata["approved_digest"])

    def replaced(self, old, new, spec=None):
        spec = FIXTURE_SPEC if spec is None else spec
        self.assertIn(old, spec)
        return spec.replace(old, new)

    def spec_on_altered_prototype(self, relative_path, old, new):
        """The fixture Spec, re-pointed at a prototype branch whose frozen
        files differ from the fixture's by one replacement."""
        altered = self.tmp / "altered-prototype"
        shutil.copytree(PROTOTYPE_SOURCE, altered)
        page = altered / relative_path
        text = page.read_text(encoding="utf-8")
        self.assertIn(old, text)
        page.write_text(text.replace(old, new), encoding="utf-8")
        remote = self.tmp / "altered-remote.git"
        commit = materialize(remote, altered)
        self.assertNotEqual(self.frozen_commit, commit)
        return self.replaced(self.frozen_commit, commit), remote

    # --- passage ----------------------------------------------------------------

    def test_the_fixture_spec_names_the_frozen_prototype_commit(self):
        self.assertEqual(FROZEN_COMMIT, self.frozen_commit)
        self.assertIn(FROZEN_COMMIT, FIXTURE_SPEC)

    def test_approves_the_fixture_spec(self):
        self.assert_approved(FIXTURE_SPEC)

    def test_approves_a_spec_without_interface_and_without_prototype_reference(self):
        self.assert_approved(
            "## Problem Statement\n\nRien ne sonde le produit.\n\n## User Stories\n\n"
            "1. As an exploitant, I want une sonde de santé, so that je sache que le produit répond.\n"
            "2. As an exploitant, I want un code de sortie, so that un script puisse le lire.\n\n"
            "## Out of Scope\n\nTout le reste.\n"
        )

    def test_reads_the_prototype_from_the_origin_remote_of_the_repo_root_by_default(self):
        subprocess.run(("git", "init", "--quiet", str(self.repo_root)), check=True)
        subprocess.run(("git", "-C", str(self.repo_root), "remote", "add", "origin", str(self.remote)), check=True)
        self.seed_spec(FIXTURE_SPEC)
        proc = self.bd_approve(name_remote=False)
        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertEqual("APPROVED_SPEC", self.current_state()["beads"]["spec-1"]["metadata"]["spec_state"])
        self.assertEqual("", subprocess.run(
            ("git", "-C", str(self.repo_root), "for-each-ref"), text=True, capture_output=True, check=True,
        ).stdout)

    def test_refuses_an_interface_spec_when_no_remote_repository_is_known(self):
        self.seed_spec(FIXTURE_SPEC)
        before = self.current_state()
        proc = self.bd_approve(name_remote=False)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("--prototype-remote", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.current_state())

    # --- refus : user stories numérotées ------------------------------------------

    def test_refuses_a_spec_whose_user_stories_are_not_numbered(self):
        spec = FIXTURE_SPEC
        for number in ("1", "2", "3"):
            spec = self.replaced(f"\n{number}. As a", "\n- As a", spec)
        self.assert_refused_untouched(spec, "user stories numérotées")

    def test_refuses_a_spec_without_a_user_stories_section(self):
        self.assert_refused_untouched("prose sans section\n\n1. une liste ailleurs\n", "user stories numérotées")

    def test_refuses_a_spec_whose_user_story_numbers_repeat(self):
        self.assert_refused_untouched(self.replaced("\n2. As a", "\n1. As a"), "numéro", "1")

    # --- refus : référence du Validated Prototype ---------------------------------

    def test_refuses_an_interface_story_without_prototype_reference(self):
        spec = FIXTURE_SPEC[: FIXTURE_SPEC.index("## Validated Prototype")] + "## Out of Scope\n\nTout le reste.\n"
        error = self.assert_refused_untouched(spec, "référence du Validated Prototype")
        self.assertIn("1", error)

    def test_refuses_a_reference_without_commit(self):
        spec = self.replaced(f"- commit : `{FROZEN_COMMIT}`\n", "")
        self.assert_refused_untouched(spec, "référence du Validated Prototype", "commit")

    def test_refuses_a_reference_without_branch_path_or_states(self):
        for line, missing in (
            ("- branche : `prototype/delivery-fixture-city`\n", "branche"),
            ("- chemin : `tests/fixtures/delivery-fixture-city/prototype`\n", "chemin"),
            ("- états : `empty`, `content`\n", "états"),
        ):
            with self.subTest(missing=missing):
                self.assert_refused_untouched(self.replaced(line, ""), "référence du Validated Prototype", missing)

    def test_refuses_a_reference_whose_commit_is_not_on_the_remote_repository(self):
        absent = "1" * 40
        self.assert_refused_untouched(self.replaced(FROZEN_COMMIT, absent), absent, "dépôt distant")

    def test_refuses_a_reference_whose_branch_is_not_on_the_remote_repository(self):
        spec = self.replaced("`prototype/delivery-fixture-city`", "`prototype/absente`")
        self.assert_refused_untouched(spec, "prototype/absente", "dépôt distant")

    def test_refuses_a_reference_whose_path_is_not_in_the_commit(self):
        spec = self.replaced("`tests/fixtures/delivery-fixture-city/prototype`", "`ailleurs/prototype`")
        self.assert_refused_untouched(spec, "ailleurs/prototype")

    # --- refus : inventaire des états ----------------------------------------------

    def test_refuses_a_spec_without_state_inventory(self):
        spec = (
            FIXTURE_SPEC[: FIXTURE_SPEC.index("### Écran : accueil")]
            + FIXTURE_SPEC[FIXTURE_SPEC.index("## Implementation Decisions"):]
        )
        self.assert_refused_untouched(spec, "inventaire des états")

    def test_refuses_an_inventory_missing_one_of_the_six_control_states(self):
        spec = self.replaced("| erreur | non prototypé | |\n", "")
        self.assert_refused_untouched(spec, "inventaire des états", "accueil", "erreur")

    def test_refuses_a_state_that_is_neither_prototyped_nor_not_prototyped(self):
        spec = self.replaced("| contenu long | non prototypé | |", "| contenu long | à voir | |")
        self.assert_refused_untouched(spec, "inventaire des états", "contenu long")

    def test_refuses_a_control_state_without_object_and_without_reason(self):
        spec = self.replaced(
            "| thème sombre | sans objet | la fixture n'a qu'un thème clair |", "| thème sombre | sans objet | |"
        )
        self.assert_refused_untouched(spec, "inventaire des états", "thème sombre", "raison")

    def test_refuses_a_prototyped_state_that_the_reference_does_not_list(self):
        spec = self.replaced("| vide | prototypé | empty |", "| vide | prototypé | blank |")
        self.assert_refused_untouched(spec, "inventaire des états", "blank")

    # --- refus : Validated Prototype non conforme ---------------------------------

    def test_refuses_when_an_anchor_is_removed_from_the_prototype(self):
        spec, remote = self.spec_on_altered_prototype(
            "states/content.html", '<h1 data-anchor="fixture-state">', "<h1>"
        )
        self.assert_refused_untouched(spec, "non conforme", "anchors", "states/content.html", remote=remote)

    def test_refuses_when_a_state_dataset_is_missing_from_the_prototype(self):
        spec, remote = self.spec_on_altered_prototype(
            "validated-prototype.json", '"dataset": "data/content.json"', '"dataset": "data/absent.json"'
        )
        self.assert_refused_untouched(spec, "non conforme", "datasets", remote=remote)

    # --- les Specs déjà approuvées restent approuvées ----------------------------

    def test_an_already_approved_spec_without_numbered_stories_stays_approved(self):
        description = "prose spec body approved before T07"
        digest = "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()
        self.seed_spec(description, {
            "spec_state": "APPROVED_SPEC", "approved_by": "benjamin",
            "approved_evidence": "« J'approuve »", "approved_digest": digest,
        })
        before = self.current_state()

        status = json.loads(self.invoke("bd-status", "--spec", "spec-1").stdout)
        self.assertEqual("APPROVED_SPEC", status["state"])
        self.assertFalse(status["void"])

        proc = self.bd_approve()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("already approved", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.current_state())



class SpecOutlineTest(unittest.TestCase):
    """T06 (af-cgauf8): `outline` reads, from a Spec text on stdin, what the
    publication door poses in each ticket -- the numbered user stories and
    the Testing Decisions -- with the reader `bd-approve` holds the Spec to."""

    def outline(self, text):
        return subprocess.run((str(TOOL), "outline"), input=text, text=True, capture_output=True)

    def test_outline_lists_the_numbered_user_stories_and_the_testing_decisions(self):
        proc = self.outline(FIXTURE_SPEC)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        outline = json.loads(proc.stdout)
        self.assertEqual(["1", "2", "3"], [story["number"] for story in outline["user_stories"]])
        self.assertEqual(
            "As an exploitant, I want une sonde de santé, so that je sache que le produit répond.",
            outline["user_stories"][2]["text"],
        )
        self.assertEqual(["Fixture City Oracle et ligne de commande des portes."], outline["testing_decisions"])

    def test_outline_lists_numbered_testing_decisions_one_per_seam(self):
        text = SPEC_BODY + (
            "\n## Testing Decisions\n\nSeams confirmés :\n\n"
            "1. **Oracle** : le flux entier.\n2. **Ligne de commande** de chaque porte.\n\nAucun seam nouveau.\n"
        )
        outline = json.loads(self.outline(text).stdout)
        self.assertEqual(
            ["1. **Oracle** : le flux entier.", "2. **Ligne de commande** de chaque porte."],
            outline["testing_decisions"],
        )

    def test_outline_of_a_spec_without_testing_decisions_lists_none(self):
        self.assertEqual([], json.loads(self.outline(SPEC_BODY).stdout)["testing_decisions"])

    def test_outline_refuses_a_spec_without_numbered_user_stories(self):
        proc = self.outline("prose spec body\n\n## User Stories\n\n- As an operator, I want a probe.\n")
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("user stories numérotées", json.loads(proc.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
