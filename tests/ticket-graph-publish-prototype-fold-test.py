#!/usr/bin/env python3
"""The publication door and the patch door on the interface part of the
entry contract of the new flow (T36, af-2nmcxw; Spec af-wf4w5r §2 and §3,
Testing Decisions seam 2): the reference of the Spec's Validated Prototype
posed in each interface ticket, and the Prototype Fold every other interface
ticket waits for. Only the command lines are exercised
(bin/ticket-graph-publish, bin/convoy-state), on a fake tracker state: one
test per refusal and per pass, each refusal re-reading the tracker to prove
nothing was written. The harness is the one of
tests/ticket-graph-publish-coverage-test.py."""

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_loaded = importlib.util.spec_from_file_location(
    "ticket_graph_publish_coverage_harness", ROOT / "tests" / "ticket-graph-publish-coverage-test.py")
_coverage = importlib.util.module_from_spec(_loaded)
_loaded.loader.exec_module(_coverage)
Harness, FIXTURE_SPEC, MARK = _coverage.Harness, _coverage.FIXTURE_SPEC, _coverage.MARK

BRANCH = "prototype/delivery-fixture-city"
COMMIT = "dfdd34f50623661f6644524b6489342cdbbdee19"
PROTOTYPE_PATH = "tests/fixtures/delivery-fixture-city/prototype"
REFERENCE = (f"- branche : {BRANCH}", f"- commit : {COMMIT}", f"- chemin : {PROTOTYPE_PATH}", "- états : empty, content")
POINTER = "## Validated Prototype"

# The Spec of the fixture with no interface: no story describes one, and it
# names no Validated Prototype.
SPEC_WITHOUT_INTERFACE = (
    FIXTURE_SPEC.split("## Validated Prototype")[0] + "## Implementation Decisions"
    + FIXTURE_SPEC.split("## Implementation Decisions")[1]
).replace(" [interface]", "")

# An interface slice a graph may carry besides the Prototype Fold (T2).
SLICE = {
    "id": "T5", "kind": "vertical_slice", "title": "La page d'accueil affiche l'heure de génération",
    "blocked_by": ["T2"], "target_rigs": ["fixture_city"],
    "what_it_delivers": "La page d'accueil affiche l'heure de génération du jeu de données.",
    "demonstration_line": "Sur le produit lancé, la page d'accueil (GET /) affiche l'heure de génération.",
    "user_stories": [1],
    "acceptance_criteria": [{
        "entry_point": "GET / sur le produit lancé avec le jeu de données « contenu »",
        "observable": "la région « état » affiche le libellé « Généré à 12:00 »",
        "false_if": "la région « état » n'affiche aucune heure",
    }],
}
REPAIR = {
    "id": "R1", "kind": "repair", "title": "La liste retrouve son troisième élément",
    "blocked_by": [], "target_rigs": ["fixture_city"],
    "what_it_delivers": "La page affiche de nouveau les trois éléments.",
    "restores": {"kind": "user_story", "ref": "user story 2"},
    "demonstration_line": "Sur le produit lancé, la page (GET /) affiche de nouveau « Gamma ».",
    "acceptance_criteria": [{
        "entry_point": "GET / sur le produit lancé", "observable": "la région « liste » contient « Gamma »",
        "false_if": "« Gamma » manque",
    }],
}


class FoldHarness(Harness):
    def with_ticket(self, added, **changes):
        draft = self.conformant()
        draft["tickets"].append({**copy.deepcopy(added), **changes})
        return draft

    def description(self, bead_id):
        return self.beads()[bead_id]["description"]

    def prototype_pointer(self, bead_id):
        """The Validated Prototype section the door posed in a ticket."""
        text = self.description(bead_id)
        self.assertIn(POINTER, text)
        return text.split(POINTER)[1].split("\n## ")[0]

    def waits_for(self, ids, key, blocker):
        """Whether the published ticket `key` is blocked, directly or
        through another ticket, by `blocker` -- read on the tracker."""
        beads = self.beads()
        stack, seen = [key], set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            blockers = [b for b in beads[ids[current]]["metadata"].get("gc.blocked_by", "").split(",") if b]
            if blocker in blockers:
                return True
            stack.extend(blockers)
        return False


