"""Tests for T20 (af-akkvmz, Spec af-oohx2x §"Suivre les projets", §"Étapes
d'un chantier", §"Actions opérateur"): chantiers accepted and promoted,
overlaid états, anomalies and historique -- lib/cockpit/projects/** and
lib/cockpit/ui/projects/**.

Same precedent T19 (tests/cockpit-projects-test.py) and T15 set: this
ticket's declared scope (gc.scope_paths: lib/cockpit/projects/**,
lib/cockpit/ui/projects/**, tests/cockpit-chantiers-test.py, tests/
fixtures/cockpit/chantiers/**) stops short of wiring any of this into the
running cockpit process -- every assertion here drives the pure functions
that are this ticket's whole public interface, plus one real disposable
git repo for the Promu/écart reads (the "faux clone git" of the Testing
Decisions, same shape as T19's RoadmapGitFixture) and the existing T13
fake-bd fixture (tests/fixtures/cockpit/actions/fake-bd) for Accepter's
trace write.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "chantiers"
ACTIONS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "actions"

sys.path.insert(0, str(ROOT / "lib"))

from cockpit.projects import actions as chantier_actions  # noqa: E402
from cockpit.projects import anomalies  # noqa: E402
from cockpit.projects import etat as etat_mod  # noqa: E402
from cockpit.projects import promotion  # noqa: E402
from cockpit.projects.builder import build_historique_par_projet, build_projects  # noqa: E402
from cockpit.projects.demandes import chantier_demandes  # noqa: E402
from cockpit.projects.descriptors import load_descriptors  # noqa: E402
from cockpit.projects.model import ACCEPTE, Chantier, LIVRAISON, LIVRE, PROMU, SPEC  # noqa: E402
from cockpit.projects.roadmap import RoadmapReadError  # noqa: E402
from cockpit.projects.stage import (  # noqa: E402
    abandoned_chantiers,
    build_chantiers,
    build_historique,
    cadrage_chantiers,
    convoy_chantiers,
    graphe_chantiers,
    spec_chantiers,
)
from cockpit.requests.model import QUAND_TU_VEUX  # noqa: E402
from cockpit.ui.projects.page import render_historique_section, render_projects_section  # noqa: E402

DESCRIPTORS = FIXTURES / "descriptors"


def load_fixture(name):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# État superposé (spec "états superposés")


class EtatResolveTest(unittest.TestCase):
    def test_priority_probleme_remonte_over_a_toi_de_jouer_over_bloque(self):
        self.assertEqual(
            (etat_mod.PROBLEME_REMONTE, "af-x"),
            etat_mod.resolve(
                probleme_remonte=True, probleme_remonte_cible="af-x",
                a_toi_de_jouer=True, a_toi_de_jouer_cible="af-y",
                bloque=True,
            ),
        )
        self.assertEqual(
            (etat_mod.A_TOI_DE_JOUER, "af-y"),
            etat_mod.resolve(a_toi_de_jouer=True, a_toi_de_jouer_cible="af-y", bloque=True),
        )
        self.assertEqual((etat_mod.BLOQUE, None), etat_mod.resolve(bloque=True))
        self.assertEqual((etat_mod.NORMAL, None), etat_mod.resolve())

    def test_etat_without_cible_is_a_displayed_defect(self):
        """spec .45: "qu'un état « en attente de Benjamin » sans cible
        d'action soit affiché comme un défaut" -- a safety net, exercised
        directly rather than waiting for a real production bug to trigger
        it."""
        etat, cible = etat_mod.resolve(a_toi_de_jouer=True, a_toi_de_jouer_cible=None)
        self.assertEqual(etat_mod.DEFAUT_LABEL, etat_mod.label(etat, cible))

        etat, cible = etat_mod.resolve(probleme_remonte=True, probleme_remonte_cible="")
        self.assertEqual(etat_mod.DEFAUT_LABEL, etat_mod.label(etat, cible))

    def test_bloque_and_normal_never_need_a_cible(self):
        self.assertEqual("bloqué", etat_mod.label(etat_mod.BLOQUE, None))
        self.assertEqual("normal", etat_mod.label(etat_mod.NORMAL, None))

    def test_no_refuse_state_exists(self):
        """spec: "il n'existe pas d'état Refusé"."""
        self.assertNotIn("Refusé", etat_mod.LABELS.values())
        self.assertNotIn("refuse", etat_mod.LABELS)


class StageEtatTest(unittest.TestCase):
    def test_spec_draft_is_a_toi_de_jouer(self):
        chantiers = spec_chantiers(load_fixture("spec-draft-a-toi-de-jouer.json"))
        self.assertEqual(1, len(chantiers))
        self.assertEqual(etat_mod.A_TOI_DE_JOUER, chantiers[0].etat)
        self.assertEqual("af-spec30", chantiers[0].etat_cible)

    def test_needs_benjamin_on_the_spec_bead_is_probleme_remonte(self):
        chantiers = spec_chantiers(load_fixture("spec-draft-probleme-remonte.json"))
        self.assertEqual(etat_mod.PROBLEME_REMONTE, chantiers[0].etat)
        self.assertEqual("af-spec31", chantiers[0].etat_cible)

    def test_convoy_livraison_with_no_active_ticket_is_bloque(self):
        chantiers = convoy_chantiers(load_fixture("convoy-bloque-sans-ticket.json"))
        self.assertEqual(1, len(chantiers))
        self.assertEqual(LIVRAISON, chantiers[0].stage)
        self.assertEqual(etat_mod.BLOQUE, chantiers[0].etat)

    def test_convoy_with_one_active_ticket_is_not_bloque_by_silence_alone(self):
        """spec .44: "le silence seul n'est jamais un blocage" -- one
        ticket merged and one still open/in_progress is ordinary
        Livraison, not bloqué."""
        beads = load_fixture("convoy-bloque-sans-ticket.json")
        beads.append(
            {
                "id": "af-tk23b",
                "title": "T23b — Rapport mensuel, étape 2",
                "status": "open",
                "issue_type": "task",
                "labels": ["approved-ticket-graph", "delivery-plane"],
                "metadata": {"gc.graph_digest": "sha256:ccc23"},
            }
        )
        chantiers = convoy_chantiers(beads)
        self.assertEqual(etat_mod.NORMAL, chantiers[0].etat)

    def test_mayor_first_on_a_tracked_ticket_is_bloque(self):
        chantiers = convoy_chantiers(load_fixture("convoy-bloque-mayor-first.json"))
        self.assertEqual(etat_mod.BLOQUE, chantiers[0].etat)

    def test_needs_benjamin_on_a_tracked_ticket_is_probleme_remonte_pointing_at_it(self):
        chantiers = convoy_chantiers(load_fixture("convoy-probleme-remonte.json"))
        self.assertEqual(etat_mod.PROBLEME_REMONTE, chantiers[0].etat)
        self.assertEqual("af-tk25", chantiers[0].etat_cible)

    def test_livre_non_accepte_is_a_toi_de_jouer(self):
        chantiers = convoy_chantiers(load_fixture("convoy-livre-not-accepted.json"))
        self.assertEqual(LIVRE, chantiers[0].stage)
        self.assertEqual(etat_mod.A_TOI_DE_JOUER, chantiers[0].etat)
        self.assertEqual("af-convoy20", chantiers[0].etat_cible)


# ---------------------------------------------------------------------------
# When a delivered chantier asks for an acceptance (2026-10-07): only when
# there is something to judge it on.


def _delivered(mark=False, note=None):
    beads = load_fixture("convoy-livre-not-accepted.json")
    metadata = beads[0]["metadata"]
    metadata.pop("gc.flow.mark", None)
    if mark:
        metadata["gc.flow.mark"] = "new-flow/v1"
    if note is not None:
        metadata["gc.cockpit_acceptance_note"] = note
    return beads


class AcceptanceAskedOnlyWithSomethingToJudgeTest(unittest.TestCase):
    NOTE = "À accepter après 7 jours d'usage réel sans défaut bloquant"

    def test_delivered_by_the_old_flow_asks_nothing_and_goes_to_the_history(self):
        beads = _delivered()
        self.assertEqual([], convoy_chantiers(beads))
        self.assertEqual([], chantier_demandes(convoy_chantiers(beads)))
        historique = build_historique(beads)
        self.assertEqual(1, len(historique))
        self.assertEqual(LIVRE, historique[0].stage)
        self.assertTrue(historique[0].termine)
        self.assertEqual(etat_mod.NORMAL, historique[0].etat)
        self.assertEqual("Livré avant le flux d'acceptation : rien à accepter", historique[0].detail)
        # Shown as delivered, never as accepted in Benjamin's name.
        self.assertNotIn("gc.cockpit_chantier_accepted", beads[0]["metadata"])
        html_out = render_historique_section([], historique)
        self.assertIn('data-stage="Livré"', html_out)
        self.assertIn("rien à accepter", html_out)

    def test_a_convoy_of_the_delivery_workflow_still_asks(self):
        chantiers = convoy_chantiers(_delivered(mark=True))
        self.assertEqual(LIVRE, chantiers[0].stage)
        self.assertEqual(etat_mod.A_TOI_DE_JOUER, chantiers[0].etat)
        demandes = chantier_demandes(chantiers)
        self.assertEqual(1, len(demandes))
        self.assertEqual(
            "Toi seul peux accepter ce chantier livré, ou demander sa correction.", demandes[0].pourquoi
        )

    def test_a_note_keeps_the_request_and_says_what_to_look_at(self):
        chantiers = convoy_chantiers(_delivered(note=self.NOTE))
        self.assertEqual(1, len(chantiers))
        self.assertEqual(etat_mod.A_TOI_DE_JOUER, chantiers[0].etat)
        demandes = chantier_demandes(chantiers)
        self.assertEqual(self.NOTE, demandes[0].pourquoi)
        self.assertEqual("Accepter", demandes[0].que_faire[0]["option"])

    def test_a_note_the_screen_could_not_show_falls_back_to_the_fixed_phrase(self):
        demandes = chantier_demandes(convoy_chantiers(_delivered(note="voir af-oohx2x, section 4")))
        self.assertEqual(1, len(demandes))
        self.assertEqual(
            "Toi seul peux accepter ce chantier livré, ou demander sa correction.", demandes[0].pourquoi
        )

    def test_an_accepted_old_flow_chantier_is_unchanged(self):
        beads = _delivered()
        beads[0]["metadata"]["gc.cockpit_chantier_accepted"] = "true"
        historique = build_historique(beads)
        self.assertEqual(ACCEPTE, historique[0].stage)


# ---------------------------------------------------------------------------
# Accepté / Promu (spec "Calcul d'étape des chantiers")


class AccepteStageTest(unittest.TestCase):
    def test_accepted_and_masque_is_excluded_from_the_active_list(self):
        chantiers = convoy_chantiers(load_fixture("convoy-accepted-masque.json"))
        self.assertEqual([], chantiers, "a terminé chantier is excluded from the active list")

    def test_accepted_and_masque_shows_up_in_historique(self):
        chantiers = build_historique(load_fixture("convoy-accepted-masque.json"))
        self.assertEqual(1, len(chantiers))
        self.assertEqual(ACCEPTE, chantiers[0].stage)
        self.assertTrue(chantiers[0].termine)
        self.assertTrue(chantiers[0].promu_masque)

    def test_accepted_not_masque_promu_true_is_promu_and_termine(self):
        beads = load_fixture("convoy-accepted-not-masque.json")
        promotion_results = {"af-convoy22": {"masque": False, "promu": True}}
        historique = build_historique(beads, promotion_results)
        self.assertEqual(1, len(historique))
        self.assertEqual(PROMU, historique[0].stage)
        self.assertTrue(historique[0].termine)
        self.assertFalse(historique[0].promu_masque)
        # And it is gone from the active list.
        self.assertEqual([], convoy_chantiers(beads, promotion_results))

    def test_accepted_not_masque_promu_false_is_accepte_a_toi_de_jouer_active(self):
        beads = load_fixture("convoy-accepted-not-masque.json")
        promotion_results = {"af-convoy22": {"masque": False, "promu": False}}
        active = convoy_chantiers(beads, promotion_results)
        self.assertEqual(1, len(active))
        self.assertEqual(ACCEPTE, active[0].stage)
        self.assertFalse(active[0].termine)
        self.assertEqual(etat_mod.A_TOI_DE_JOUER, active[0].etat)
        self.assertEqual([], build_historique(beads, promotion_results))

    def test_accepted_not_masque_promu_unknown_stays_accepte_active(self):
        beads = load_fixture("convoy-accepted-not-masque.json")
        promotion_results = {"af-convoy22": {"masque": False, "promu": None}}
        active = convoy_chantiers(beads, promotion_results)
        self.assertEqual(ACCEPTE, active[0].stage)
        self.assertIn("inconnue", active[0].detail)


# ---------------------------------------------------------------------------
# Accepter / "Pas bon → agent" (spec "Actions opérateur")


class FakeClock:
    def __init__(self, start=0.0):
        self._now = start

    def now(self):
        return self._now


class AccepterActionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_file = str(Path(self.tmp.name) / "state.json")
        self.calls_file = str(Path(self.tmp.name) / "calls.jsonl")
        # The click accepts a chantier of the flow before the Delivery
        # Workflow, which says what to look at; one of the new flow is not
        # accepted by it (tests below).
        beads = _delivered(note="Vérifier le résultat livré avant d'accepter")
        with open(self.state_file, "w") as fh:
            json.dump(beads, fh)
        self.bd_bin = str(ACTIONS_FIXTURES / "fake-bd")

    def _stored(self, beads):
        with open(self.state_file, "w") as fh:
            json.dump(beads, fh)

    def test_the_click_is_refused_on_a_chantier_of_the_new_flow_and_writes_nothing(self):
        self._stored(_delivered(mark=True))
        with open(self.state_file) as fh:
            before = fh.read()
        with self.assertRaises(chantier_actions.AccepterError) as refused:
            chantier_actions.accepter_chantier(
                self._bd_bin_with_env(), "af-convoy20", clock=FakeClock(100.0), confirm=True,
            )
        self.assertIn("bin/owner-answer", str(refused.exception))
        with open(self.state_file) as fh:
            self.assertEqual(before, fh.read())

    def test_a_chantier_of_the_new_flow_is_accepted_by_the_recorded_answer_not_by_the_cockpit_key(self):
        commit, pack = "a" * 40, "sha256:" + "b" * 64
        answer = {"response": "accepted", "approver": "benjamin", "words": "Accepté.", "commit": commit, "pack": pack,
                  "at": "2026-10-09T08:00:00Z"}
        # The cockpit's own key says nothing of a convoy of the new flow.
        beads = _delivered(mark=True)
        beads[0]["metadata"]["gc.cockpit_chantier_accepted"] = "true"
        self.assertEqual(LIVRE, convoy_chantiers(beads)[0].stage)
        # Benjamin's recorded answer does.
        beads = _delivered(mark=True)
        beads[0]["metadata"]["gc.flow.judgement"] = json.dumps({"verdicts": [], "answers": [answer]})
        self.assertEqual(ACCEPTE, build_historique(beads)[0].stage)
        # « constats rendus » is not an acceptance.
        returned = {**answer, "response": "findings", "findings": [{"text": "Le titre manque.", "route": "later"}]}
        beads[0]["metadata"]["gc.flow.judgement"] = json.dumps({"verdicts": [], "answers": [returned]})
        self.assertEqual(LIVRE, convoy_chantiers(beads)[0].stage)

    def _bd_bin_with_env(self):
        # cockpit.actions.trace shells out with subprocess.run([bd_bin,
        # ...]) with no explicit env -- it inherits this process's own
        # environment, so the fake's state file needs to be visible there.
        for key, value in (("FAKE_BD_STATE_FILE", self.state_file), ("FAKE_BD_CALLS_FILE", self.calls_file)):
            previous = os.environ.get(key)
            os.environ[key] = value
            self.addCleanup(lambda k=key, v=previous: os.environ.update({k: v}) if v is not None else os.environ.pop(k, None))
        return self.bd_bin

    def test_first_tap_without_confirm_is_refused_and_writes_nothing(self):
        with self.assertRaises(chantier_actions.AccepterError):
            chantier_actions.accepter_chantier(
                self._bd_bin_with_env(), "af-convoy20", clock=FakeClock(), confirm=False,
            )
        with open(self.state_file) as fh:
            beads = json.load(fh)
        bead = next(b for b in beads if b["id"] == "af-convoy20")
        self.assertNotIn("gc.cockpit_chantier_accepted", bead.get("metadata") or {})

    def test_confirmed_accepter_traces_and_flips_the_bead_to_accepte(self):
        chantier_actions.accepter_chantier(
            self._bd_bin_with_env(), "af-convoy20", clock=FakeClock(100.0), confirm=True,
        )
        with open(self.state_file) as fh:
            beads = json.load(fh)
        bead = next(b for b in beads if b["id"] == "af-convoy20")
        self.assertEqual("true", bead["metadata"]["gc.cockpit_chantier_accepted"])
        self.assertIn("Cockpit: accepter_chantier", bead["notes"])

        # Re-running stage computation on the traced bead now reads Accepté.
        chantiers = build_historique(beads)
        self.assertEqual(1, len(chantiers))
        self.assertEqual(ACCEPTE, chantiers[0].stage)

    def test_pas_bon_vers_agent_copies_a_ready_prompt_without_touching_any_graph(self):
        prompt = chantier_actions.pas_bon_vers_agent("af-convoy20", "Export CSV")
        self.assertIn("af-convoy20", prompt)
        self.assertIn("Export CSV", prompt)
        self.assertIn("consomme des tokens", prompt)
        # Pure text -- no subprocess, no bd/gc call of any kind.
        with open(self.calls_file) if Path(self.calls_file).exists() else open("/dev/null") as fh:
            self.assertEqual("", fh.read())


# ---------------------------------------------------------------------------
# Promotion git facts (spec .41, .42) -- real disposable git repos


def run_git(repo_dir, *args):
    subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


class PromotionGitFixture:
    """A disposable bare "origin" plus a read-only clone, with a `main`
    branch and a `dev` branch ahead of it by a known number of commits --
    the "faux clone git" of the Testing Decisions, same shape as T19's
    RoadmapGitFixture (tests/cockpit-projects-test.py)."""

    def __init__(self, tmp_path):
        self.origin_dir = tmp_path / "origin.git"
        self.clone_dir = tmp_path / "clone"
        self.work_dir = tmp_path / "work"
        run_git(tmp_path, "init", "--bare", str(self.origin_dir))
        run_git(self.origin_dir, "symbolic-ref", "HEAD", "refs/heads/main")
        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(self.work_dir)],
            check=True, capture_output=True, text=True,
        )
        (self.work_dir / "f.txt").write_text("main\n")
        run_git(self.work_dir, "add", "f.txt")
        run_git(self.work_dir, "commit", "-m", "init")
        run_git(self.work_dir, "push", "origin", "HEAD:refs/heads/main")
        self.main_sha = subprocess.run(
            ["git", "-C", str(self.work_dir), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

        run_git(self.work_dir, "checkout", "-b", "dev")
        self.dev_shas = []
        for i in range(3):
            (self.work_dir / "f.txt").write_text("dev %d\n" % i)
            run_git(self.work_dir, "add", "f.txt")
            run_git(self.work_dir, "commit", "-m", "dev %d" % i)
            self.dev_shas.append(
                subprocess.run(
                    ["git", "-C", str(self.work_dir), "rev-parse", "HEAD"],
                    check=True, capture_output=True, text=True,
                ).stdout.strip()
            )
        run_git(self.work_dir, "push", "origin", "HEAD:refs/heads/dev")

        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(self.clone_dir)],
            check=True, capture_output=True, text=True,
        )
        promotion.fetch(self.clone_dir)


class PromotionReadTest(unittest.TestCase):
    def test_main_commit_is_ancestor_of_main_dev_commit_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertTrue(promotion.is_ancestor(fixture.clone_dir, fixture.main_sha, "origin/main"))
            self.assertFalse(promotion.is_ancestor(fixture.clone_dir, fixture.dev_shas[-1], "origin/main"))
            self.assertTrue(promotion.is_ancestor(fixture.clone_dir, fixture.dev_shas[-1], "origin/dev"))

    def test_unknown_commit_raises_for_the_caller_to_turn_into_inconnu(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            with self.assertRaises(RoadmapReadError):
                promotion.is_ancestor(fixture.clone_dir, "0" * 40, "origin/main")

    def test_commits_ahead_counts_dev_ahead_of_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertEqual(3, promotion.commits_ahead(fixture.clone_dir, "origin/dev", "origin/main"))
            self.assertEqual(0, promotion.commits_ahead(fixture.clone_dir, "origin/main", "origin/main"))

    def test_compute_promu_true_when_every_commit_merged_to_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertTrue(promotion.compute_promu(fixture.clone_dir, [fixture.main_sha], "origin/main"))

    def test_compute_promu_false_when_a_commit_is_not_yet_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertFalse(
                promotion.compute_promu(fixture.clone_dir, [fixture.dev_shas[0]], "origin/main")
            )

    def test_compute_promu_unknown_when_a_commit_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertIsNone(promotion.compute_promu(fixture.clone_dir, ["0" * 40], "origin/main"))

    def test_compute_promu_true_for_an_empty_commit_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = PromotionGitFixture(Path(tmp))
            self.assertTrue(promotion.compute_promu(fixture.clone_dir, [], "origin/main"))


# ---------------------------------------------------------------------------
# Historique (spec .46) -- terminé + abandonné


class HistoriqueTest(unittest.TestCase):
    def test_abandoned_map_shows_up_with_its_reason(self):
        chantiers = abandoned_chantiers(load_fixture("abandoned-map.json"))
        self.assertEqual(1, len(chantiers))
        self.assertTrue(chantiers[0].abandonne)
        self.assertIn("Besoin disparu", chantiers[0].raison_abandon)
        self.assertIn("Besoin disparu", chantiers[0].detail)

    def test_abandoned_spec_shows_up_with_its_reason(self):
        chantiers = abandoned_chantiers(load_fixture("abandoned-spec.json"))
        self.assertEqual(1, len(chantiers))
        self.assertEqual(SPEC, chantiers[0].stage)
        self.assertIn("Superseded", chantiers[0].raison_abandon)

    def test_closed_bead_without_abandon_reason_is_not_abandoned(self):
        beads = load_fixture("abandoned-map.json")
        del beads[0]["metadata"]["gc.chantier_abandon_reason"]
        self.assertEqual([], abandoned_chantiers(beads))

    def test_active_chantiers_never_include_termine_or_abandonne(self):
        beads = (
            load_fixture("convoy-accepted-masque.json")
            + load_fixture("abandoned-map.json")
            + load_fixture("spec-draft-a-toi-de-jouer.json")
        )
        active = build_chantiers(beads)
        self.assertTrue(all(not c.termine and not c.abandonne for c in active))
        ids = {c.id for c in active}
        self.assertIn("af-spec30", ids)
        self.assertNotIn("af-convoy21", ids)
        self.assertNotIn("af-map40", ids)

    def test_historique_section_renders_both_kinds(self):
        descriptors = load_descriptors(DESCRIPTORS)
        beads = load_fixture("convoy-accepted-masque.json") + load_fixture("abandoned-map.json")
        projects, sans_projet = build_historique_par_projet(descriptors, beads)
        html_out = render_historique_section(projects, sans_projet)
        self.assertIn('data-state="filled"', html_out)
        self.assertIn("Accepté", html_out)
        self.assertIn("Abandonné", html_out)

    def test_empty_historique_section(self):
        html_out = render_historique_section([], [])
        self.assertIn('data-state="empty"', html_out)


# ---------------------------------------------------------------------------
# Anomalies en santé (spec "Étapes d'un chantier", .48)


class AnomaliesTest(unittest.TestCase):
    def test_convoy_closed_with_unmerged_child_is_flagged(self):
        found = anomalies.convoy_closed_with_unmerged_child(load_fixture("convoy-closed-unmerged-child.json"))
        self.assertEqual(1, len(found))
        self.assertEqual("af-convoy50", found[0]["convoy_id"])
        self.assertIn("1", found[0]["detail"])

    def test_fully_merged_closed_convoy_is_not_flagged(self):
        found = anomalies.convoy_closed_with_unmerged_child(load_fixture("convoy-livre-not-accepted.json"))
        self.assertEqual([], found)

    def test_roadmap_step_done_with_open_chantier_is_an_incoherence(self):
        chantier = Chantier(
            id="af-spec60", titre="Spec X", projet="agent-factory", stage=LIVRAISON,
            detail="", planning_run_target="A1",
        )
        steps_by_project = {"agent-factory": [{"id": "A1", "status": "done"}]}
        found = anomalies.roadmap_incoherences([chantier], steps_by_project)
        self.assertEqual(1, len(found))
        self.assertEqual("af-spec60", found[0]["chantier_id"])

    def test_chantier_targeting_a_todo_step_with_active_work_is_an_incoherence(self):
        chantier = Chantier(
            id="af-spec61", titre="Spec Y", projet="agent-factory", stage=LIVRE,
            detail="", planning_run_target="A2",
        )
        steps_by_project = {"agent-factory": [{"id": "A2", "status": "todo"}]}
        found = anomalies.roadmap_incoherences([chantier], steps_by_project)
        self.assertEqual(1, len(found))

    def test_terminated_chantier_against_a_done_step_is_not_an_incoherence(self):
        chantier = Chantier(
            id="af-spec62", titre="Spec Z", projet="agent-factory", stage=PROMU,
            detail="", planning_run_target="A1", termine=True,
        )
        steps_by_project = {"agent-factory": [{"id": "A1", "status": "done"}]}
        self.assertEqual([], anomalies.roadmap_incoherences([chantier], steps_by_project))

    def test_no_target_or_unknown_step_is_never_an_incoherence(self):
        chantier = Chantier(id="af-spec63", titre="Spec W", projet="agent-factory", stage=SPEC, detail="")
        self.assertEqual([], anomalies.roadmap_incoherences([chantier], {}))


# ---------------------------------------------------------------------------
# Livré non Accepté / Accepté non Promu as Quand tu veux demandes (spec
# §"Demandes opérateur")


class ChantierDemandesTest(unittest.TestCase):
    def test_livre_non_accepte_is_a_quand_tu_veux_demande(self):
        chantiers = convoy_chantiers(load_fixture("convoy-livre-not-accepted.json"))
        demandes = chantier_demandes(chantiers)
        self.assertEqual(1, len(demandes))
        self.assertEqual(QUAND_TU_VEUX, demandes[0].niveau)
        self.assertEqual("af-convoy20", demandes[0].id)
        # The cockpit never recommends accepting: only Benjamin, having looked
        # at the result, knows whether the delivery is good (af-mjfvwx).
        self.assertFalse(any(o["recommande"] for o in demandes[0].que_faire))

    def test_accepte_non_promu_is_a_quand_tu_veux_demande(self):
        beads = load_fixture("convoy-accepted-not-masque.json")
        promotion_results = {"af-convoy22": {"masque": False, "promu": False}}
        chantiers = convoy_chantiers(beads, promotion_results)
        demandes = chantier_demandes(chantiers)
        self.assertEqual(1, len(demandes))
        self.assertEqual(QUAND_TU_VEUX, demandes[0].niveau)

    def test_termine_or_abandonne_chantiers_produce_no_demande(self):
        beads = load_fixture("convoy-accepted-masque.json") + load_fixture("abandoned-map.json")
        all_chantiers = build_historique(beads)
        self.assertEqual([], chantier_demandes(all_chantiers))


# ---------------------------------------------------------------------------
# Rendering (spec prototype variant D)


class RenderStepperTest(unittest.TestCase):
    def test_promu_dot_is_omitted_when_masque(self):
        beads = load_fixture("convoy-accepted-masque.json")
        descriptors = load_descriptors(DESCRIPTORS)
        projects, sans_projet = build_historique_par_projet(descriptors, beads)
        html_out = render_historique_section(projects, sans_projet)
        self.assertNotIn('title="Promu"', html_out)

    def test_promu_dot_is_present_when_not_masque(self):
        beads = load_fixture("convoy-accepted-not-masque.json")
        promotion_results = {"af-convoy22": {"masque": False, "promu": False}}
        descriptors = load_descriptors(DESCRIPTORS)
        projects, sans_projet = build_projects(descriptors, beads, promotion_results=promotion_results)
        html_out = render_projects_section(projects, sans_projet)
        self.assertIn('title="Promu"', html_out)

    def test_etat_badge_is_rendered(self):
        beads = load_fixture("convoy-livre-not-accepted.json")
        descriptors = load_descriptors(DESCRIPTORS)
        projects, sans_projet = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, sans_projet)
        self.assertIn("À toi de jouer", html_out)
        self.assertIn('data-etat="a_toi_de_jouer"', html_out)

    def test_accepter_and_pas_bon_buttons_on_livre_chantier(self):
        beads = load_fixture("convoy-livre-not-accepted.json")
        descriptors = load_descriptors(DESCRIPTORS)
        projects, sans_projet = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, sans_projet)
        self.assertIn('data-action="accepter_chantier"', html_out)
        self.assertIn('data-action="pas_bon_vers_agent"', html_out)
        self.assertIn('data-bead-id="af-convoy20"', html_out)

    def test_no_action_buttons_outside_livre_stage(self):
        beads = load_fixture("convoy-bloque-sans-ticket.json")
        descriptors = load_descriptors(DESCRIPTORS)
        projects, sans_projet = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, sans_projet)
        self.assertNotIn('data-action="accepter_chantier"', html_out)

    def test_ecart_commits_rendered_per_rig(self):
        descriptors = load_descriptors(DESCRIPTORS)
        projects, _ = build_projects(descriptors, [])
        for project in projects:
            if project.project_id == "saymyname":
                project.ecart_commits_par_rig = {"saymyname-backend": 3, "saymyname-frontend": 0}
        html_out = render_projects_section(projects, [])
        self.assertIn("dev a 3 commits d'avance", html_out)
        self.assertIn("dev a 0 commits d'avance", html_out)


if __name__ == "__main__":
    unittest.main()
