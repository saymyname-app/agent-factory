#!/usr/bin/env python3
# ci: over-ceiling — already above the ceiling when it was set on 2026-10-10 (CI01, af-q9urgr) but not measured then: the file is newer than the durations recorded on 2026-10-09
"""bin/outcome-promote (T30, Spec §9 and §11), on a fake tracker state and
on the Delivered Outcome of the delivery fixture, with its remote: what
follows « accepté » and « abandonné ». One test per pass and per refusal;
each refusal re-reads the tracker, the Evidence Packs and the protected
branch to prove nothing was written and nothing was merged."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "outcome-promote"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


answers = load("owner-answer-test.py")
gate = answers.gate
CONVOY, PLAIN_CONVOY, INTEGRATION = answers.CONVOY, answers.PLAIN_CONVOY, answers.INTEGRATION
PROTECTED, APP = gate.PROTECTED, gate.APP
EXIT_REFUSED, EXIT_UNRULED, EXIT_NOT_NEW_FLOW = 1, 3, 4
REASON = "Le besoin a disparu."


class OutcomePromoteTest(answers.OwnerAnswerTest):
    # --- harness ------------------------------------------------------------

    def promote(self, command="run", *args, convoy=CONVOY, env=None):
        given = ("--profile", self.profile) if command == "run" else ()
        proc = self.run_cmd(TOOL, command, convoy, "--repo", self.repo, *given, *args, env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def accepted(self):
        """The Outcome Benjamin accepted: the judged commit and the tip the
        protected branch had."""
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("accepté", commit, digest))
        return commit, self.remote_tip(PROTECTED)

    def abandoned(self):
        commit, _ = self.delivered_dossier()
        self.passed(self.respond("abandonné", None, None, "--reason", REASON, words=None))
        return commit, self.remote_tip(PROTECTED)

    def break_the_tests(self):
        """The protected branch receives, from elsewhere, a commit that makes
        the regression command of the project red."""
        def edit(tree):
            app = tree / APP
            app.write_text(app.read_text().replace('<p data-anchor="fixture-generated-at">', "<p>"))
        return self.commit_to(PROTECTED, edit, "la date perd son ancre")

    def parents(self, commit):
        out = subprocess.run(("git", "--git-dir", str(self.origin), "rev-list", "--parents", "-n", "1", commit),
                             env=self.env, text=True, capture_output=True).stdout.split()
        return out[1:]

    def first_parent_commits(self, old, new):
        out = subprocess.run(("git", "--git-dir", str(self.origin), "rev-list", "--first-parent", f"{old}..{new}"),
                             env=self.env, text=True, capture_output=True).stdout.split()
        return out

    def convoy(self, expect=0):
        return self.show(expect)["convoy"]

    def refused_and_nothing_merged(self, call, main):
        error = self.refusal_of(call)
        self.assertEqual(main, self.remote_tip(PROTECTED))
        return error

    def assert_red(self, cause, commit, main):
        """Nothing merged; the acceptance voided; the red on the integration
        branch, for the pass to publish its repair; Delivered withdrawn."""
        status, answer = self.promote()
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual((False, cause), (answer["promoted"], answer["cause"]))
        self.assertIn("rien n'est fusionné", answer["error"])
        self.assertEqual(main, self.remote_tip(PROTECTED))
        shown = self.convoy()
        last = shown["judgement"]["answers"][-1]
        self.assertEqual(("accepted", cause, commit), (last["response"], last["voided"]["cause"], last["commit"]))
        self.assertEqual((None, None, None, "open"),
                         (shown["delivered"], shown["acceptance"], shown["promotion"], shown["status"]))
        self.assertIsNotNone(shown["integration_red"])
        self.assertIsNone(shown["integration_red"].get("repair"))
        return answer

    # --- « accepté » -----------------------------------------------------------

    def test_nothing_of_the_convoy_is_in_the_protected_branch_before_accepted_then_one_merge_and_the_convoy_closes(self):
        commit, main = self.accepted()
        self.assertFalse(self.holds(commit, main))
        self.assertEqual("delivered", self.convoy()["outcome"])
        self.assertEqual((0, "merge"), (self.promote("check")[0], self.promote("check")[1]["due"]))

        answer = self.passed(self.promote())

        merged = self.remote_tip(PROTECTED)
        self.assertEqual((True, merged, True, "accepted"),
                         (answer["promoted"], answer["merged"], answer["closed"], answer["how"]))
        self.assertNotIn("pending", answer)
        self.assertEqual([main, commit], self.parents(merged))
        self.assertEqual([merged], self.first_parent_commits(main, merged))
        shown = self.convoy()
        self.assertEqual(("closed", [], "accepted"), (shown["status"], shown["unruled"], shown["outcome"]))
        self.assertEqual((commit, merged, main, commit), tuple(shown["promotion"][k] for k in ("judged", "merged", "protected", "tip")))
        self.assertEqual(("accepted", answers.WORDS, answers.APPROVER),
                         tuple(shown["closed"][k] for k in ("how", "said", "approver")))
        self.assertEqual(commit, self.remote_tip(INTEGRATION))

    def test_the_dossier_notes_the_judged_and_the_merged_commit_and_the_judged_page_keeps_its_bytes(self):
        commit, _ = self.accepted()
        pack = self.convoy()["evidence_pack"]
        page = (Path(pack["path"]) / "index.html").read_bytes()

        self.passed(self.promote())

        merged = self.remote_tip(PROTECTED)
        note = (Path(pack["path"]) / "fusion.html").read_text()
        self.assertIn(commit, note)
        self.assertIn(merged, note)
        self.assertIn("Commit jugé", note)
        self.assertIn("Commit fusionné", note)
        self.assertIn(answers.WORDS.replace("'", "&#x27;"), note)
        self.assertEqual(page, (Path(pack["path"]) / "index.html").read_bytes())

    def test_the_spec_and_the_draft_close_with_the_accepted_convoy_and_the_evidence_store_is_purged(self):
        self.accepted()
        beads = json.loads(self.tracker.read_text())["beads"]
        spec = beads[CONVOY]["metadata"]["gc.spec_id"]
        beads[CONVOY]["metadata"]["gc.artifact_id"] = "fx-draft"
        beads["fx-draft"] = {"title": "brouillon de graphe", "status": "open", "issue_type": "task", "metadata": {}}
        self.tracker.write_text(json.dumps({"beads": beads}))
        self.assertTrue(self.store_files())

        answer = self.passed(self.promote())

        beads = json.loads(self.tracker.read_text())["beads"]
        self.assertEqual(("closed", "closed", "closed"),
                         (beads[CONVOY]["status"], beads[spec]["status"], beads["fx-draft"]["status"]))
        self.assertEqual([], self.store_files())
        self.assertGreater(answer["purged"], 0)

    def test_a_protected_branch_that_moved_is_taken_up_the_controls_replayed_green_and_both_commits_are_kept(self):
        commit, _ = self.accepted()
        moved = self.note(PROTECTED)

        answer = self.passed(self.promote())

        merged, tip = self.remote_tip(PROTECTED), self.remote_tip(INTEGRATION)
        self.assertEqual([commit, moved], self.parents(tip))
        self.assertEqual([moved, tip], self.parents(merged))
        self.assertEqual([merged], self.first_parent_commits(moved, merged))
        promotion = self.convoy()["promotion"]
        self.assertEqual((commit, merged, moved, tip), tuple(promotion[k] for k in ("judged", "merged", "protected", "tip")))
        self.assertEqual((commit, "accepted"), (answer["judged"], self.convoy()["outcome"]))
        note = (Path(self.convoy()["evidence_pack"]["path"]) / "fusion.html").read_text()
        self.assertIn(commit, note)
        self.assertIn(merged, note)

    def test_red_controls_on_the_taken_up_branch_merge_nothing_and_void_the_acceptance(self):
        commit, _ = self.accepted()
        broken = self.break_the_tests()

        answer = self.assert_red("regression", commit, broken)

        self.assertEqual(commit, self.remote_tip(INTEGRATION))
        self.assertIn("control", answer["red"])

    def test_a_conflict_with_the_protected_branch_merges_nothing_and_voids_the_acceptance(self):
        commit, _ = self.accepted()
        # The protected branch receives a file the convoy also wrote.
        written = f"docs/{answers.packs.gate.SLICE}.md"
        clash = self.commit_to(PROTECTED, lambda tree: self.write(tree / written, "écrit ailleurs\n"), "le même fichier, ailleurs")

        answer = self.assert_red("conflict", commit, clash)

        self.assertIn("conflit", answer["red"]["control"])
        self.assertEqual(commit, self.remote_tip(INTEGRATION))

    def test_benjamin_answers_again_after_a_voided_acceptance(self):
        commit, digest = self.accepted()
        self.break_the_tests()
        self.promote()

        status, answer = self.respond("accepté", commit, digest)

        # Not refused as following an accepted Outcome: it is no longer Delivered.
        self.assertEqual(EXIT_REFUSED, status)
        self.assertNotIn("rien ne le rouvre", answer["error"])
        self.assertIn("Delivered", answer["error"])

    # --- « abandonné » ---------------------------------------------------------

    def test_an_abandoned_convoy_closes_with_its_reason_nothing_is_merged_and_the_branch_stays(self):
        commit, main = self.abandoned()
        store = self.store_files()

        answer = self.passed(self.promote())

        self.assertEqual((False, None, True, "abandoned", REASON),
                         tuple(answer[k] for k in ("promoted", "merged", "closed", "how", "said")))
        self.assertEqual(main, self.remote_tip(PROTECTED))
        self.assertEqual(commit, self.remote_tip(INTEGRATION))
        shown = self.convoy()
        self.assertEqual(("closed", [], "abandoned", None), (shown["status"], shown["unruled"], shown["outcome"], shown["promotion"]))
        self.assertEqual(store, self.store_files())

    # --- refusals ----------------------------------------------------------------

    def test_no_merge_without_an_accepted_answer(self):
        self.delivered_dossier()
        main = self.remote_tip(PROTECTED)

        error = self.refused_and_nothing_merged(self.promote, main)

        self.assertIn("ni « accepté » ni « abandonné »", error)
        self.assertEqual("nothing", self.promote("check")[1]["due"])

    def test_no_merge_of_a_tip_that_is_not_the_accepted_commit(self):
        commit, main = self.accepted()
        tip = self.note(INTEGRATION)

        error = self.refused_and_nothing_merged(self.promote, main)

        self.assertIn(f"aucun « accepté » n'est enregistré pour la pointe {tip[:12]}", error)
        self.assertIn(commit[:12], error)

    def test_an_agent_session_does_not_merge_nor_close(self):
        _, main = self.accepted()

        for identity in ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID"):
            with self.subTest(identity=identity):
                error = self.refused_and_nothing_merged(
                    lambda: self.promote(env={**self.env, identity: "delivery-author-1"}), main)
                self.assertIn("aucun agent", error)

    def test_a_convoy_without_the_mark_is_not_touched(self):
        before = self.everything()

        status, answer = self.promote(convoy=PLAIN_CONVOY)

        self.assertEqual((EXIT_NOT_NEW_FLOW, False), (status, answer["new_flow"]))
        self.assertEqual(before, self.everything())

    # --- nothing reopens an Accepted Outcome ---------------------------------------

    def test_a_second_run_writes_nothing_and_merges_nothing(self):
        self.accepted()
        self.passed(self.promote())
        merged, before = self.remote_tip(PROTECTED), self.tracker.read_bytes()

        answer = self.passed(self.promote())

        self.assertTrue(answer["done"])
        self.assertEqual((merged, before), (self.remote_tip(PROTECTED), self.tracker.read_bytes()))
        self.assertEqual("nothing", self.promote("check")[1]["due"])

    def test_the_commands_of_the_flow_refuse_to_reopen_an_accepted_outcome_and_point_to_new_work(self):
        commit, _ = self.accepted()
        digest = self.convoy()["delivered"]["pack"]
        self.passed(self.promote())
        ticket = self.show()["tickets"][0]["id"]

        for name, call in (
                ("owner-answer", lambda: self.respond("constats rendus", commit, digest, "--findings",
                                                      self.findings_file(answers.cited()))),
                ("spec-end", lambda: self.outcome(gate.TOOL, "run", "--profile", self.profile)),
                ("open-resume", lambda: self.outcome(answers.packs.gate.STATE_TOOL, "open-resume", ticket, repo=False)),
                ("mark", lambda: self.outcome(answers.packs.gate.STATE_TOOL, "mark", repo=False))):
            with self.subTest(command=name):
                before, merged = self.tracker.read_bytes(), self.remote_tip(PROTECTED)
                status, answer = call()
                self.assertEqual(EXIT_REFUSED, status, answer)
                self.assertIn("rien ne le rouvre", answer["error"])
                self.assertIn("travail nouveau", answer["error"])
                self.assertEqual((before, merged), (self.tracker.read_bytes(), self.remote_tip(PROTECTED)))

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def outcome(self, tool, command, *args, repo=True):
        proc = self.run_cmd(tool, command, CONVOY, *(("--repo", self.repo) if repo else ()), *args)
        return proc.returncode, json.loads(proc.stdout)


for inherited in (answers.OwnerAnswerTest, answers.sessions.AcceptanceSessionTest):
    for name in dir(inherited):
        if name.startswith("test_") and name not in OutcomePromoteTest.__dict__:
            setattr(OutcomePromoteTest, name, None)


if __name__ == "__main__":
    unittest.main()