class PrototypeFoldPublicationTest(FoldHarness):
    def refused(self, *mentions):
        proc = self.assert_refused_and_nothing_written(self.door, "rien n'est écrit", *mentions)
        self.assertEqual({"draft-1", "spec-1"}, set(self.beads()))
        return proc

    # --- AC1: an interface graph without Prototype Fold is refused -------------

    def test_refuses_an_interface_graph_without_prototype_fold_and_names_the_validated_prototype(self):
        # Demonstration line of the ticket, first part.
        draft = self.conformant()
        del self.ticket(draft, "T2")["prototype_fold"]
        self.seed(draft)

        proc = self.refused()
        lines = self.refusal_lines(proc, "graphe")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("Prototype Fold", lines[0])
        for named in (PROTOTYPE_PATH, BRANCH, COMMIT):
            self.assertIn(named, lines[0])
        # The interface tickets left without a Fold are named too.
        self.assertIn("T2, T3", lines[0])

    def test_refuses_two_prototype_folds_for_one_validated_prototype(self):
        self.seed(self.with_ticket(SLICE, prototype_fold=True))

        proc = self.refused()
        for key in ("T2", "T5"):
            self.assertTrue(any("un seul" in line for line in self.refusal_lines(proc, key)), proc.stderr)

    def test_refuses_a_prototype_fold_that_is_not_a_vertical_slice(self):
        for key, kind in (("T1", "prefactoring"), ("T3", "repair")):
            with self.subTest(kind=kind):
                draft = self.conformant()
                self.ticket(draft, key)["prototype_fold"] = True
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(
                    any("prototype_fold" in line and "vertical_slice" in line for line in self.refusal_lines(proc, key)),
                    proc.stderr)

    def test_refuses_a_malformed_prototype_fold(self):
        for value in ("oui", False, 1, PROTOTYPE_PATH):
            with self.subTest(prototype_fold=value):
                draft = self.conformant()
                self.ticket(draft, "T2")["prototype_fold"] = value
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(any("prototype_fold" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)

    def test_refuses_a_prototype_fold_when_the_spec_names_no_validated_prototype(self):
        self.seed(self.conformant())
        self.amend_spec(SPEC_WITHOUT_INTERFACE)

        proc = self.refused()
        lines = self.refusal_lines(proc, "T2")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("Validated Prototype", lines[0])

    # --- AC2: every other interface ticket waits for the Prototype Fold --------

    def test_refuses_an_interface_slice_that_does_not_wait_for_the_prototype_fold(self):
        self.seed(self.with_ticket(SLICE, blocked_by=[]))

        proc = self.refused()
        lines = self.refusal_lines(proc, "T5")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("Prototype Fold T2", lines[0])
        for other in ("T1", "T2", "T3", "T4", "graphe"):
            self.assertEqual([], self.refusal_lines(proc, other), other)

    def test_refuses_an_interface_repair_that_does_not_wait_for_the_prototype_fold(self):
        draft = self.conformant()
        self.ticket(draft, "T3")["blocked_by"] = []
        self.seed(draft)

        proc = self.refused()
        self.assertTrue(any("Prototype Fold T2" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    def test_refuses_a_repair_of_an_anchor_that_does_not_wait_for_the_prototype_fold(self):
        draft = self.conformant()
        self.ticket(draft, "T3").update(blocked_by=[], restores={"kind": "anchor", "ref": "liste"})
        self.seed(draft)

        proc = self.refused()
        self.assertTrue(any("Prototype Fold T2" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    def test_publishes_an_interface_ticket_that_waits_for_the_fold_through_another_ticket(self):
        self.seed(self.with_ticket(SLICE, blocked_by=["T3"]))  # T3 waits for T2, the Fold

        ids = self.published()["ids"]
        self.assertTrue(self.waits_for(ids, "T5", "T2"))

    def test_a_ticket_that_is_not_an_interface_ticket_does_not_wait_for_the_fold(self):
        # T4 covers story 3, which describes no interface: it is ready with the Fold.
        self.seed(self.conformant())
        ids = self.published()["ids"]
        self.assertFalse(self.waits_for(ids, "T4", "T2"))
        self.assertNotIn(POINTER, self.description(ids["T4"]))

    # --- AC3: the door poses the reference frozen in the Spec ------------------

    def test_published_interface_tickets_show_the_reference_of_the_validated_prototype(self):
        # Demonstration line of the ticket, second part.
        self.seed(self.with_ticket(SLICE))
        ids = self.published()["ids"]

        for key in ("T2", "T3", "T5"):
            posed = self.prototype_pointer(ids[key])
            for line in REFERENCE:
                self.assertIn(line, posed.splitlines(), key)
        for key in ("T1", "T4"):
            self.assertNotIn(POINTER, self.description(ids[key]), key)
        self.assertNotIn(COMMIT, self.dump(self.conformant()))  # never written by hand

    def test_the_fold_and_the_tickets_that_wait_for_it_say_which_ticket_is_the_fold(self):
        self.seed(self.conformant())
        ids = self.published()["ids"]

        self.assertIn("Prototype Fold : ce ticket", self.prototype_pointer(ids["T2"]))
        self.assertIn("Prototype Fold : T2", self.prototype_pointer(ids["T3"]))

    def test_the_reference_posed_is_the_one_of_the_spec_the_draft_slices(self):
        other_commit = "0123456789abcdef0123456789abcdef01234567"
        self.seed(self.conformant())
        self.amend_spec(
            FIXTURE_SPEC.replace(COMMIT, other_commit).replace("`empty`, `content`", "`content`, `empty`")
            .replace(PROTOTYPE_PATH, "prototypes/accueil"))
        ids = self.published()["ids"]

        posed = self.prototype_pointer(ids["T3"]).splitlines()
        self.assertIn(f"- commit : {other_commit}", posed)
        self.assertIn("- chemin : prototypes/accueil", posed)
        self.assertIn("- états : content, empty", posed)
        self.assertNotIn(COMMIT, self.description(ids["T3"]))

    def test_the_fold_is_kept_by_the_state_command(self):
        self.seed(self.conformant())
        result = self.published()
        convoy = result["ids"]["_convoy"]

        self.assertFalse(self.convoy_state(convoy)["unruled"])
        self.assertIs(True, self.shown_ticket(convoy, result["ids"]["T2"])["prototype_fold"])
        for key in ("T1", "T3", "T4"):
            self.assertIs(False, self.shown_ticket(convoy, result["ids"][key])["prototype_fold"], key)

    # --- AC4: among the interface tickets, only the Fold is ready --------------

    def test_every_published_interface_ticket_but_the_fold_waits_for_it(self):
        # Demonstration line of the ticket, last part (bd ready on the real
        # tracker: tests/ticket-graph-publish-new-flow-real-tracker-test.sh).
        self.seed(self.with_ticket(SLICE, blocked_by=["T3"]))
        ids = self.published()["ids"]

        for key in ("T3", "T5"):
            self.assertTrue(self.waits_for(ids, key, "T2"), key)
        for interface in ("T2", "T3", "T5"):
            self.assertFalse(self.waits_for(ids, "T2", interface))

    # --- AC5: a Spec without interface is sliced without Prototype Fold --------

    def test_graph_of_a_spec_without_interface_is_published_without_prototype_fold(self):
        draft = self.conformant()
        del self.ticket(draft, "T2")["prototype_fold"]
        self.seed(draft)
        self.amend_spec(SPEC_WITHOUT_INTERFACE)

        result = self.published()
        self.assertEqual(MARK, result["flow_contract"])
        for key in ("T1", "T2", "T3", "T4"):
            self.assertNotIn(POINTER, self.description(result["ids"][key]), key)
            self.assertIs(False, self.shown_ticket(result["ids"]["_convoy"], result["ids"][key])["prototype_fold"])

    def test_interface_stories_without_validated_prototype_need_no_fold(self):
        # Spec af-wf4w5r, Further Notes: an interface whose states are all
        # « non prototypés » has no Validated Prototype to fold.
        draft = self.conformant()
        del self.ticket(draft, "T2")["prototype_fold"]
        self.seed(draft)
        self.amend_spec(SPEC_WITHOUT_INTERFACE.replace(
            "so that je puisse les lire.", "so that je puisse les lire. [interface]"))

        result = self.published()
        self.assertNotIn(POINTER, self.description(result["ids"]["T2"]))


class PrototypeFoldPatchTest(FoldHarness):
    """The same rules on the graph that results from a patch."""

    def setUp(self):
        super().setUp()
        self.seed(self.conformant())
        self.first = self.published()
        self.ids = self.first["ids"]
        self.convoy = self.ids["_convoy"]

    def propose(self, draft, approved=True):
        self.add_draft("draft-2", draft, approved=approved, revises_digest=self.first["graph_digest"])

    def refused(self, *mentions, extra=()):
        return self.assert_refused_and_nothing_written(lambda: self.patch(extra=extra), "rien n'est écrit", *mentions)

    def test_refuses_an_added_interface_ticket_that_does_not_wait_for_the_prototype_fold(self):
        self.propose(self.with_ticket(SLICE, blocked_by=[]))

        proc = self.refused()
        self.assertTrue(any("Prototype Fold T2" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)

    def test_added_interface_ticket_that_waits_for_the_fold_shows_the_reference(self):
        self.propose(self.with_ticket(SLICE))

        result = self.patched()
        posed = self.prototype_pointer(result["ids"]["T5"])
        for line in REFERENCE:
            self.assertIn(line, posed.splitlines())
        self.assertIn("Prototype Fold : T2", posed)
        self.assertFalse(self.convoy_state(self.convoy)["unruled"])

    def test_added_repair_needs_no_edge_to_a_prototype_fold_already_delivered(self):
        # A repair written at the end of the Spec restores an interface story
        # once the Fold is merged: there is nothing left to wait for.
        self.state_tool("record-gate", self.convoy, self.ids["T2"], "--gate", "ticket_end", "--commit", "a" * 40)
        self.edit_bead(self.ids["T2"], status="closed")
        draft = self.conformant()
        draft["tickets"] = [copy.deepcopy(REPAIR)]
        self.propose(draft, approved=False)

        result = self.patched()
        self.assertIn(REFERENCE[1], self.prototype_pointer(result["ids"]["R1"]).splitlines())

    def test_repair_the_prototype_fold_waits_for_does_not_wait_for_it(self):
        # Code blocks the Fold behind the repair that unblocks it: the repair
        # comes first, and still shows the reference it works against.
        draft = self.conformant()
        draft["tickets"] = [t for t in draft["tickets"] if t["id"] in ("T1", "T2")] + [copy.deepcopy(REPAIR)]
        self.ticket(draft, "T2")["blocked_by"] = ["T1", "R1"]
        self.propose(draft, approved=False)

        result = self.patched()
        self.assertIn(REFERENCE[1], self.prototype_pointer(result["ids"]["R1"]).splitlines())

    def test_added_repair_waits_for_a_prototype_fold_still_open(self):
        draft = self.conformant()
        draft["tickets"] = [copy.deepcopy(REPAIR)]
        self.propose(draft, approved=False)

        proc = self.refused()
        self.assertTrue(any("Prototype Fold T2" in line for line in self.refusal_lines(proc, "R1")), proc.stderr)

    def test_refuses_a_patch_that_changes_which_ticket_is_the_prototype_fold(self):
        draft = self.conformant()
        del self.ticket(draft, "T2")["prototype_fold"]
        self.propose(draft)

        proc = self.refused()
        self.assertTrue(
            any("prototype_fold" in line and "gelé" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)

    def test_refuses_a_patch_that_adds_a_second_prototype_fold(self):
        self.propose(self.with_ticket(SLICE, prototype_fold=True))

        proc = self.refused()
        self.assertTrue(any("un seul" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)


if __name__ == "__main__":
    unittest.main()
