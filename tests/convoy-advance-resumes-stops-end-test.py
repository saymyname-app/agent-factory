#!/usr/bin/env python3
# ci: over-ceiling — second half of tests/convoy-advance-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); what is left is the passes each case verifies
"""bin/convoy-advance on a fake tracker state, the second half of the cases
(Spec CI01, af-q9urgr: tests/convoy-advance-test.py was the longest file of
the battery, cut in two files of about the same duration).

The harness is the one of tests/convoy-advance-test.py, loaded from there:
the seeded tracker, the settings, the stand-ins of the doors and the set-up
helpers. This file holds the cases of the resumes and the parked tickets
(T20), of the stops of the convoy (T21, T45) and of the end of the Spec
(T23, T24, T25); the first holds the starts, the ceiling, the factory
incidents, the dispatch door, the merges and the controls before them.

Since af-vqew1x the cases of the end of the Spec (T23, T24, T25) are in
tests/convoy-advance-end-of-spec-test.py."""

import importlib.machinery
import importlib.util
import hashlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: unittest collects the test classes
# named at the top of a file, and the cases of the first half run there.
first = load("convoy-advance-test.py")
TOOL = first.TOOL
STATE = first.STATE
ESCALATION = first.ESCALATION
CONVOY = first.CONVOY
OTHER = first.OTHER
PLAIN = first.PLAIN
T1 = first.T1
T2 = first.T2
T3 = first.T3
EXIT_REFUSED = first.EXIT_REFUSED
EXIT_UNRULED = first.EXIT_UNRULED
EXIT_NOT_NEW_FLOW = first.EXIT_NOT_NEW_FLOW
ticket = first.ticket
session = first.session

AUTHORIZED_TICKET = "af-ocz64w"
AUTHORIZED_COMMIT = "e62cb740dc8d134f26758c24fea4634d3787ffe8"
AUTHORIZED_RESPONSE_AT = "2026-11-06T16:22:23Z"
AUTHORIZED_FILES = [
    "tests/cockpit-criteria/commands/home-result-essai-test.py",
    "tests/cockpit-criteria/commands/result_trial.py",
]
AUTHORIZED_REF = "authorization:af-atrg8o"

RETURNED_RELEASE_ENV = "CONVOY_ADVANCE_TEST_RETURNED_RELEASE"
RETURNED_RELEASE_MAINTENANCE = "fx-returned-release"
RETURNED_RELEASE_REPAIR = "fx-r9"
RETURNED_RELEASE_EVIDENCE = "sha256:46fe2ee17aa730ba261b6a8bd940f17d1c3cb7eb0a66607eebf4051b3fb7fedd"
RETURNED_RESULT_RELEASE_ENV = "CONVOY_ADVANCE_TEST_RETURNED_RESULT_RELEASE"
RETURNED_RESULT_RELEASE_REPAIR = "fx-c59"
C2B_RELEASE_ENV = "CONVOY_ADVANCE_TEST_C2B_RELEASE"
C2B_RELEASE_REPAIR = "fx-c2b-repair"
C2B_RELEASE_MIGRATION = "fx-c2b-migration"
C2B_RESULT_RELEASE_ENV = "CONVOY_ADVANCE_TEST_C2B_RESULT_RELEASE"
C2B_RESULT_RELEASE_REPAIR = "fx-c58"
C2B_EVALUATION_RECOVERY_ENV = "CONVOY_ADVANCE_TEST_C2B_EVALUATION_RECOVERY"
C2B_EVALUATION_RECOVERY_REPAIR = "fx-c63"
R8_CLOSE_RELEASE_ENV = "CONVOY_ADVANCE_TEST_R8_CLOSE_RELEASE"
R8_CLOSE_RELEASE_REPAIR = "fx-r8close"
R8_CLOSE_CURRENT_REPAIR = "fx-r8current"
R6_R7_WITHDRAWAL_ENV = "CONVOY_ADVANCE_TEST_R6_R7_WITHDRAWAL"
R6_R7_WITHDRAWAL_REPAIR = "fx-r6-r7-withdrawal"


def delivered(number, head, merge):
    return {
        "gc.delivery_contract": "pr-ci-merged-v1",
        "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
        "gc.github_repo": "example/factory", "gc.pr_number": number,
        "gc.pr_head": head, "gc.merge_commit": merge,
        "gc.pr_url": f"https://github.com/example/factory/pull/{number}",
        "pr_number": number, "merge_result": "merged", "merged_sha": merge,
        "merged_target": "main", "gc.required_ci_workflow": "Factory CI",
        "gc.ci_run_id": number, "gc.ci_head_sha": head, "gc.ci_conclusion": "success",
    }


class ConvoyAdvanceTest(first.ConvoyAdvanceHarness):
    # --- resumes counted and bounded, parked tickets, one grouped request (T20) ---

    def earlier_resumes(self, cause, count, ticket_id=T1, refs=None):
        """`count` resumes of `cause` the ticket took long before, written
        under its recorded ones, the counter with them (ADR-0030 L2: the
        bound is per cause)."""
        metadata = self.bead(ticket_id)["metadata"]
        record = json.loads(metadata.get("gc.flow.resume") or '{"entries": []}')
        refs = refs or [f"earlier:{n}" for n in range(count)]
        earlier = [{"cause": cause, "ref": refs[n], "session": None, "exit": None, "launches": [],
                    "at": "2000-01-01T00:00:00Z"} for n in range(count)]
        record["entries"] = earlier + record["entries"]
        metadata["gc.flow.resume"] = json.dumps(record)
        metadata["gc.flow.counter.resumes"] += count
        self.edit(ticket_id, metadata=metadata)

    def exact_returned_release(self):
        """The shape of D's one authorized release, on a disposable graph."""
        self.integrated()
        self.resumable()
        self.advance(CONVOY)
        self.taken(T1, "auteur-returned")

        self.git("checkout", "-q", "--detach", self.INTEGRATION)
        (self.root / "r9.md").write_text("repair R9\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "repair R9")
        repair_commit = self.git("rev-parse", "HEAD")
        (self.root / "integration-tip.md").write_text("integration after R9\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "integration after R9")
        integration_tip = self.git("rev-parse", "HEAD")
        self.returned_release_unrelated = self.git(
            "commit-tree", f"{integration_tip}^{{tree}}", "-m", "unrelated integration history")
        self.git("update-ref", f"refs/heads/{self.INTEGRATION}", integration_tip)
        self.git("checkout", "-q", "--detach", "main")

        ticket_commit = self.finished(T1)
        self.git("checkout", "-q", "--detach", integration_tip)
        self.git("merge", "-q", "--no-ff", "-m", "returned merge candidate", f"ticket/{T1}")
        merge_commit = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", "main")
        self.run_ok(STATE, "set-merge", CONVOY, T1, "--outcome", "red", "--ticket-commit", ticket_commit,
                    "--integration", integration_tip, "--commit", merge_commit)
        merge = self.shown_state(T1)["merge"]
        self.run_ok(STATE, "open-resume", CONVOY, T1, "--cause", "returned", "--ref",
                    f"merge:{merge['at']}/exit:{self.shown_state(T1)['exit']['at']}")
        self.earlier_resumes("returned", 2)
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "resumes_exhausted",
                    "--detail", "reprises épuisées pour la cause returned")

        state = self.tracker_state()
        metadata = state["beads"][T1]["metadata"]
        metadata["gc.flow.evidence.merged_tests"] = json.dumps({
            "at": merge["at"], "commit": merge_commit, "digest": RETURNED_RELEASE_EVIDENCE,
        })
        state["beads"][RETURNED_RELEASE_MAINTENANCE] = {
            "title": "release D once", "status": "closed", "issue_type": "bug", "metadata":
                delivered(901, "a" * 40, "b" * 40),
        }
        state["beads"][RETURNED_RELEASE_REPAIR] = {
            "title": "R9", "status": "closed", "issue_type": "task", "metadata": {
                "gc.flow.merge": json.dumps({"at": merge["at"], "commit": integration_tip,
                                              "integration": repair_commit, "outcome": "merged",
                                              "ticket_commit": repair_commit}),
            },
        }
        self.tracker.write_text(json.dumps(state))
        park = self.shown_state(T1)["park"]
        authorization = {
            "ticket": T1,
            "parked_at": park["at"],
            "merge_commit": merge_commit,
            "integration_tip": integration_tip,
            "repair_bead": RETURNED_RELEASE_REPAIR,
            "repair_commit": repair_commit,
            "maintenance_bead": RETURNED_RELEASE_MAINTENANCE,
        }
        self.write_log.write_text("")
        return authorization

    def exact_c2b_release(self):
        """The exhausted C2b state and its two already-delivered repairs."""
        self.started_convoy()
        self.taken(T1, "auteur-c2b")
        (self.root / "c2b.txt").write_text("exact exhausted C2b state\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "c2b.txt")
        self.git("commit", "-q", "-m", "C2b state")
        verdict_commit = self.git("rev-parse", "HEAD")
        self.git("branch", f"ticket/{T1}", "HEAD")
        self.run_ok(STATE, "set-branch", CONVOY, T1, "--branch", f"ticket/{T1}")
        state = self.tracker_state()
        metadata = state["beads"][T1]["metadata"]
        entries = [
            {"at": "2026-11-02T03:32:59Z", "cause": "evaluation_no_result",
             "exit": {"at": "2026-10-29T07:43:22Z", "exit": "finished"},
             "launches": [{"at": "2026-11-02T03:33:27Z", "bead": "fx-old1"}],
             "ref": "integration:6fb1abcedd29b405ec056b71e4ed2fa40b58993a/stop:2026-11-02T03:30:55Z",
             "session": "auteur-c2b-old-1",
             "stop": {"at": "2026-11-02T03:30:55Z", "detail": "aucun état", "raised": "2026-11-02T03:31:08Z",
                      "reason": "evaluation_no_result"}},
            {"at": "2026-11-05T02:01:03Z", "cause": "evaluation_no_result",
             "exit": {"at": "2026-11-02T04:18:07Z", "exit": "finished"},
             "launches": [{"at": "2026-11-05T02:01:43Z", "bead": "fx-old2"}],
             "ref": "integration:10e1c4376a9d5dabb40e8bd07a2b57d1b615f51e/stop:2026-11-02T08:28:29Z",
             "session": "auteur-c2b-old-2",
             "stop": {"at": "2026-11-02T08:28:29Z", "detail": "aucun état", "raised": "2026-11-02T08:29:28Z",
                      "reason": "evaluation_no_result"}},
            {"at": "2026-11-05T06:48:15Z", "cause": "evaluation_no_result",
             "exit": {"at": "2026-11-05T03:11:03Z", "exit": "finished"}, "launches": [],
             "ref": "integration:1c8287226d6db22e4e0a529eab3b7c756caf1ed6/stop:2026-11-05T06:07:57Z",
             "session": "auteur-c2b",
             "stop": {"at": "2026-11-05T06:07:57Z", "detail": "aucun état", "raised": "2026-11-05T06:08:28Z",
                      "reason": "evaluation_no_result"}},
        ]
        park = {"at": "2026-11-05T06:48:34Z", "cause": "resumes_exhausted",
                "detail": "reprises épuisées pour la cause evaluation_no_result", "origin": T1}
        metadata.update({
            "gc.flow.counter.resumes": 5,
            "gc.flow.counter.correction_rounds": 0,
            "gc.flow.resume": json.dumps({"entries": entries}),
            "gc.flow.park": json.dumps(park),
            "gc.flow.verdict.code_review": json.dumps({"at": "2026-11-05T03:38:51Z", "commit": verdict_commit,
                                                         "state": "unfavorable"}),
            "gc.flow.verdict.evaluation": json.dumps({"at": "2026-10-29T09:58:09Z", "commit": verdict_commit,
                                                        "state": "unfavorable"}),
            "gc.flow.verdict.fidelity": json.dumps({"at": "2026-11-05T04:22:42Z", "commit": verdict_commit,
                                                      "state": "unfavorable"}),
            "gc.needs_benjamin": "none",
        })
        state["beads"][T3]["metadata"]["gc.flow.park"] = json.dumps(park)
        state["beads"][C2B_RELEASE_REPAIR] = {
            "title": "repair C2b", "status": "closed", "issue_type": "bug", "labels": ["maintenance"],
            "metadata": delivered(798, "4" * 40, "5" * 40),
        }
        state["beads"][C2B_RELEASE_MIGRATION] = {
            "title": "migrate C2b", "status": "closed", "issue_type": "bug", "labels": ["maintenance"],
            "metadata": delivered(814, "6" * 40, "7" * 40),
        }
        self.tracker.write_text(json.dumps(state))
        self.write_log.write_text("")
        return {
            "ticket": T1,
            "parked_at": park["at"],
            "resume_at": entries[-1]["at"],
            "stop_at": entries[-1]["stop"]["at"],
            "integration_tip": "1c8287226d6db22e4e0a529eab3b7c756caf1ed6",
            "session": "auteur-c2b",
            "repair_bead": C2B_RELEASE_REPAIR,
            "repair_commit": "5" * 40,
            "repair_repo": "example/factory",
            "migration_bead": C2B_RELEASE_MIGRATION,
            "migration_commit": "7" * 40,
            "migration_repo": "example/factory",
        }

    def exact_c2b_result_release(self):
        """The repaired C2b result parked before its fresh judgements."""
        authorization = self.exact_c2b_release()
        self.advance(CONVOY, env={**self.env, C2B_RELEASE_ENV: json.dumps(authorization)})

        self.env["EVIDENCE_STORE_DIR"] = str(self.tmp / "store")
        self.env["EVIDENCE_PACK_DIR"] = str(self.tmp / "packs")
        descriptor = json.loads((ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json").read_text())
        descriptor["rigs"] = ["fx-rig"]
        descriptor["stacks"] = {"fx-rig": ["fixture-stack"]}
        descriptor["launch"]["regression_command"] = "true"
        (self.root / "config" / "project-descriptors").mkdir(parents=True)
        (self.root / "config" / "project-descriptors" / "fx.json").write_text(json.dumps(descriptor))
        (self.root / ".gitignore").write_text("config/\n")
        shutil.copytree(ROOT / first.FIXTURE, self.root / first.FIXTURE)
        self.run_ok(first.INTEGRATION_TOOL, "open", CONVOY, "--repo", self.root, "--protected", "main")
        self.code_reviewed("silent")
        self.evaluated()

        self.taken(T1, "auteur-c2b-result")
        self.git("checkout", "-q", f"ticket/{T1}")
        (self.root / "c2b.txt").write_text("repaired C2b result\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "repair C2b result")
        tip = self.git("rev-parse", "HEAD")
        base = self.git("rev-parse", "main")
        self.git("checkout", "-q", "--detach", "main")
        first.ticket_proofs.finish(
            self.env, self.root, CONVOY, T1, tip, base, f"ticket/{T1}",
            sections=dict.fromkeys(("done", "deviations", "not_done", "out_of_ticket"), "aucun"),
        )
        self.run_ok(STATE, "invalidate-verdicts", CONVOY, T1, "--tip", tip,
                    "--kind", "code_review", "--kind", "evaluation")
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "resumes_exhausted",
                    "--detail", "reprises épuisées pour la cause commit_after_verdict")

        state = self.tracker_state()
        metadata = state["beads"][T1]["metadata"]
        exit_record = json.loads(metadata["gc.flow.exit"])
        exit_record["at"] = "2026-11-06T20:57:26Z"
        metadata["gc.flow.exit"] = json.dumps(exit_record)
        resume = json.loads(metadata["gc.flow.resume"])
        resume["entries"][-1]["launches"][0]["at"] = "2026-11-05T06:49:00Z"
        metadata["gc.flow.resume"] = json.dumps(resume)
        verdict = json.loads(metadata["gc.flow.verdict.code_review"])
        verdict["invalidated"]["at"] = "2026-11-06T20:57:37Z"
        metadata["gc.flow.verdict.code_review"] = json.dumps(verdict)
        park = json.loads(metadata["gc.flow.park"])
        park["at"] = "2026-11-06T20:58:20Z"
        metadata["gc.flow.park"] = json.dumps(park)
        metadata["gc.flow.park_lifts"] = json.dumps({"entries": [{
            "at": "2026-11-02T00:51:08Z",
            "cause": "planning_exception",
            "detail": "Planning Exception sur C2b : inobservable sur le produit lancé",
            "option": "c",
            "parked_at": "2026-10-29T09:59:31Z",
            "request": T1,
            "resumes": 0,
            "taken": {
                "behind": 0, "code_review_no_result": 0, "commit_after_verdict": 0,
                "evaluation_no_result": 0, "inherited_change": 0, "interrupted": 0,
                "returned": 0, "stage_removed": 0, "unblocked": 0,
            },
        }]})
        state["beads"][T3]["metadata"]["gc.flow.park"] = json.dumps(park)
        state["beads"][C2B_RESULT_RELEASE_REPAIR] = {
            "title": "release repaired C2b result", "status": "closed", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": delivered(818, "8" * 40, "9" * 40),
        }
        self.tracker.write_text(json.dumps(state))
        self.write_log.write_text("")
        return {
            "ticket": T1,
            "tip": tip,
            "exit_at": exit_record["at"],
            "parked_at": park["at"],
            "resume_at": resume["entries"][-1]["at"],
            "resume_bead": resume["entries"][-1]["launches"][0]["bead"],
            "invalidated_at": verdict["invalidated"]["at"],
            "repair_bead": C2B_RESULT_RELEASE_REPAIR,
        }

    def exact_cleaned_c2b_evaluation(self):
        """C2b after its unclaimed second Evaluator route was cleaned."""
        result_release = self.exact_c2b_result_release()
        tip = result_release["tip"]
        findings = [
            {"axis": "standards", "blocking": True, "summary": "secret encore persisté",
             "citation": {"source": "spec", "quote": "As Benjamin, I want un essai."}},
            {"axis": "spec", "blocking": True, "summary": "usage manquant encore affiché comme zéro",
             "citation": {"source": "spec", "quote": "As Benjamin, I want un essai."}},
        ]
        self.code_reviewed({"findings": findings})
        self.evaluated("unclaimed")
        self.env["CONVOY_ADVANCE_EVALUATION_BIN"] = str(
            ROOT / "tests" / "fixtures" / "convoy-advance" / "evaluation")
        self.env["CONVOY_ADVANCE_FAKE_EVALUATION_LOG"] = str(self.tmp / "convoy-evaluation.log")
        self.corrected("leaves")
        prepared = self.advance(
            CONVOY, env={**self.env, C2B_RESULT_RELEASE_ENV: json.dumps(result_release)})
        self.assertIn("launched", self.evaluation_of(prepared), prepared)

        state = self.tracker_state()
        metadata = state["beads"][T1]["metadata"]
        exit_at = json.loads(metadata["gc.flow.exit"])["at"]
        metadata.pop("gc.flow.exit")
        evaluation = json.loads(metadata["gc.flow.evaluation"])
        cleaned_launch = evaluation["request"]["launches"][-1]["bead"]
        evaluation.pop("request")
        evaluation.pop("live", None)
        metadata["gc.flow.evaluation"] = json.dumps(evaluation)
        first_launch = "fx-c2b-claimed-evaluation"
        for bead_id in (first_launch, cleaned_launch):
            state["beads"][bead_id] = {
                "title": "old C2b evaluation", "status": "closed", "issue_type": "task",
                "metadata": {"gc.dispatch_formula": "mol-ticket-evaluation",
                             "gc.execution_routed_to": "evaluator"},
            }
        integration_tip = self.git("rev-parse", self.INTEGRATION)
        resume = {"entries": [{
            "at": "2026-11-02T03:32:59Z", "cause": "evaluation_no_result",
            "exit": {"at": "2026-10-29T07:43:22Z", "exit": "finished"}, "launches": [],
            "ref": "integration:6fb1abcedd29b405ec056b71e4ed2fa40b58993a/stop:2026-11-02T03:30:55Z",
            "session": "auteur-c2b-old-1",
            "stop": {"at": "2026-11-02T03:30:55Z", "detail": "aucun état", "raised": "2026-11-02T03:31:08Z",
                     "reason": "evaluation_no_result"}},
            {"at": "2026-11-05T02:01:03Z", "cause": "evaluation_no_result",
             "exit": {"at": "2026-11-02T04:18:07Z", "exit": "finished"}, "launches": [],
             "ref": "integration:10e1c4376a9d5dabb40e8bd07a2b57d1b615f51e/stop:2026-11-02T08:28:29Z",
             "session": "auteur-c2b-old-2",
             "stop": {"at": "2026-11-02T08:28:29Z", "detail": "aucun état", "raised": "2026-11-02T08:29:28Z",
                      "reason": "evaluation_no_result"}},
            {"at": "2026-11-05T06:48:15Z", "cause": "repair_delivered",
             "exit": {"at": "2026-11-05T03:11:03Z", "exit": "finished"}, "launches": [],
             "ref": "integration:1c8287226d6db22e4e0a529eab3b7c756caf1ed6/stop:2026-11-05T06:07:57Z",
             "session": "auteur-c2b-repair",
             "stop": {"at": "2026-11-05T06:07:57Z", "detail": "aucun état", "raised": "2026-11-05T06:08:28Z",
                      "reason": "evaluation_no_result"}},
            {
            "at": "2026-11-07T03:38:30Z", "cause": "evaluation_no_result",
            "exit": {"at": exit_at, "exit": "finished"}, "launches": [],
            "ref": f"integration:{integration_tip}/stop:2026-11-07T03:36:06Z",
            "session": "auteur-c2b-current",
            "stop": {"at": "2026-11-07T03:36:06Z",
                     "detail": f"aucun état en 2 lancements ({first_launch}, {cleaned_launch})",
                     "raised": "2026-11-07T03:36:25Z", "reason": "evaluation_no_result"},
        }]}
        metadata["gc.flow.resume"] = json.dumps(resume)
        metadata["gc.flow.counter.resumes"] = 7
        metadata["gc.flow.session"] = json.dumps(
            {"at": "2026-11-06T20:29:21Z", "name": "auteur-c2b-current"})
        park = {"at": "2026-11-07T03:38:57Z", "cause": "resumes_exhausted",
                "detail": "reprises épuisées pour la cause evaluation_no_result", "origin": T1}
        metadata["gc.flow.park"] = json.dumps(park)
        metadata["gc.flow.park_lifts"] = json.dumps({"entries": [
            {"at": "2026-11-02T00:51:08Z", "cause": "planning_exception", "detail": "inobservable",
             "option": "c", "parked_at": "2026-10-29T09:59:31Z", "request": T1, "resumes": 0,
             "taken": {"behind": 0, "code_review_no_result": 0, "commit_after_verdict": 0,
                       "evaluation_no_result": 0, "inherited_change": 0, "interrupted": 0,
                       "returned": 0, "stage_removed": 0, "unblocked": 0}},
            {"at": "2026-11-07T00:12:20Z", "cause": "resumes_exhausted", "detail": "C2b result release",
             "option": None, "parked_at": "2026-11-06T20:58:20Z", "request": C2B_RESULT_RELEASE_REPAIR,
             "reset_cause": "commit_after_verdict", "resumes": 6,
             "taken": {"behind": 0, "code_review_no_result": 0, "commit_after_verdict": 3,
                       "evaluation_no_result": 0, "inherited_change": 0, "interrupted": 0,
                       "repair_delivered": 0, "returned": 0, "stage_removed": 0, "unblocked": 0}},
        ]})
        state["beads"][T3]["metadata"]["gc.flow.park"] = json.dumps(park)
        state["beads"][C2B_EVALUATION_RECOVERY_REPAIR] = {
            "title": "recover cleaned C2b evaluation", "status": "closed", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": delivered(826, "a" * 40, "b" * 40),
        }
        review = json.loads(metadata["gc.flow.code_review"])
        blocking = ",".join(finding["id"] for finding in review["rounds"][-1]["findings"]
                            if finding["blocking"])
        self.tracker.write_text(json.dumps(state))
        self.write_log.write_text("")
        return {
            "ticket": T1, "tip": tip, "exit_at": exit_at,
            "parked_at": park["at"], "resume_at": resume["entries"][-1]["at"],
            "stop_at": resume["entries"][-1]["stop"]["at"],
            "integration_tip": integration_tip,
            "session": "auteur-c2b-current", "first_launch": first_launch,
            "cleaned_launch": cleaned_launch, "blocking_findings": blocking,
            "previous_repair": C2B_RESULT_RELEASE_REPAIR,
            "repair_bead": C2B_EVALUATION_RECOVERY_REPAIR,
        }

    def exact_returned_result_release(self):
        """D's repaired result with its four historical parking lifts."""
        authorization = self.exact_returned_release()
        self.advance(CONVOY, env={**self.env, RETURNED_RELEASE_ENV: json.dumps(authorization)})
        self.code_reviewed("silent")
        self.evaluated()

        self.taken(T1, "auteur-returned-result")
        self.git("checkout", "-q", f"ticket/{T1}")
        (self.root / "d-result.txt").write_text("repaired D result\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "repair D result")
        tip = self.git("rev-parse", "HEAD")
        base = self.git("rev-parse", "main")
        self.git("checkout", "-q", "--detach", "main")
        first.ticket_proofs.finish(
            self.env, self.root, CONVOY, T1, tip, base, f"ticket/{T1}",
            sections=dict.fromkeys(("done", "deviations", "not_done", "out_of_ticket"), "aucun"),
        )
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "resumes_exhausted",
                    "--detail", "reprises épuisées pour la cause returned")

        state = self.tracker_state()
        metadata = state["beads"][T1]["metadata"]
        exit_record = json.loads(metadata["gc.flow.exit"])
        exit_record["at"] = "2026-11-06T19:45:34Z"
        metadata["gc.flow.exit"] = json.dumps(exit_record)
        resume = json.loads(metadata["gc.flow.resume"])
        resume["entries"][-1]["at"] = "2026-11-06T02:50:06Z"
        resume["entries"][-1]["launches"][0]["at"] = "2026-11-06T19:10:51Z"
        metadata["gc.flow.resume"] = json.dumps(resume)
        metadata["gc.flow.counter.resumes"] = 13
        park = json.loads(metadata["gc.flow.park"])
        park["at"] = "2026-11-06T19:15:40Z"
        metadata["gc.flow.park"] = json.dumps(park)
        metadata["gc.flow.park_lifts"] = json.dumps({"entries": [
            {"at": "2026-10-21T02:15:51Z", "cause": "operator_request", "detail": "green impossible",
             "option": "a", "parked_at": "2026-10-21T00:35:02Z", "request": T1, "resumes": 1,
             "taken": {"amendment_granted": 1, "answered": 0, "behind": 0, "code_review_no_result": 0,
                       "commit_after_verdict": 0, "evaluation_no_result": 0, "interrupted": 0,
                       "returned": 0, "stage_removed": 0, "unblocked": 0}},
            {"at": "2026-10-21T16:26:26Z", "cause": "planning_exception", "detail": "inobservable",
             "option": "a", "parked_at": "2026-10-21T04:16:56Z", "request": T1, "resumes": 2,
             "taken": {"amendment_granted": 1, "answered": 1, "behind": 0, "code_review_no_result": 0,
                       "commit_after_verdict": 0, "evaluation_no_result": 0, "interrupted": 0,
                       "returned": 0, "stage_removed": 0, "unblocked": 0}},
            {"at": "2026-10-27T14:10:16Z", "cause": "resumes_exhausted", "detail": "behind exhausted",
             "option": "a", "parked_at": "2026-10-23T16:36:17Z", "request": "af-89ctnv", "resumes": 8,
             "taken": {"amendment_granted": 1, "answered": 1, "behind": 3, "code_review_no_result": 0,
                       "commit_after_verdict": 0, "evaluation_no_result": 0, "interrupted": 0,
                       "returned": 0, "stage_removed": 0, "unblocked": 0}},
            {"at": "2026-10-31T23:42:04Z", "cause": "operator_request", "detail": "red merge",
             "option": "a", "parked_at": "2026-10-31T04:58:15Z", "request": T1, "resumes": 10,
             "taken": {"behind": 0, "code_review_no_result": 0, "commit_after_verdict": 0,
                       "evaluation_no_result": 0, "inherited_change": 0, "interrupted": 0,
                       "returned": 2, "stage_removed": 0, "unblocked": 0}},
        ]})
        state["beads"][T3]["metadata"]["gc.flow.park"] = json.dumps(park)
        state["beads"][RETURNED_RESULT_RELEASE_REPAIR] = {
            "title": "release repaired D result", "status": "closed", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": delivered(819, "a" * 40, "b" * 40),
        }
        self.tracker.write_text(json.dumps(state))
        self.write_log.write_text("")
        return {
            "ticket": T1,
            "tip": tip,
            "exit_at": exit_record["at"],
            "parked_at": park["at"],
            "resume_at": resume["entries"][-1]["at"],
            "resume_bead": resume["entries"][-1]["launches"][0]["bead"],
            "repair_bead": RETURNED_RESULT_RELEASE_REPAIR,
        }

    def exact_r8_close_release(self, regression="true"):
        """R8 after its answered close-without-merge choice was re-asked."""
        tip = self.integrated(regression=regression)
        self.resumable()
        self.advance(CONVOY)
        self.git("branch", f"ticket/{T1}", tip)
        self.run_ok(STATE, "set-branch", CONVOY, T1, "--branch", f"ticket/{T1}")
        self.taken(T1, "auteur-r8-1")
        first_request = {
            "quoi": "R8 : le rouge ne se reproduit pas",
            "pourquoi": "Le même arbre passe le contrôle.",
            "que_faire": [
                {"option": "Clore R8 sans fusion", "consequence": "R8 est fermé sans fusion."},
                {"option": "Conserver R8", "consequence": "R8 reste ouvert."},
            ],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(first_request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", first_request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")
        resumed = self.advance(CONVOY)
        self.assertEqual([(T1, "answered")], [(entry["id"], entry["cause"])
                                               for entry in self.of(resumed, "resumed")])

        self.taken(T1, "auteur-r8-2")
        second_request = {
            "quoi": "R8 : réponse a reçue, mais aucune porte ne clôt un ticket non fusionné",
            "pourquoi": "Le rouge est déjà retiré ; seule reste la clôture sans fusion.",
            "que_faire": [
                {"option": "Clore R8 sans fusion dans le Planning Run",
                 "consequence": "R8 est fermé sans fusion et le convoi continue."},
                {"option": "Corriger la porte par maintenance",
                 "consequence": "Le ticket reprend après la maintenance."},
            ],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(second_request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", second_request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        state = self.tracker_state()
        state["beads"][R8_CLOSE_RELEASE_REPAIR] = {
            "title": "execute R8 close without merge", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", R8_CLOSE_RELEASE_REPAIR)
        self.edit(R8_CLOSE_RELEASE_REPAIR, status="closed", metadata=delivered(820, "a" * 40, "b" * 40))
        metadata = self.bead(T1)["metadata"]
        park = json.loads(metadata["gc.flow.park"])
        exit_record = json.loads(metadata["gc.flow.exit"])
        resume = json.loads(metadata["gc.flow.resume"])["entries"][-1]
        self.write_log.write_text("")
        return {
            "ticket": T1,
            "tip": tip,
            "session": "auteur-r8-2",
            "response_at": metadata["gc.escalation_response_at"],
            "response_actor": metadata["gc.escalation_response_actor"],
            "response_option": "a",
            "needs": metadata["gc.needs_benjamin"],
            "resume_at": resume["at"],
            "resume_bead": resume["launches"][0]["bead"],
            "resume_session": resume["session"],
            "resume_cause": resume["cause"],
            "parked_at": park["at"],
            "exit_at": exit_record["at"],
            "repair_bead": R8_CLOSE_RELEASE_REPAIR,
        }

    def exact_r8_close_release_after_generic_lift(self):
        """R8 after its delivered repair was generically lifted and resumed."""
        self.exact_r8_close_release()
        lifted = self.advance(CONVOY)
        resume = json.loads(self.bead(T1)["metadata"]["gc.flow.resume"])["entries"][-1]
        park_lift = json.loads(self.bead(T1)["metadata"]["gc.flow.park_lifts"])["entries"][-1]
        self.assertEqual(("repair_delivered", 1), (resume["cause"], len(resume["launches"])))
        self.assertEqual((None, [R8_CLOSE_RELEASE_REPAIR]),
                         (park_lift["option"], park_lift["repairs"]))
        self.assertEqual([(T1, "repair_delivered")],
                         [(entry["id"], entry["cause"]) for entry in self.of(lifted, "resumed")])

        self.taken(T1, "auteur-r8-3")
        request = {
            "quoi": "R8 : la clôture sans fusion n'a pas reconnu la levée générique",
            "pourquoi": "La reprise repair_delivered a consommé l'état attendu par la porte dédiée.",
            "que_faire": [
                {"option": "Réparer la clôture sans fusion pour l'état actuel de R8",
                 "consequence": "R8 est fermé sans fusion sans nouvel auteur."},
                {"option": "Laisser R8 parqué", "consequence": "R8 reste ouvert."},
            ],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        state = self.tracker_state()
        state["beads"][R8_CLOSE_CURRENT_REPAIR] = {
            "title": "close current R8 without merge", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": R8_CLOSE_RELEASE_REPAIR},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", R8_CLOSE_CURRENT_REPAIR)
        self.edit(R8_CLOSE_CURRENT_REPAIR, status="closed", metadata=delivered(821, "c" * 40, "d" * 40))
        metadata = self.bead(T1)["metadata"]
        park = json.loads(metadata["gc.flow.park"])
        exit_record = json.loads(metadata["gc.flow.exit"])
        resume = json.loads(metadata["gc.flow.resume"])["entries"][-1]
        self.write_log.write_text("")
        return {
            "ticket": T1,
            "tip": self.shown_state(T1)["tip"],
            "session": "auteur-r8-3",
            "response_at": metadata["gc.escalation_response_at"],
            "response_actor": metadata["gc.escalation_response_actor"],
            "response_option": "a",
            "needs": metadata["gc.needs_benjamin"],
            "resume_at": resume["at"],
            "resume_bead": resume["launches"][0]["bead"],
            "resume_session": resume["session"],
            "resume_cause": resume["cause"],
            "parked_at": park["at"],
            "exit_at": exit_record["at"],
            "repair_bead": R8_CLOSE_CURRENT_REPAIR,
        }

    def exact_r6_r7_withdrawal(self):
        """The two historical Planning Exceptions Benjamin answered b."""
        first_tip = self.integrated()
        self.resumable()
        self.advance(CONVOY)
        second_tip = self.git("commit-tree", f"{first_tip}^{{tree}}", "-p", first_tip, "-m", "R7 tip")
        tickets = []
        for ticket_id, tip in ((T1, first_tip), (T2, second_tip)):
            self.git("branch", f"ticket/{ticket_id}", tip)
            self.run_ok(STATE, "set-branch", CONVOY, ticket_id, "--branch", f"ticket/{ticket_id}")
            self.taken(ticket_id, f"author-{ticket_id}")
            self.planning_exception(ticket_id)
            self.run_ok(ESCALATION, "repondre", ticket_id, "b", "--actor", "benjamin")
            metadata = self.bead(ticket_id)["metadata"]
            tickets.append({
                "ticket": ticket_id,
                "tip": tip,
                "exit_at": json.loads(metadata["gc.flow.exit"])["at"],
                "parked_at": json.loads(metadata["gc.flow.park"])["at"],
                "response_at": metadata["gc.escalation_response_at"],
                "response_actor": "benjamin",
                "response_option": "b",
            })
        state = self.tracker_state()
        state["beads"][R6_R7_WITHDRAWAL_REPAIR] = {
            "title": "withdraw R6 and R7", "status": "closed", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": delivered(822, "e" * 40, "f" * 40),
        }
        self.tracker.write_text(json.dumps(state))
        self.write_log.write_text("")
        return {"convoy": CONVOY, "repair_bead": R6_R7_WITHDRAWAL_REPAIR, "tickets": tickets}

    def test_a_pass_sends_an_interrupted_ticket_to_a_fresh_author_session_and_counts_the_resume(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")

        answer = self.advance(CONVOY)

        [resumed] = self.of(answer, "resumed")
        self.assertEqual((T1, "interrupted"), (resumed["id"], resumed["cause"]))
        self.assertEqual(1, self.resumes())
        self.assertEqual([["sling", "fx-worker", resumed["bead"], "fx-resume"]], self.resume_launches())
        sent = self.bead(resumed["bead"])["description"]
        self.assertIn(f"convoy: {CONVOY}", sent)
        self.assertIn(f"ticket: {T1}", sent)
        # The ticket is at work again: it will exit again.
        self.assertIsNone(self.shown_state(T1)["exit"])
        self.assertEqual(0, self.resumes(T2))

    def test_a_session_that_ended_without_an_exit_is_resumed_as_interrupted(self):
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(0, self.resumes())
        self.edit(sessions=[])

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "interrupted")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())

    def test_a_second_pass_on_the_same_interruption_counts_and_sends_nothing_more(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(before, self.tickets_snapshot())
        self.assertEqual(1, len(self.resume_launches()))

    def test_a_resume_whose_session_ended_without_taking_the_ticket_is_one_more_interruption(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        [first] = self.of(self.advance(CONVOY), "resumed")
        self.edit(first["bead"], status="closed")

        [second] = self.of(self.advance(CONVOY), "resumed")

        self.assertNotEqual(first["bead"], second["bead"])
        self.assertEqual(2, self.resumes())

    def test_a_resume_that_cannot_be_sent_fails_the_pass_is_counted_once_and_is_sent_by_the_next(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        env = {**self.env, "CONVOY_STATE_FAKE_SLING_FAIL": "fx-new1"}

        proc = self.run_cmd(TOOL, CONVOY, env=env)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([T1], [entry["id"] for entry in self.of(json.loads(proc.stdout), "refused")])
        self.assertEqual([], self.resume_launches())
        self.assertEqual(1, self.resumes())

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_to_resume_without_resume_settings_is_refused_and_nothing_is_written(self):
        self.advance(CONVOY)
        self.interrupted(T1, "auteur-1")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        [refused] = self.of(answer, "refused")
        self.assertEqual(T1, refused["id"])
        self.assertIn("resume.formula", refused["reason"])
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_resume_waits_for_a_free_place_under_the_ceiling_and_counts_nothing_meanwhile(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.resumable(ceiling=1)
        self.edit(sessions=[session("delivery-reviewer")])

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertIn(T1, [entry["id"] for entry in self.of(answer, "waiting")])
        self.assertEqual(0, self.resumes())
        self.assertEqual([], self.resume_launches())

    def test_a_resume_sent_and_not_yet_taken_by_a_session_holds_its_place(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        # T2 alone awaits its session when this pass counts, then T1 is sent.
        self.assertEqual([T2], self.advance(CONVOY)["awaiting_a_session"])

        answer = self.advance(CONVOY)

        self.assertEqual([T1, T2], answer["awaiting_a_session"])
        self.assertEqual(2, answer["occupied"])

    def test_a_resume_whose_session_ended_without_taking_the_ticket_holds_no_place(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        [sent] = self.of(self.advance(CONVOY), "resumed")
        self.edit(sent["bead"], status="closed")

        answer = self.advance(CONVOY)

        self.assertEqual([T2], answer["awaiting_a_session"])

    def test_a_stopped_ticket_is_never_resumed_as_interrupted(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "amendment_exhausted", "--detail", "second amendement")
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(before, self.tickets_snapshot())

    # --- a ticket stopped without an evaluation result is resumed on itself (af-xhc0sj) ---

    NO_RESULT = "evaluation_no_result"

    @first.staged
    def evaluation_stopped(self):
        """T1, a slice, finished on the integration branch, then stopped as
        bin/ticket-evaluation stops it: its evaluation request left open
        with two launches that gave no result, the stop raised to the
        operator."""
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.env.update({
            "TICKET_EVALUATION_CANCEL_BIN": str(first.ROOT / "tests" / "fixtures" / "ticket-evaluation" / "cancel"),
            "TICKET_EVALUATION_CANCEL_LOG": str(self.tmp / "evaluation-cancel.log"),
        })
        self.advance(CONVOY)
        tip = self.finished(T1)
        bead = self.bead(T1)
        self.edit(T1, metadata={**bead["metadata"], "gc.ticket_kind": "vertical_slice",
                                "gc.flow.demonstration_line": "La page affiche 3",
                                "gc.flow.user_stories": json.dumps({"stories": ["1"]})},
                  description="## Acceptance criteria\n\n- [ ] La page affiche 3\n\n" + bead["description"])
        request = self.tmp / "evaluation-request.json"
        request.write_text(json.dumps({
            "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:9",
                             "state_file": str(self.tmp / "launches" / "gone.json")}]}))
        self.run_ok(STATE, "open-evaluation", CONVOY, T1, "--commit", tip, "--file", request)
        for launch in ("fx-e1", "fx-e2"):
            self.run_ok(STATE, "launch-evaluation", CONVOY, T1, "--bead", launch)
        self.assertEqual(2, len(self.shown_state(T1)["evaluation"]["request"]["launches"]))
        self.stop_without_result()
        self.write_log.write_text("")

    def stop_without_result(self):
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", self.NO_RESULT,
                    "--detail", "la Ticket Evaluation n'a rendu aucun état en 2 lancements")
        request = {"quoi": f"Ticket {T1} arrêté : sa Ticket Evaluation n'a rendu aucun état",
                   "pourquoi": "Une évaluation sans résultat n'est pas passée.",
                   "que_faire": [{"option": "Laisser le ticket arrêté", "consequence": "Rien ne fusionne."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)

    def test_a_ticket_stopped_without_an_evaluation_result_is_resumed_on_itself_once_per_integration_tip(self):
        self.evaluation_stopped()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, self.NO_RESULT)], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(["sling", "fx-worker", self.of(answer, "resumed")[0]["bead"], "fx-resume"],
                         self.resume_launches()[-1][:4])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, None), (shown["counters"]["resumes"], shown["stop"], shown["exit"]))
        # The stop is lifted, not erased: it is kept on the resume that lifted it.
        self.assertEqual(self.NO_RESULT, shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        # The exit taken back, the evaluation left open on it is withdrawn in the same pass.
        self.assertIsNone(shown["evaluation"].get("request"))
        # Stopped again on the same integration tip: it stays with the operator.
        self.stop_without_result()
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])
        # The integration branch moved: once more, counted.
        self.integration_moved()
        again = self.advance(CONVOY)
        self.assertEqual([(T1, self.NO_RESULT)], [(r["id"], r["cause"]) for r in self.of(again, "resumed")])
        self.assertEqual(2, self.resumes())

    def test_an_evaluation_without_result_resumes_once_after_its_linked_factory_repair_is_delivered(self):
        self.evaluation_stopped()
        repair = "fx-er1"
        state = self.tracker_state()
        state["beads"][repair] = {
            "title": "réparer le rôle Evaluator", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))

        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)
        waiting = self.advance(CONVOY)
        self.assertEqual([], self.of(waiting, "resumed"))
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])

        self.edit(repair, status="closed", metadata=delivered(43, "1" * 40, "2" * 40))
        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "repair_delivered")],
                         [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        self.assertEqual((None, None, 1),
                         (shown["stop"], shown["technical_repairs"], shown["counters"]["resumes"]))
        self.assertEqual(self.NO_RESULT, shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_stopped_without_an_evaluation_result_at_its_third_resume_is_parked_not_restarted(self):
        self.evaluation_stopped()
        self.earlier_resumes(self.NO_RESULT, 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        self.assertEqual(([], []), (self.of(answer, "resumed"), self.resume_launches()))
        self.assertEqual((3, None), (self.resumes(), self.shown_state(T1)["stop"]))

    def test_a_stop_without_evaluation_result_the_operator_answered_is_not_resumed(self):
        self.evaluation_stopped()
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])

    def test_an_evaluation_stop_answered_while_its_request_is_cleared_is_not_resumed(self):
        self.evaluation_stopped()

        answer = self.advance(CONVOY, env={**self.env, "CONVOY_STATE_FAKE_ANSWER_ON_CLEAR": f"{T1}=a"})

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])

    # --- a ticket stopped by a stage the flow removed is resumed on itself (ADR-0030 L3, af-pjvsgo) ---

    def stopped_by_the_test_review(self, raised=True):
        """T1 at work under an author session that is over, then stopped as
        the test review stopped it before L3 removed that stage, its
        request raised to the operator (T59, af-qjq1t6) when `raised`."""
        self.resumable()
        self.advance(CONVOY)
        self.edit(T1, status="in_progress")
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "test_review_no_result",
                    "--detail", "la relecture des tests n'a rendu aucun verdict en 2 lancements")
        self.write_log.write_text("")
        if not raised:
            return
        request = {"quoi": f"Ticket {T1} arrêté : relecture des tests sans résultat",
                   "pourquoi": "La relecture des tests n'a rendu aucun verdict.",
                   "que_faire": [{"option": "Laisser le ticket arrêté", "consequence": "Rien ne fusionne."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        self.write_log.write_text("")

    def test_a_ticket_the_removed_test_review_stopped_is_resumed_once_and_its_request_withdrawn(self):
        self.stopped_by_the_test_review()
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "stage_removed")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, None), (shown["counters"]["resumes"], shown["stop"], shown["exit"]))
        # The stop is lifted, not erased: it is kept on the resume that lifted it.
        self.assertEqual("test_review_no_result", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        # The next pass counts and sends nothing more.
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_stop_of_the_removed_test_review_the_operator_answered_is_not_resumed(self):
        self.stopped_by_the_test_review()
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual("test_review_no_result", self.shown_state(T1)["stop"]["reason"])

    def test_a_removed_stage_stop_answered_while_its_request_is_cleared_is_not_resumed(self):
        self.stopped_by_the_test_review()

        answer = self.advance(CONVOY, env={**self.env, "CONVOY_STATE_FAKE_ANSWER_ON_CLEAR": f"{T1}=a"})

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual("test_review_no_result", self.shown_state(T1)["stop"]["reason"])

    def test_a_ticket_the_removed_test_review_stopped_without_a_resume_left_stays_stopped_and_is_raised_once(self):
        self.stopped_by_the_test_review(raised=False)
        self.earlier_resumes("stage_removed", 3)

        first_pass, second_pass = self.advance(CONVOY), self.advance(CONVOY)

        self.assertEqual([], self.of(first_pass, "resumed"))
        self.assertEqual([{"ticket": T1, "reason": "test_review_no_result"}],
                         self.of(first_pass, "tdd_stops")["escalated"])
        self.assertEqual([], self.of(second_pass, "tdd_stops"))
        self.assertEqual("test_review_no_result", self.shown_state(T1)["stop"]["reason"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    # --- a ticket stopped for an exhausted amendment reaches the operator (T45) ---

    def test_a_pass_raises_a_ticket_stopped_for_an_exhausted_amendment_naming_it_and_the_cause(self):
        self.amendment_exhausted()
        self.assertEqual([], self.needs())

        answer = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "reason": "amendment_exhausted"}], self.of(answer, "tdd_stops")["escalated"])
        needs = self.needs()
        self.assertEqual(1, len(needs), needs)
        self.assertIn(T1, needs[0])
        self.assertIn("amendement épuisé", needs[0])
        mails = self.log("mail")
        self.assertEqual(1, len(mails), mails)
        self.assertEqual("human", mails[0][1])

    def test_a_second_pass_on_the_same_exhausted_amendment_raises_nothing_more_and_the_state_shows_it_was_raised(self):
        self.amendment_exhausted()
        self.advance(CONVOY)
        self.assertIn("raised", self.shown_state(T1)["stop"])
        before = self.tickets_snapshot()
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))
        self.assertEqual([], self.log("mail"))
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_ticket_stopped_for_an_exhausted_amendment_is_neither_merged_nor_resumed_and_the_others_go_on(self):
        self.amendment_exhausted(ceiling=1)
        self.assert_not_started(T2)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([], self.resume_launches())
        self.assertNotIn("integration", next(c for c in answer["convoys"] if c["id"] == CONVOY))
        self.assertEqual("in_progress", self.bead(T1)["status"])
        self.assertEqual([T2], self.started(answer))
        self.assert_started_through_door(T2)
        self.assert_not_started(T3)

    def test_an_exhausted_amendment_the_door_could_not_raise_fails_the_pass_and_is_raised_by_the_next(self):
        self.amendment_exhausted()

        failed = self.advance(CONVOY, expect=EXIT_REFUSED, env={**self.env, "CONVOY_STATE_FAKE_MAIL_FAIL": "1"})

        self.assertIn("error", self.of(failed, "tdd_stops"))
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

        self.advance(CONVOY)

        self.assertIn("raised", self.shown_state(T1)["stop"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    # --- an exhausted amendment the operator answered « a » is resumed with one more amendment (af-25o7vr) ---

    def amendment_answered(self, letter):
        """T1 stopped at its second amendment, its request raised, then
        answered `letter` by the operator."""
        self.amendment_exhausted()
        self.advance(CONVOY)
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop
        self.run_ok(ESCALATION, "repondre", T1, letter, "--actor", "operateur-test")
        self.write_log.write_text("")

    def preauthorized_amendment(self, *, ticket_id=AUTHORIZED_TICKET, own=AUTHORIZED_FILES,
                                commit=AUTHORIZED_COMMIT):
        """The exact A2 response and commit, on an unraised amendment stop."""
        self.amendment_exhausted()
        state = self.tracker_state()
        bead = state["beads"].pop(T1)
        state["beads"][ticket_id] = bead
        state["beads"][CONVOY]["tracks"] = [ticket_id if item == T1 else item
                                               for item in state["beads"][CONVOY]["tracks"]]
        state["beads"][T3]["blocks"] = [ticket_id if item == T1 else item
                                          for item in state["beads"][T3]["blocks"]]
        bead["metadata"].update({
            "gc.escalation_response_actor": "benjamin",
            "gc.escalation_response_option": "a",
            "gc.escalation_response_at": AUTHORIZED_RESPONSE_AT,
            "gc.needs_benjamin": "none",
        })
        self.tracker.write_text(json.dumps(state))

        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        branch = f"ticket/{ticket_id}"
        self.git("branch", branch, "HEAD")
        self.run_ok(STATE, "set-branch", CONVOY, ticket_id, "--branch", branch)
        descriptors = self.root / "config" / "project-descriptors"
        descriptors.mkdir(parents=True, exist_ok=True)
        (descriptors / "fx.json").write_text(json.dumps({"rigs": ["fx-rig"]}))
        fake = self.tmp / "authorized-tdd-changes"
        fake.write_text("#!/bin/sh\necho '" + json.dumps(
            {"ok": True, "ticket": ticket_id, "commit": commit, "own": own, "inherited": []}) + "'\n")
        fake.chmod(0o755)
        self.env["CONVOY_ADVANCE_TDD_STEP_BIN"] = str(fake)

    def test_the_exact_a2_response_before_the_stop_resumes_its_exact_commit_and_files_once(self):
        self.preauthorized_amendment()

        answer = self.advance(CONVOY)

        self.assertEqual([(AUTHORIZED_TICKET, "amendment_granted")],
                         [(entry["id"], entry["cause"]) for entry in self.of(answer, "resumed")])
        shown = self.shown_state(AUTHORIZED_TICKET)
        self.assertIsNone(shown["stop"])
        self.assertTrue(shown["resume"]["entries"][-1]["ref"].endswith(f"/{AUTHORIZED_REF}"))
        self.run_ok(STATE, "stop-ticket", CONVOY, AUTHORIZED_TICKET,
                    "--reason", "amendment_exhausted", "--detail", "seconde consommation")

        repeated = self.advance(CONVOY)

        self.assertEqual([], self.of(repeated, "resumed"))
        self.assertEqual(1, self.resumes(AUTHORIZED_TICKET))

    def test_the_a2_pre_stop_response_refuses_another_file(self):
        self.preauthorized_amendment(own=[*AUTHORIZED_FILES, "tests/other.py"])

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(0, self.resumes(AUTHORIZED_TICKET))

    def test_the_a2_pre_stop_response_refuses_another_ticket(self):
        self.preauthorized_amendment(ticket_id="af-other")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(0, self.resumes("af-other"))

    def test_the_a2_pre_stop_response_refuses_another_commit(self):
        self.preauthorized_amendment(commit="0" * 40)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(0, self.resumes(AUTHORIZED_TICKET))

    def test_an_exhausted_amendment_answered_a_is_resumed_once_and_its_stop_kept_on_the_resume(self):
        self.amendment_answered("a")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "amendment_granted")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        shown = self.shown_state(T1)
        self.assertEqual((1, None), (shown["counters"]["resumes"], shown["stop"]))
        self.assertEqual("amendment_exhausted", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        # The next pass counts and sends nothing more.
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    # --- an exhausted amendment whose every change is the merged base's is resumed (af-npz9v1.39) ---

    def tdd_changes(self, own, inherited):
        """bin/tdd-step changes answers what changed since the freeze."""
        fake = self.tmp / "tdd-step-changes"
        fake.write_text("#!/bin/sh\necho '" + json.dumps({"ok": True, "own": own, "inherited": inherited}) + "'\n")
        fake.chmod(0o755)
        self.env["CONVOY_ADVANCE_TDD_STEP_BIN"] = str(fake)
        # The profile of its project, and its tip: what bin/tdd-step changes is asked about.
        descriptors = self.root / "config" / "project-descriptors"
        descriptors.mkdir(parents=True, exist_ok=True)
        (descriptors / "fx.json").write_text(json.dumps({"rigs": ["fx-rig"]}))
        if not (self.root / ".git").exists():
            self.git("init", "-q", "-b", "main")
            self.git("commit", "-q", "--allow-empty", "-m", "base")
        self.git("branch", "-f", f"ticket/{T1}", "HEAD")
        self.run_ok(STATE, "set-branch", CONVOY, T1, "--branch", f"ticket/{T1}")

    def test_an_exhausted_amendment_whose_every_change_is_the_merged_base_s_is_resumed_without_an_answer(self):
        """A harness main's maintenance changed, taken with the integration
        branch, is no amendment of the ticket's: no answer is asked."""
        self.amendment_exhausted()
        self.advance(CONVOY)
        self.write_log.write_text("")
        self.tdd_changes([], ["tests/fixtures/cockpit/core/fake_gc.py"])

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "inherited_change")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        self.assertIsNone(shown["stop"])
        self.assertEqual("amendment_exhausted", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))

    def test_an_exhausted_amendment_with_a_change_of_its_own_stays_stopped(self):
        self.amendment_exhausted()
        self.advance(CONVOY)
        self.tdd_changes(["tests/criterion-test.py"], ["tests/fixtures/cockpit/core/fake_gc.py"])

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual("amendment_exhausted", self.shown_state(T1)["stop"]["reason"])

    def test_an_exhausted_amendment_answered_b_stays_stopped(self):
        self.amendment_answered("b")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual(([], []), (self.of(answer, "resumed"), self.resume_launches()))
        self.assertEqual("amendment_exhausted", self.shown_state(T1)["stop"]["reason"])
        self.assertEqual(before, self.tickets_snapshot())

    def test_an_exhausted_amendment_not_answered_yet_is_not_resumed(self):
        self.amendment_exhausted()
        self.advance(CONVOY)

        answer = self.advance(CONVOY)

        self.assertEqual(([], []), (self.of(answer, "resumed"), self.resume_launches()))
        self.assertEqual("amendment_exhausted", self.shown_state(T1)["stop"]["reason"])

    # --- a repair that only moves a proof, stopped all green, is resumed (af-oa2ci4) ---

    def stopped_all_green(self, restores, raised=True):
        """T1, a repair that restores `restores`, at work under an author
        session that is over, stopped all green by bin/tdd-step red before
        it gave a moved proof its path, the stop raised to the operator (R12,
        af-0p3nfo)."""
        self.resumable()
        self.advance(CONVOY)
        metadata = self.bead(T1)["metadata"]
        metadata.update({"gc.ticket_kind": "repair",
                         "gc.flow.demonstration_line": "La page projet montre les lignes de roadmap"})
        description = self.bead(T1)["description"].replace(
            "## Target rigs", f"## Restores\n\n{restores}\n\n## Target rigs")
        self.edit(T1, status="in_progress", metadata=metadata, description=description)
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green",
                    "--detail", "critère 1 déjà vert : tests/roadmap-test.py::RoadmapTest.test_rows passe au commit de départ")
        if raised:
            self.stopped_all_green_request()

    def stopped_all_green_request(self):
        request = {"quoi": f"Ticket {T1} arrêté : critères tous déjà verts",
                   "pourquoi": "Le code existant satisfait déjà ce ticket.",
                   "que_faire": [{"option": "Laisser le ticket arrêté", "consequence": "Rien ne fusionne."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        self.write_log.write_text("")

    def test_a_repair_that_moves_a_proof_stopped_all_green_is_resumed_once_without_an_answer_nor_a_round_of_the_end(self):
        self.stopped_all_green("repo_rule : docs/TEST_GUIDELINE.md : The internal functions stay forbidden: "
                               "a test that calls one is not a test of the tool.")
        rounds = self.bead(CONVOY)["metadata"].get("gc.flow.counter.end_rounds")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "proof_moved")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        shown = self.shown_state(T1)
        self.assertIsNone(shown["stop"])
        self.assertEqual("criterion_already_green", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual(rounds, self.bead(CONVOY)["metadata"].get("gc.flow.counter.end_rounds"))
        # The next pass counts and sends nothing more.
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_repair_of_a_behavior_stopped_all_green_stays_stopped_with_the_operator(self):
        self.stopped_all_green("spec_line : la page projet montre les lignes de roadmap")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual(([], []), (self.of(answer, "resumed"), self.resume_launches()))
        self.assertEqual("criterion_already_green", self.shown_state(T1)["stop"]["reason"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))
        self.assertEqual(before, self.tickets_snapshot())

    def answered_before_its_stop_request(self):
        """R12 (af-vm0vua): stopped all green at 00:52, a Planning Exception
        raised on the same bead at 00:54 and answered at 07:54, then the
        stop's own request raised and recorded raised, and cleared."""
        metadata = self.bead(T1)["metadata"]
        metadata["gc.flow.stop"] = json.dumps({**json.loads(metadata["gc.flow.stop"]), "at": "2026-01-01T00:52:47Z"})
        self.edit(T1, metadata=metadata)
        exception = {"quoi": f"Planning Exception sur {T1}", "pourquoi": "Le critère est déjà vert.",
                     "que_faire": [{"option": "a", "consequence": "a"}, {"option": "b", "consequence": "b"},
                                   {"option": "c", "consequence": "c"}],
                     "langue": "fr", "bloquant": True}
        self.env["ESCALATION_DOOR_NOW"] = "1767228840"  # 2026-01-01T00:54:00Z
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(exception))
        self.env["ESCALATION_DOOR_NOW"] = "1767254060"  # 2026-01-01T07:54:20Z
        self.run_ok(ESCALATION, "repondre", T1, "c", "--actor", "benjamin")
        del self.env["ESCALATION_DOOR_NOW"]
        self.stopped_all_green_request()

    def test_an_answer_to_an_earlier_planning_exception_does_not_hold_a_proof_moved_resume(self):
        self.stopped_all_green("repo_rule : docs/TEST_GUIDELINE.md : The internal functions stay forbidden: "
                               "a test that calls one is not a test of the tool.", raised=False)
        self.answered_before_its_stop_request()
        self.run_ok(ESCALATION, "clear", T1)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "proof_moved")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertIsNone(self.shown_state(T1)["stop"])
        self.assertEqual(1, self.resumes())

    def test_a_proof_moved_stop_answered_after_its_own_request_is_not_resumed(self):
        self.stopped_all_green("repo_rule : docs/TEST_GUIDELINE.md : The internal functions stay forbidden: "
                               "a test that calls one is not a test of the tool.", raised=False)
        self.answered_before_its_stop_request()
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop's request
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "benjamin")

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual("criterion_already_green", self.shown_state(T1)["stop"]["reason"])

    def test_a_ticket_blocked_by_a_repair_is_resumed_once_the_repair_is_closed(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "technically_blocked")
        self.edit(T1, blocks=["fx-o1"])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(0, self.resumes())
        self.run_ok(STATE, "record-gate", OTHER, "fx-o1", "--gate", "withdrawn")
        self.edit("fx-o1", status="closed")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "unblocked")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())

    def test_an_evaluation_outage_resumes_once_after_its_linked_factory_repair_is_delivered(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "evaluation_outage",
                    "--detail", "l'environnement d'évaluation a manqué 2 fois de suite")
        request = {
            "quoi": f"Ticket {T1} arrêté : l'environnement d'évaluation est en panne",
            "pourquoi": "Une panne de l'environnement n'est pas un refus.",
            "que_faire": [{"option": "Faire réparer l'environnement d'évaluation par la maintenance de l'usine",
                            "consequence": "Le ticket reprend après livraison."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        repair = "fx-er1"
        state = self.tracker_state()
        state["beads"][repair] = {
            "title": "réparer l'environnement d'évaluation", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)

        waiting = self.advance(CONVOY)
        self.assertEqual([], self.of(waiting, "resumed"))
        self.assertEqual("evaluation_outage", self.shown_state(T1)["stop"]["reason"])

        self.edit(repair, status="closed", metadata=delivered(43, "1" * 40, "2" * 40))
        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "repair_delivered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        self.assertEqual((None, None, 1),
                         (shown["stop"], shown["technical_repairs"], shown["counters"]["resumes"]))
        self.assertEqual("evaluation_outage", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_factory_technical_request_waits_for_every_linked_repair_s_delivery_proof_then_resumes_once(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {
            "quoi": "Le contrôle de l'usine est rouge",
            "pourquoi": "Le défaut est dans un test de l'usine, hors du ticket",
            "que_faire": [{"option": "Corriger par maintenance sur main", "consequence": "Le ticket reprend après livraison."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")

        repair1, repair2, unrelated = "fx-repair1", "fx-repair2", "fx-unrelated"
        state = self.tracker_state()
        state["beads"][repair1] = {
            "title": "réparation ouverte", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        state["beads"][repair2] = {
            "title": "réparation échouée", "status": "closed", "issue_type": "bug",
            "metadata": {"gc.delivery_contract": "pr-ci-merged-v1", "gc.work_outcome": "abandoned"},
        }
        state["beads"][unrelated] = {
            "title": "bug ordinaire ouvert", "status": "open", "issue_type": "bug", "metadata": {},
        }
        self.tracker.write_text(json.dumps(state))
        refused = self.run_cmd(STATE, "link-technical-repair", CONVOY, T1, "--repair", unrelated)
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("maintenance autorisée", refused.stdout + refused.stderr)
        for repair in (repair1, repair2, repair1):
            self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)
        self.assertEqual(
            [repair1, repair2],
            [entry["id"] for entry in self.shown_state(T1)["technical_repairs"]["entries"]],
        )

        waiting = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(waiting, "lifted"), self.of(waiting, "resumed")))
        self.assertEqual("operator_request", self.park_of(T1)["cause"])

        sha1, sha2, merge1, merge2 = "1" * 40, "2" * 40, "3" * 40, "4" * 40

        # One delivered repair cannot release a request whose other linked
        # repair is merely closed without merge/CI proof.
        self.edit(repair1, status="closed", metadata={"gc.delivery_contract": "pr-ci-merged-v1"})
        self.edit(repair2, status="closed", metadata=delivered(42, sha2, merge2))
        unproven = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(unproven, "lifted"), self.of(unproven, "resumed")))
        self.assertEqual("operator_request", self.park_of(T1)["cause"])

        self.edit(repair1, status="closed", metadata=delivered(41, sha1, merge1))
        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "repair_delivered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual([(T1, [T1, T3])], [(entry["id"], entry["lifted"]) for entry in self.of(answer, "lifted")])
        self.assertEqual([repair1, repair2], self.shown_state(T1)["park_lifts"][-1]["repairs"])
        self.assertIsNone(self.shown_state(T1)["technical_repairs"])
        self.assertEqual((None, None), (self.park_of(T1), self.park_of(T3)))
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual(1, self.resumes())
        writes = self.log(T1)
        lift_at = next(index for index, call in enumerate(writes)
                       if "--unset-metadata" in call and "gc.flow.park" in call)
        clear_at = next(index for index, call in enumerate(writes)
                        if any(value == "gc.needs_benjamin=none" for value in call))
        resume_at = next(index for index, call in enumerate(writes)
                         if "gc.flow.exit" in call and "gc.flow.technical_repairs" in call)
        self.assertLess(lift_at, clear_at)
        self.assertLess(clear_at, resume_at)
        self.assertNotIn("gc.flow.technical_repairs", writes[lift_at])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

        # The delivered repairs released that request, not every later
        # operator request on the same ticket.
        self.taken(T1, "auteur-human-after-repair", alive=True)
        human_request = {
            "quoi": "Décision produit nouvelle, sans rapport avec la panne réparée",
            "pourquoi": "Cette décision appartient à Benjamin",
            "que_faire": [{"option": "Conserver le comportement", "consequence": "Attendre sa réponse explicite."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(human_request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", human_request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        # Timestamps have one-second precision. Even an exact collision with
        # the released exit cannot turn this new human request into its old
        # technical generation.
        metadata = self.bead(T1)["metadata"]
        exit_record = json.loads(metadata["gc.flow.exit"])
        exit_record["at"] = self.shown_state(T1)["park_lifts"][-1]["exit_at"]
        metadata["gc.flow.exit"] = json.dumps(exit_record)
        self.edit(T1, metadata=metadata)

        second = self.advance(CONVOY)

        self.assertEqual(([], []), (self.of(second, "lifted"), self.of(second, "resumed")))
        self.assertEqual(human_request["quoi"], self.park_of(T1)["detail"])
        self.assertIn(T1, "\n".join(self.needs()))
        self.assertEqual(1, self.resumes())

    def test_a_maintenance_answer_waits_for_its_linked_repair_s_delivery_then_resumes_once(self):
        # af-fv8ca4: R13 and R20 resumed on « Corriger par maintenance sur
        # main » before their repair was linked or merged.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {
            "quoi": "Le contrôle de l'usine est rouge",
            "pourquoi": "Le défaut est dans un test de l'usine, hors du ticket",
            "que_faire": [{"option": "Corriger par maintenance sur main",
                            "consequence": "Le ticket reprend après la fusion de sa réparation."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        answered = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(answered, "lifted"), self.of(answered, "resumed")))
        self.assertEqual("operator_request", self.park_of(T1)["cause"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        refused = self.run_cmd(STATE, "lift-park", CONVOY, T1, "--request", T1, "--option", "a")
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("livraison prouvée de la réparation liée", refused.stdout + refused.stderr)

        repair, sha, merge = "fx-repair1", "1" * 40, "3" * 40
        state = self.tracker_state()
        state["beads"][repair] = {
            "title": "réparation ouverte", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)
        # A pass that read the ticket before this link writes its lift after
        # it: the write itself refuses.
        raced = self.run_cmd(STATE, "lift-park", CONVOY, T1, "--request", T1)
        self.assertNotEqual(0, raced.returncode)
        self.assertIn(f"attend ses réparations techniques liées ({repair})", raced.stdout + raced.stderr)
        linked = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(linked, "lifted"), self.of(linked, "resumed")))
        self.assertEqual("operator_request", self.park_of(T1)["cause"])

        self.edit(repair, status="closed", metadata=delivered(41, sha, merge))
        delivered_pass = self.advance(CONVOY)

        self.assertEqual([(T1, "repair_delivered")], [(r["id"], r["cause"]) for r in self.of(delivered_pass, "resumed")])
        self.assertEqual([repair], self.shown_state(T1)["park_lifts"][-1]["repairs"])
        self.assertIsNone(self.park_of(T1))
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def linked_open_repair(self, repair):
        state = self.tracker_state()
        state["beads"][repair] = {
            "title": "réparation ouverte", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)

    def repair_asks_where_to_fix(self, repair, letter):
        request = {
            "quoi": "La correction vise du code présent sur la seule branche d'intégration",
            "pourquoi": "Aucune voie de livraison n'ouvre de PR vers une branche d'intégration",
            "que_faire": [
                {"option": "Corriger dans le convoi : le ticket modifie serve_sessions",
                 "consequence": "Le ticket reprend sans attendre main."},
                {"option": "Autoriser une PR de maintenance vers l'intégration",
                 "consequence": "Une PR vise la branche d'intégration."},
            ],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", repair, json.dumps(request))
        self.run_ok(ESCALATION, "repondre", repair, letter, "--actor", "operateur-test")

    def test_a_linked_repair_answered_to_be_fixed_in_the_convoy_goes_back_to_the_ticket_s_author_once(self):
        # af-t8hycw: af-8fk8nz, linked to R20, could only change code of the
        # integration branch; answered « Corriger dans le convoi », R20 still
        # waited for its delivery on main.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {
            "quoi": "Le faux superviseur rend tout son journal d'un coup",
            "pourquoi": "Le rouge du ticket est impossible",
            "que_faire": [{"option": "Corriger par maintenance sur main : serve_sessions journalise par emit",
                            "consequence": "Le ticket reprend après la fusion de sa réparation."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")
        repair = "fx-repair1"
        self.linked_open_repair(repair)
        refused = self.run_cmd(STATE, "return-technical-repair", CONVOY, T1)
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("« Corriger dans le convoi »", refused.stdout + refused.stderr)

        self.repair_asks_where_to_fix(repair, "b")
        other = self.advance(CONVOY)
        self.assertEqual(([], [], []), (self.of(other, "returned_repairs"), self.of(other, "lifted"),
                                        self.of(other, "resumed")))
        self.assertEqual("operator_request", self.park_of(T1)["cause"])

        self.repair_asks_where_to_fix(repair, "a")
        returned = self.advance(CONVOY)

        self.assertEqual([{"id": T1, "repairs": [repair]}], self.of(returned, "returned_repairs"))
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(returned, "resumed")])
        shown = self.shown_state(T1)
        self.assertIsNone(shown["park"])
        self.assertIsNone(shown["technical_repairs"])
        self.assertEqual([repair], [entry["id"] for entry in shown["returned_repairs"]])
        self.assertEqual(shown["resume"]["entries"][-1]["exit"]["at"], shown["returned_repairs"][-1]["exit_at"])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_lifted_before_its_link_resumes_once_its_repair_is_answered_to_be_fixed_in_the_convoy(self):
        # R20 itself: lifted on the answer before af-fv8ca4, its link to
        # af-8fk8nz still bound to its operator-request exit.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", "faux superviseur")
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        repair = "fx-repair1"
        self.linked_open_repair(repair)
        metadata = dict(self.bead(T1)["metadata"])
        del metadata["gc.flow.park"]
        self.edit(T1, metadata=metadata)
        self.repair_asks_where_to_fix(repair, "a")

        returned = self.advance(CONVOY)

        self.assertEqual([{"id": T1, "repairs": [repair]}], self.of(returned, "returned_repairs"))
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(returned, "resumed")])
        self.assertIsNone(self.shown_state(T1)["technical_repairs"])

    def test_a_factory_repair_is_taken_up_and_tested_before_its_resume_is_consumed_once(self):
        self.integrated(regression="test -f budget.txt")
        self.resumable()
        self.advance(CONVOY)
        self.taken(T1, "auteur-1")
        request = {
            "quoi": "Le budget vert de l'usine manque à la branche d'intégration",
            "pourquoi": "Le correctif livré sur main n'est pas dans l'arbre que le ticket teste.",
            "que_faire": [{"option": "Reprendre main par la porte d'intégration",
                            "consequence": "Le ticket reprend seulement sur le résultat vert."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")

        repair = "fx-rmain"
        state = self.tracker_state()
        state["beads"][repair] = {
            "title": "budget vert livré", "status": "open", "issue_type": "bug",
            "labels": ["maintenance"], "metadata": {"gc.authorized_by": "af-authority"},
        }
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "link-technical-repair", CONVOY, T1, "--repair", repair)

        (self.root / "budget.txt").write_text("1140\n")
        self.git("add", "budget.txt")
        self.git("commit", "-q", "-m", "repair delivered on main")
        repair_commit = self.git("rev-parse", "main")
        proof = delivered(41, "1" * 40, repair_commit)
        proof["gc.github_repo"] = "example/fx"
        proof["gc.pr_url"] = "https://github.com/example/fx/pull/41"
        self.edit(repair, status="closed", metadata=proof)
        before = self.git("rev-parse", self.INTEGRATION)

        answer = self.advance(CONVOY)

        convoy = next(entry for entry in answer["convoys"] if entry["id"] == CONVOY)
        self.assertEqual([(T1, "repair_delivered")],
                         [(entry["id"], entry["cause"]) for entry in convoy["resumed"]], answer)
        self.assertEqual((repair, 0),
                         (convoy["repair_take_up"]["repairs"][0],
                          convoy["repair_take_up"]["tests"]["exit_code"]))
        self.assertIsNotNone(convoy["repair_take_up"]["takeover"])
        self.assertNotEqual(before, self.git("rev-parse", self.INTEGRATION))
        self.git("merge-base", "--is-ancestor", repair_commit, self.INTEGRATION)
        resumed_tip = self.git("rev-parse", self.INTEGRATION)

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "resumed"))
        self.assertEqual(resumed_tip, self.git("rev-parse", self.INTEGRATION))
        self.assertEqual(1, self.resumes())

    def test_a_legacy_delivered_repair_at_the_unblocked_bound_is_migrated_and_sent_once(self):
        # af-o5ritb: A2 (af-ocz64w) already had two `unblocked` resumes and
        # four resumes in all. Its next linked repair was counted as the third
        # `unblocked`, then parked with an empty launch instead of reaching the
        # author through the door.
        self.started_convoy()
        self.taken(T1, "auteur-a2")
        self.earlier_resumes("answered", 1)
        self.earlier_resumes("unblocked", 2)
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.run_ok(STATE, "open-resume", CONVOY, T1, "--cause", "unblocked",
                    "--ref", "repairs:b39d09d98a2aa52e/exit:2026-11-02T05:41:08Z")
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "resumes_exhausted",
                    "--detail", "reprises épuisées pour la cause unblocked (5 reprises en tout)")
        metadata = self.bead(T1)["metadata"]
        resume = json.loads(metadata["gc.flow.resume"])
        # Exact durable entry reported by af-ihjw25 on af-ocz64w. It predates
        # `repair_delivered`, so its preserved evaluation stop was lifted by
        # `unblocked`; the current reader must accept it only through the
        # narrow migration of the final, still-unlaunched repair signal.
        resume["entries"][1] = {
            "at": "2026-11-02T00:39:47Z", "cause": "unblocked",
            "exit": {"at": "2026-10-30T18:24:02Z", "exit": "finished"},
            "launches": [{"at": "2026-11-02T00:40:01Z", "bead": "af-vokni8"}],
            "ref": "repairs:ab580b5b24002f19/stop:2026-10-30T21:06:32Z",
            "session": "delivery-author-af-wisp-ea4lfm",
            "stop": {"at": "2026-10-30T21:06:32Z",
                     "detail": "l'environnement d'évaluation a manqué 2 fois de suite au commit 0de042ff0bf7",
                     "raised": "2026-10-30T21:06:41Z", "reason": "evaluation_outage"},
        }
        metadata["gc.flow.resume"] = json.dumps(resume)
        self.edit(T1, metadata=metadata)
        before = self.bead(T1)["metadata"]
        before_resume = json.loads(before["gc.flow.resume"])["entries"]
        self.assertEqual((5, "resumes_exhausted", "unblocked", "evaluation_outage", 1, "unblocked", []),
                         (before["gc.flow.counter.resumes"], json.loads(before["gc.flow.park"])["cause"],
                          before_resume[1]["cause"], before_resume[1]["stop"]["reason"],
                          len(before_resume[1]["launches"]), before_resume[-1]["cause"],
                          before_resume[-1]["launches"]))
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "repair_delivered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        last = shown["resume"]["entries"][-1]
        self.assertEqual((5, None, "repair_delivered", 1, 2),
                         (shown["counters"]["resumes"], shown["park"], last["cause"], len(last["launches"]),
                          shown["resumes_left_by_cause"]["repair_delivered"]))
        self.assertIsNone(shown["technical_repairs"])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, len(self.resume_launches()))

    def test_a_malformed_legacy_resume_is_left_to_the_incident_door_without_crashing(self):
        self.started_convoy()
        metadata = self.bead(T1)["metadata"]
        metadata["gc.flow.resume"] = json.dumps({"entries": 1})
        self.edit(T1, metadata=metadata)

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        convoy = next(entry for entry in answer["convoys"] if entry["id"] == CONVOY)
        self.assertEqual(([], "état sans règle"), (convoy["resumed"], convoy["signal"]))
        self.assertTrue(convoy["incident"]["raised"])
        self.assertEqual("gc.flow.resume", convoy["unruled"][0]["field"])
        self.assertEqual({"entries": 1}, json.loads(self.bead(T1)["metadata"]["gc.flow.resume"]))

    def test_a_finished_ticket_behind_the_integration_tip_goes_back_to_its_author_once_and_is_counted(self):
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        self.integration_moved()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "behind")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(["sling", "fx-worker", self.of(answer, "resumed")[0]["bead"], "fx-resume"],
                         self.resume_launches()[-1][:4])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, f"ticket/{T1}", tip),
                         (shown["counters"]["resumes"], shown["exit"], shown["branch"], shown["tip"]))
        self.assertEqual(([], []), (self.code_review_launches(), self.evaluation_launches()))
        self.assertIsNone(shown["verdicts"].get("code_review"))
        self.assertNotIn(T1, [m["id"] for m in (self.integration_of(answer) or {}).get("merged", [])])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_behind_after_many_merges_of_others_is_resumed_and_never_parked(self):
        # af-npz9v1.36 (Benjamin, 27/10/2026 15:45 Paris: « oui les 6 »): ticket
        # D was parked on 23/10 after 8 resumes, each merge of another ticket
        # moving the integration branch. Those resumes no longer count in K.
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.earlier_resumes("behind", 8, refs=[f"integration:{n:040x}/exit:{n}" for n in range(8)])
        self.integration_moved()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "behind")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual([], self.of(answer, "parked"))
        shown = self.shown_state(T1)
        self.assertEqual((9, None, 3), (shown["counters"]["resumes"], shown["park"],
                                        shown["resumes_left_by_cause"]["behind"]))

    def test_a_ticket_that_never_takes_the_integration_tip_is_parked_by_the_guard(self):
        # The guard against an endless loop: on a tip already resumed for, a
        # finished ticket that did not take it is counted, and parked at the bound.
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        tip = self.integration_moved()
        self.earlier_resumes("behind", 3, refs=[f"integration:{tip}/exit:old{n}" for n in range(3)])

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        self.assertEqual([], self.of(answer, "resumed"))
        self.assertIn("behind : une même pointe d'intégration reprise sans être prise", self.park_of(T1)["detail"])

    def test_a_finished_ticket_that_holds_the_integration_tip_is_reviewed_and_not_resumed(self):
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.integration_moved()
        self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual(1, len(self.code_review_launches()))

    def test_a_ticket_the_merge_returned_is_resumed_and_the_resume_is_counted(self):
        self.integrated(regression="false")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)  # the merge returns it: red tests on the merged result

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "returned")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_finished_without_its_green_at_the_tip_goes_back_to_its_author_once(self):
        # af-1row55: R16 finished at a tip its green was not proven at; the
        # review and the evaluation wait for a green tip, nothing moved it.
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        # Its regression proven one commit before the tip it finished at.
        before = self.git("rev-parse", f"{tip}~1")
        self.run_ok(STATE, "set-tdd", CONVOY, T1, "--step", "prefactoring", "--commit", before, "--base", before)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "returned")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(f"unproven:{tip}/", self.shown_state(T1)["resume"]["entries"][-1]["ref"][:len(tip) + 10])
        self.assertEqual(1, self.resumes())
        self.assertEqual([], self.code_review_launches())
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_the_exact_delivered_release_sends_D_s_counted_returned_resume_once(self):
        authorization = self.exact_returned_release()
        env = {**self.env, RETURNED_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        before_resume = json.loads(before["gc.flow.resume"])
        before_decisions = {key: value for key, value in before.items()
                            if key.startswith("gc.escalation_response_") or key == "gc.needs_benjamin"}

        answer = self.advance(CONVOY, env=env)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, None, RETURNED_RELEASE_MAINTENANCE, [T1, T3], "returned_once"),
                         (lifted["id"], lifted["option"], lifted["request"], lifted["lifted"], lifted["release"]))
        self.assertEqual([(T1, "returned")], [(entry["id"], entry["cause"])
                                               for entry in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        after = self.bead(T1)["metadata"]
        after_resume = json.loads(after["gc.flow.resume"])
        self.assertIsNone(shown["park"])
        self.assertEqual(before["gc.flow.counter.resumes"], after["gc.flow.counter.resumes"])
        self.assertEqual(before_resume["entries"][:-1], after_resume["entries"][:-1])
        self.assertEqual({**before_resume["entries"][-1], "launches": after_resume["entries"][-1]["launches"]},
                         after_resume["entries"][-1])
        self.assertEqual(1, len(after_resume["entries"][-1]["launches"]))
        self.assertEqual(before_decisions, {key: value for key, value in after.items()
                                            if key.startswith("gc.escalation_response_")
                                            or key == "gc.needs_benjamin"})
        self.assertEqual([], self.log("clear"))

        again = self.advance(CONVOY, env=env)

        self.assertEqual(([], 1), (self.of(again, "resumed"), len(self.resume_launches())))
        self.assertIsNone(self.park_of(T1))
        self.assertEqual(before["gc.flow.counter.resumes"], self.resumes())

    def test_the_repaired_D_result_is_judged_without_another_author_resume(self):
        authorization = self.exact_returned_result_release()
        env = {**self.env, RETURNED_RESULT_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        before_resume = json.loads(before["gc.flow.resume"])
        before_lifts = json.loads(before["gc.flow.park_lifts"])["entries"]
        before_left = self.shown_state(T1)["resumes_left_by_cause"]
        author_launches = len(self.resume_launches())

        answer = self.advance(CONVOY, env=env)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, None, RETURNED_RESULT_RELEASE_REPAIR, [T1, T3], "returned_result_once"),
                         (lifted["id"], lifted["option"], lifted["request"], lifted["lifted"], lifted["release"]))
        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(author_launches, len(self.resume_launches()))
        self.assertEqual((None, None), (self.park_of(T1), self.park_of(T3)))
        after = self.bead(T1)["metadata"]
        shown = self.shown_state(T1)
        self.assertEqual(13, after["gc.flow.counter.resumes"])
        self.assertEqual(before_resume, json.loads(after["gc.flow.resume"]))
        self.assertEqual(3, shown["resumes_left_by_cause"]["returned"])
        self.assertEqual({key: value for key, value in before_left.items() if key != "returned"},
                         {key: value for key, value in shown["resumes_left_by_cause"].items()
                          if key != "returned"})
        after_lifts = shown["park_lifts"]
        self.assertEqual(before_lifts, after_lifts[:-1])
        self.assertEqual((RETURNED_RESULT_RELEASE_REPAIR, None, "returned"),
                         tuple(after_lifts[-1][key] for key in ("request", "option", "reset_cause")))
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(answer)["launched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.evaluation_of(answer)["started"]])

        again = self.advance(CONVOY, env=env)

        self.assertEqual(([], [], 1),
                         (self.of(again, "lifted"), self.of(again, "resumed"), len(self.code_review_launches())))
        self.assertIsNone(self.evaluation_of(again))

    def test_the_repaired_D_result_release_rejects_nearby_state_and_incomplete_delivery(self):
        authorization = self.exact_returned_result_release()
        seeded = self.tracker.read_text()

        def wrong_tip(state, auth):
            auth["tip"] = "0" * 40

        def wrong_exit(state, auth):
            auth["exit_at"] = "2000-01-01T00:00:00Z"

        def wrong_park(state, auth):
            auth["parked_at"] = "2000-01-01T00:00:00Z"

        def wrong_resume(state, auth):
            auth["resume_at"] = "2000-01-01T00:00:00Z"

        def wrong_launch(state, auth):
            auth["resume_bead"] = "fx-other"

        def wrong_history(state, auth):
            lifts = json.loads(state["beads"][T1]["metadata"]["gc.flow.park_lifts"])
            lifts["entries"][-1]["taken"]["returned"] = 1
            state["beads"][T1]["metadata"]["gc.flow.park_lifts"] = json.dumps(lifts)

        def undelivered_repair(state, auth):
            state["beads"][RETURNED_RESULT_RELEASE_REPAIR]["status"] = "open"

        changes = (
            ("tip", wrong_tip), ("exit", wrong_exit), ("parking", wrong_park),
            ("resume", wrong_resume), ("launch", wrong_launch), ("history", wrong_history),
            ("delivery", undelivered_repair),
        )
        for name, change in changes:
            with self.subTest(name=name):
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))

                answer = self.advance(CONVOY, env={**self.env, RETURNED_RESULT_RELEASE_ENV: json.dumps(auth)})

                self.assertEqual(([], []), (self.of(answer, "lifted"), self.of(answer, "resumed")), name)
                self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"], name)
                self.assertEqual([], self.resume_launches(), name)
                self.assertIsNone(self.code_review_of(answer), name)
                self.assertIsNone(self.evaluation_of(answer), name)

    def test_the_returned_release_rejects_every_nearby_state(self):
        authorization = self.exact_returned_release()
        seeded = self.tracker.read_text()

        def wrong_ticket(state, auth):
            auth["ticket"] = T2

        def wrong_park(state, auth):
            park = json.loads(state["beads"][T1]["metadata"]["gc.flow.park"])
            park["at"] = "2000-01-01T00:00:00Z"
            state["beads"][T1]["metadata"]["gc.flow.park"] = json.dumps(park)

        def wrong_merge(state, auth):
            merge = json.loads(state["beads"][T1]["metadata"]["gc.flow.merge"])
            merge["commit"] = "0" * 40
            state["beads"][T1]["metadata"]["gc.flow.merge"] = json.dumps(merge)

        def wrong_integration(state, auth):
            merge = json.loads(state["beads"][T1]["metadata"]["gc.flow.merge"])
            merge["integration"] = "0" * 40
            state["beads"][T1]["metadata"]["gc.flow.merge"] = json.dumps(merge)

        def wrong_current_tip(state, auth):
            self.git("update-ref", f"refs/heads/{self.INTEGRATION}", auth["repair_commit"])

        def wrong_ancestor(state, auth):
            merge = json.loads(state["beads"][RETURNED_RELEASE_REPAIR]["metadata"]["gc.flow.merge"])
            merge["ticket_commit"] = self.returned_release_unrelated
            state["beads"][RETURNED_RELEASE_REPAIR]["metadata"]["gc.flow.merge"] = json.dumps(merge)
            auth["repair_commit"] = self.returned_release_unrelated

        def undelivered_maintenance(state, auth):
            state["beads"][RETURNED_RELEASE_MAINTENANCE]["status"] = "open"

        for name, change in (("ticket", wrong_ticket), ("park", wrong_park), ("merge", wrong_merge),
                             ("integration", wrong_integration), ("current tip", wrong_current_tip),
                             ("ancestor", wrong_ancestor), ("maintenance", undelivered_maintenance)):
            with self.subTest(name=name):
                self.git("update-ref", f"refs/heads/{self.INTEGRATION}", authorization["integration_tip"])
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))

                answer = self.advance(CONVOY, env={**self.env, RETURNED_RELEASE_ENV: json.dumps(auth)})

                self.assertEqual([], self.of(answer, "lifted"), name)
                self.assertEqual([], self.of(answer, "resumed"), name)
                self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"], name)
                self.assertEqual([], self.resume_launches(), name)

    def test_the_exact_delivered_C2b_release_becomes_one_native_repair_resume(self):
        authorization = self.exact_c2b_release()
        env = {**self.env, C2B_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        before_resume = json.loads(before["gc.flow.resume"])
        protected = {key: value for key, value in before.items()
                     if key.startswith("gc.flow.verdict.") or key.startswith("gc.escalation_")
                     or key == "gc.needs_benjamin"}

        answer = self.advance(CONVOY, env=env)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, None, C2B_RELEASE_REPAIR, [T1, T3], "repair_delivered_once"),
                         (lifted["id"], lifted["option"], lifted["request"], lifted["lifted"], lifted["release"]))
        self.assertEqual([(T1, "repair_delivered")],
                         [(entry["id"], entry["cause"]) for entry in self.of(answer, "resumed")])
        after = self.bead(T1)["metadata"]
        after_resume = json.loads(after["gc.flow.resume"])
        self.assertIsNone(self.park_of(T1))
        self.assertIsNone(self.park_of(T3))
        self.assertEqual(before["gc.flow.counter.resumes"], after["gc.flow.counter.resumes"])
        self.assertEqual(before_resume["entries"][:-1], after_resume["entries"][:-1])
        self.assertEqual({**before_resume["entries"][-1], "cause": "repair_delivered",
                          "launches": after_resume["entries"][-1]["launches"]}, after_resume["entries"][-1])
        self.assertEqual(1, len(after_resume["entries"][-1]["launches"]))
        self.assertEqual(protected, {key: value for key, value in after.items()
                                     if key.startswith("gc.flow.verdict.") or key.startswith("gc.escalation_")
                                     or key == "gc.needs_benjamin"})
        self.assertEqual(([], []), (self.log("clear"), self.log("repondre")))

        again = self.advance(CONVOY, env=env)

        self.assertEqual(([], 1), (self.of(again, "resumed"), len(self.resume_launches())))
        self.assertEqual(before["gc.flow.counter.resumes"], self.resumes())

    def test_the_C2b_release_rejects_nearby_state_and_incomplete_delivery_proof(self):
        authorization = self.exact_c2b_release()
        seeded = self.tracker.read_text()

        def wrong_ticket(state, auth):
            auth["ticket"] = T2

        def wrong_park(state, auth):
            park = json.loads(state["beads"][T1]["metadata"]["gc.flow.park"])
            park["at"] = "2000-01-01T00:00:00Z"
            state["beads"][T1]["metadata"]["gc.flow.park"] = json.dumps(park)

        def wrong_resume(state, auth):
            resume = json.loads(state["beads"][T1]["metadata"]["gc.flow.resume"])
            resume["entries"][-1]["at"] = "2000-01-01T00:00:00Z"
            state["beads"][T1]["metadata"]["gc.flow.resume"] = json.dumps(resume)

        def wrong_ref(state, auth):
            resume = json.loads(state["beads"][T1]["metadata"]["gc.flow.resume"])
            resume["entries"][-1]["ref"] = f"integration:{'0' * 40}/stop:{auth['stop_at']}"
            state["beads"][T1]["metadata"]["gc.flow.resume"] = json.dumps(resume)

        def wrong_stop(state, auth):
            resume = json.loads(state["beads"][T1]["metadata"]["gc.flow.resume"])
            resume["entries"][-1]["stop"]["at"] = "2000-01-01T00:00:00Z"
            state["beads"][T1]["metadata"]["gc.flow.resume"] = json.dumps(resume)

        def already_launched(state, auth):
            resume = json.loads(state["beads"][T1]["metadata"]["gc.flow.resume"])
            resume["entries"][-1]["launches"] = [{"at": "2026-11-05T06:49:00Z", "bead": "fx-old3"}]
            state["beads"][T1]["metadata"]["gc.flow.resume"] = json.dumps(resume)

        def wrong_session(state, auth):
            resume = json.loads(state["beads"][T1]["metadata"]["gc.flow.resume"])
            resume["entries"][-1]["session"] = "auteur-voisin"
            state["beads"][T1]["metadata"]["gc.flow.resume"] = json.dumps(resume)

        def undelivered_repair(state, auth):
            state["beads"][C2B_RELEASE_REPAIR]["status"] = "open"

        def wrong_repair_merge(state, auth):
            state["beads"][C2B_RELEASE_REPAIR]["metadata"]["gc.merge_commit"] = "8" * 40

        def undelivered_migration(state, auth):
            state["beads"][C2B_RELEASE_MIGRATION]["status"] = "open"

        changes = (
            ("ticket", wrong_ticket), ("parking", wrong_park), ("resume", wrong_resume),
            ("integration reference", wrong_ref), ("stop", wrong_stop), ("already launched", already_launched),
            ("session", wrong_session), ("repair delivery", undelivered_repair),
            ("repair merge", wrong_repair_merge), ("migration delivery", undelivered_migration),
        )
        for name, change in changes:
            with self.subTest(name=name):
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))

                answer = self.advance(CONVOY, env={**self.env, C2B_RELEASE_ENV: json.dumps(auth)})

                self.assertEqual([], self.of(answer, "lifted"), name)
                self.assertEqual([], self.of(answer, "resumed"), name)
                self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"], name)
                self.assertEqual([], self.resume_launches(), name)

    def test_the_repaired_C2b_result_is_judged_without_another_author_resume(self):
        authorization = self.exact_c2b_result_release()
        env = {**self.env, C2B_RESULT_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        before_resume = json.loads(before["gc.flow.resume"])
        before_lifts = json.loads(before["gc.flow.park_lifts"])["entries"]
        before_decisions = {key: value for key, value in before.items()
                            if key.startswith("gc.escalation_response_") or key == "gc.needs_benjamin"}

        answer = self.advance(CONVOY, env=env)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, None, C2B_RESULT_RELEASE_REPAIR, [T1, T3], "c2b_result_once"),
                         (lifted["id"], lifted["option"], lifted["request"], lifted["lifted"], lifted["release"]))
        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([], self.resume_launches())
        self.assertEqual((None, None), (self.park_of(T1), self.park_of(T3)))
        after = self.bead(T1)["metadata"]
        self.assertEqual(6, after["gc.flow.counter.resumes"])
        self.assertEqual(before_resume, json.loads(after["gc.flow.resume"]))
        shown = self.shown_state(T1)
        self.assertEqual(3, shown["resumes_left_by_cause"]["commit_after_verdict"])
        self.assertEqual(1, shown["resumes_left_by_cause"]["evaluation_no_result"])
        self.assertEqual(2, shown["resumes_left_by_cause"]["repair_delivered"])
        self.assertEqual(before_lifts, shown["park_lifts"][:-1])
        self.assertEqual((C2B_RESULT_RELEASE_REPAIR, None, "commit_after_verdict"),
                         tuple(shown["park_lifts"][-1][key] for key in ("request", "option", "reset_cause")))
        self.assertEqual(before_decisions, {key: value for key, value in after.items()
                                            if key.startswith("gc.escalation_response_")
                                            or key == "gc.needs_benjamin"})
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(answer)["launched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.evaluation_of(answer)["started"]])

        again = self.advance(CONVOY, env=env)

        self.assertEqual(([], [], 1),
                         (self.of(again, "lifted"), self.of(again, "resumed"), len(self.code_review_launches())))
        self.assertEqual({}, self.evaluation_of(again))

    def test_the_cleaned_C2b_evaluation_request_is_rebuilt_once_without_an_author_resume(self):
        authorization = self.exact_cleaned_c2b_evaluation()
        env = {**self.env, C2B_EVALUATION_RECOVERY_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        review = before["gc.flow.code_review"]
        shown = self.shown_state(T1)
        latest = shown["resume"]["entries"][-1]
        self.assertEqual((authorization["ticket"], authorization["tip"], None,
                          authorization["parked_at"], authorization["session"], 7, 0),
                         (shown["id"], shown["tip"], shown["exit"], shown["park"]["at"],
                          shown["session"]["name"], shown["counters"]["resumes"], shown["resumes_left"]))
        self.assertEqual(("finished", authorization["exit_at"]),
                         (latest["exit"]["exit"], latest["exit"]["at"]))
        self.assertEqual((authorization["resume_at"], authorization["stop_at"], [], 0, 2),
                         (latest["at"], latest["stop"]["at"], latest["launches"],
                          shown["resumes_left_by_cause"]["evaluation_no_result"], len(shown["park_lifts"])))
        self.assertEqual(("evaluation_no_result",
                          f"integration:{authorization['integration_tip']}/stop:{authorization['stop_at']}",
                          authorization["session"], "evaluation_no_result", authorization["previous_repair"],
                          "commit_after_verdict"),
                         (latest["cause"], latest["ref"], latest["session"], latest["stop"]["reason"],
                          shown["park_lifts"][-1]["request"], shown["park_lifts"][-1]["reset_cause"]))
        recorded_review = json.loads(review)["rounds"][-1]
        self.assertEqual((authorization["tip"], "unfavorable", authorization["blocking_findings"]),
                         (recorded_review["commit"], recorded_review["verdict"],
                          ",".join(finding["id"] for finding in recorded_review["findings"]
                                   if finding["blocking"])))
        for name in ("first_launch", "cleaned_launch"):
            route = self.bead(authorization[name])
            self.assertEqual(("closed", "mol-ticket-evaluation"),
                             (route["status"], route["metadata"]["gc.dispatch_formula"]))
        repair = self.bead(authorization["repair_bead"])
        self.assertEqual(("closed", "merged", "success", "main"),
                         (repair["status"], repair["metadata"]["gc.delivery_status"],
                          repair["metadata"]["gc.ci_conclusion"], repair["metadata"]["merged_target"]))

        answer = self.advance(CONVOY, env=env)

        self.assertEqual(["c2b_evaluation_once"], [entry["release"] for entry in self.of(answer, "lifted")], answer)
        self.assertIsNotNone(self.evaluation_of(answer), answer)
        [launched] = self.evaluation_of(answer)["launched"]
        after = self.shown_state(T1)
        request = after["evaluation"]["request"]
        self.assertEqual(T1, launched["ticket"])
        self.assertEqual(1, len(request["launches"]))
        self.assertEqual(("finished", authorization["exit_at"]),
                         (after["exit"]["exit"], after["exit"]["at"]))
        self.assertEqual((None, None), (self.park_of(T1), self.park_of(T3)))
        self.assertEqual((7, [], review),
                         (self.resumes(), self.resume_launches(), self.bead(T1)["metadata"]["gc.flow.code_review"]))
        launch_bead = request["launches"][0]["bead"]
        step = self.bead(f"{launch_bead}-step")
        self.assertEqual(("open", None), (step["status"], step["metadata"].get("gc.claimed_at")))

        again = self.advance(CONVOY, env=env)

        same = self.shown_state(T1)["evaluation"]["request"]
        self.assertEqual(request, same)
        self.assertEqual([0], [entry["launches"] for entry in self.evaluation_of(again)["pending"]])
        self.assertEqual((7, [], review),
                         (self.resumes(), self.resume_launches(), self.bead(T1)["metadata"]["gc.flow.code_review"]))

    def test_the_repaired_C2b_result_release_rejects_nearby_state_and_incomplete_delivery(self):
        authorization = self.exact_c2b_result_release()
        seeded = self.tracker.read_text()

        def wrong_tip(state, auth):
            auth["tip"] = "0" * 40

        def wrong_exit(state, auth):
            auth["exit_at"] = "2000-01-01T00:00:00Z"

        def wrong_park(state, auth):
            auth["parked_at"] = "2000-01-01T00:00:00Z"

        def wrong_resume(state, auth):
            auth["resume_at"] = "2000-01-01T00:00:00Z"

        def wrong_launch(state, auth):
            auth["resume_bead"] = "fx-other"

        def wrong_invalidation(state, auth):
            auth["invalidated_at"] = "2000-01-01T00:00:00Z"

        def wrong_history(state, auth):
            lifts = json.loads(state["beads"][T1]["metadata"]["gc.flow.park_lifts"])
            lifts["entries"][0]["at"] = "2000-01-01T00:00:00Z"
            state["beads"][T1]["metadata"]["gc.flow.park_lifts"] = json.dumps(lifts)

        def undelivered_repair(state, auth):
            state["beads"][C2B_RESULT_RELEASE_REPAIR]["status"] = "open"

        changes = (
            ("tip", wrong_tip), ("exit", wrong_exit), ("parking", wrong_park),
            ("resume", wrong_resume), ("launch", wrong_launch),
            ("invalidation", wrong_invalidation), ("history", wrong_history),
            ("delivery", undelivered_repair),
        )
        for name, change in changes:
            with self.subTest(name=name):
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))

                answer = self.advance(CONVOY, env={**self.env, C2B_RESULT_RELEASE_ENV: json.dumps(auth)})

                self.assertEqual(([], []), (self.of(answer, "lifted"), self.of(answer, "resumed")), name)
                self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"], name)
                self.assertEqual([], self.resume_launches(), name)
                self.assertIsNone(self.code_review_of(answer), name)
                self.assertIsNone(self.evaluation_of(answer), name)

    def test_the_exact_answered_R8_is_closed_without_merge_then_its_control_runs_green(self):
        authorization = self.exact_r8_close_release()
        env = {**self.env, R8_CLOSE_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)["metadata"]
        before_resume = before["gc.flow.resume"]
        before_response = {key: value for key, value in before.items()
                           if key.startswith("gc.escalation_response_")}

        answer = self.advance(CONVOY, env=env)

        after = self.bead(T1)
        shown = self.shown_state(T1)
        self.assertEqual("closed", after["status"])
        self.assertIn("withdrawn", shown["gates"])
        self.assertIsNone(shown["merge"])
        self.assertEqual(before_resume, after["metadata"]["gc.flow.resume"])
        self.assertEqual(before_response, {key: value for key, value in after["metadata"].items()
                                           if key.startswith("gc.escalation_response_")})
        self.assertNotIn(T1, "\n".join(self.needs()))
        self.assertEqual([], self.resume_launches())
        release = self.of(answer, "closed_without_merge")
        self.assertEqual((T1, R8_CLOSE_RELEASE_REPAIR, 0),
                         (release["ticket"], release["repair"], release["tests"]["exit_code"]))
        shown_convoy = json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"]
        self.assertIsNone(shown_convoy["integration_red"])

        again = self.advance(CONVOY, env=env)

        self.assertEqual([], self.of(again, "closed_without_merge"))
        self.assertEqual([], self.resume_launches())

    def test_the_exact_answered_R6_and_R7_are_withdrawn_together_after_delivery(self):
        authorization = self.exact_r6_r7_withdrawal()
        env = {**self.env, R6_R7_WITHDRAWAL_ENV: json.dumps(authorization)}
        before_unrelated = self.tickets_snapshot(T3, "fx-o1", "fx-p1")
        before_responses = {
            ticket_id: {key: value for key, value in self.bead(ticket_id)["metadata"].items()
                        if key.startswith("gc.escalation_response_")}
            for ticket_id in (T1, T2)
        }

        answer = self.advance(CONVOY, env=env)

        for ticket_id in (T1, T2):
            ticket_state = self.shown_state(ticket_id)
            self.assertEqual("closed", self.bead(ticket_id)["status"])
            self.assertIn("withdrawn", ticket_state["gates"])
            self.assertIsNone(ticket_state["merge"])
            self.assertEqual(before_responses[ticket_id], {
                key: value for key, value in self.bead(ticket_id)["metadata"].items()
                if key.startswith("gc.escalation_response_")
            })
            self.assertNotIn(ticket_id, "\n".join(self.needs()))
        self.assertEqual(before_unrelated, self.tickets_snapshot(T3, "fx-o1", "fx-p1"))
        self.assertEqual([], self.resume_launches())
        release = self.of(answer, "withdrawn_by_decision")
        self.assertEqual(
            ([T1, T2], R6_R7_WITHDRAWAL_REPAIR),
            (release["withdrawn"], release["repair"]),
        )

        before_second_pass = self.tickets_snapshot(T1, T2)
        again = self.advance(CONVOY, env=env)

        self.assertEqual(before_second_pass, self.tickets_snapshot(T1, T2))
        self.assertEqual([], self.of(again, "withdrawn_by_decision"))

    def test_the_R6_R7_withdrawal_rejects_every_nearby_state_before_writing(self):
        authorization = self.exact_r6_r7_withdrawal()
        seeded = self.tracker.read_text()

        def wrong_identity(state, auth):
            auth["tickets"][0]["ticket"] = "fx-not-r6"

        def wrong_tip(state, auth):
            auth["tickets"][0]["tip"] = "0" * 40

        def wrong_exit(state, auth):
            auth["tickets"][0]["exit_at"] = "2000-01-01T00:00:00Z"

        def wrong_parking(state, auth):
            auth["tickets"][1]["parked_at"] = "2000-01-01T00:00:00Z"

        def wrong_response(state, auth):
            state["beads"][T2]["metadata"]["gc.escalation_response_option"] = "a"

        def already_merged(state, auth):
            tip = auth["tickets"][0]["tip"]
            state["beads"][T1]["metadata"]["gc.flow.merge"] = json.dumps({
                "at": "2026-11-07T00:00:00Z", "outcome": "merged",
                "ticket_commit": tip, "integration": tip, "commit": tip,
            })

        for name, change in (
            ("identity", wrong_identity), ("tip", wrong_tip), ("exit", wrong_exit),
            ("parking", wrong_parking), ("response", wrong_response), ("merge", already_merged),
        ):
            with self.subTest(name=name):
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))
                before = self.tickets_snapshot(T1, T2, T3)

                answer = self.advance(
                    CONVOY, expect=1, env={**self.env, R6_R7_WITHDRAWAL_ENV: json.dumps(auth)}
                )

                self.assertEqual(before, self.tickets_snapshot(T1, T2, T3), name)
                release = self.of(answer, "withdrawn_by_decision")
                self.assertIn("refus : retrait R6/R7", release["error"], name)
                self.assertEqual([], release["withdrawn"], name)

    def test_the_exact_R8_close_retry_finishes_after_its_durable_native_lift(self):
        authorization = self.exact_r8_close_release()
        env = {**self.env, R8_CLOSE_RELEASE_ENV: json.dumps(authorization)}
        # The durable first write of the R8 release, which withdraws next.
        self.run_ok(STATE, "lift-park", CONVOY, T1, "--request", T1, "--option", "a", "--withdrawing")

        answer = self.advance(CONVOY, env=env)

        self.assertEqual("closed", self.bead(T1)["status"])
        self.assertIn("withdrawn", self.shown_state(T1)["gates"])
        self.assertEqual([], self.resume_launches())
        release = self.of(answer, "closed_without_merge")
        self.assertEqual((T1, [], None),
                         (release["ticket"], release["lifted"], release.get("tests")))

    def test_the_current_R8_after_generic_lift_closes_without_another_author(self):
        authorization = self.exact_r8_close_release_after_generic_lift()
        env = {**self.env, R8_CLOSE_RELEASE_ENV: json.dumps(authorization)}
        before = self.bead(T1)
        before_state = self.shown_state(T1)
        before_other = self.bead(T2)
        before_lifts = json.loads(before["metadata"]["gc.flow.park_lifts"])["entries"]
        preserved = {
            key: value for key, value in before["metadata"].items()
            if key == "gc.flow.resume" or key.startswith("gc.flow.counter.")
            or key.startswith("gc.flow.evidence.") or key.startswith("gc.escalation_response_")
        }

        answer = self.advance(CONVOY, env=env)

        after = self.bead(T1)
        after_state = self.shown_state(T1)
        after_lifts = json.loads(after["metadata"]["gc.flow.park_lifts"])["entries"]
        self.assertEqual("closed", after["status"])
        self.assertIn("withdrawn", after_state["gates"])
        self.assertIsNone(after_state["merge"])
        self.assertEqual(before_state["tip"], after_state["tip"])
        self.assertEqual(preserved, {key: after["metadata"].get(key) for key in preserved})
        self.assertEqual(before_lifts, after_lifts[:-1])
        self.assertEqual(("a", T1), (after_lifts[-1]["option"], after_lifts[-1]["request"]))
        self.assertEqual(before_other, self.bead(T2))
        self.assertEqual([], self.resume_launches())
        release = self.of(answer, "closed_without_merge")
        self.assertEqual((T1, R8_CLOSE_CURRENT_REPAIR, 0),
                         (release["ticket"], release["repair"], release["tests"]["exit_code"]))

        again = self.advance(CONVOY, env=env)

        self.assertEqual([], self.of(again, "closed_without_merge"))
        self.assertEqual([], self.resume_launches())

    def test_the_exact_answered_R8_closes_without_merge_and_one_repair_follows_a_red_control(self):
        authorization = self.exact_r8_close_release(regression="false")
        env = {**self.env, R8_CLOSE_RELEASE_ENV: json.dumps(authorization)}
        repair = "fx-r8red"
        state = self.tracker_state()
        state["beads"][repair] = {
            **ticket(repair),
            "title": f"Rétablir le contrôle rouge de la branche d'intégration ({authorization['tip'][:12]})",
            "metadata": {"gc.ticket_kind": "repair"},
        }
        state["beads"][CONVOY]["tracks"].append(repair)
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "mark", CONVOY, "--demonstration-line",
                    f"{repair}=La commande de régression se termine avec le code 0")
        self.write_log.write_text("")

        answer = self.advance(CONVOY, env=env)

        self.assertEqual("closed", self.bead(T1)["status"])
        self.assertIn("withdrawn", self.shown_state(T1)["gates"])
        release = self.of(answer, "closed_without_merge")
        self.assertEqual((T1, R8_CLOSE_RELEASE_REPAIR), (release["ticket"], release["repair"]))
        shown = json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"]
        red = shown["integration_red"]
        self.assertIsNotNone(red)
        self.assertIn("commande de régression (false)", red["control"])
        self.assertEqual(repair, red["repair"])
        self.assertEqual({"id": repair, "published": False}, self.of(answer, "repair"))

        again = self.advance(CONVOY, env=env)

        self.assertEqual([], self.of(again, "closed_without_merge"))
        matching = [entry for entry in self.tracker_state()["beads"].values()
                    if entry.get("title", "").startswith("Rétablir le contrôle rouge de la branche d'intégration")]
        self.assertEqual(1, len(matching))
        shown_again = json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"]
        self.assertEqual(red["repair"], shown_again["integration_red"]["repair"])

    def test_the_R8_close_release_rejects_nearby_state_and_option_b(self):
        authorization = self.exact_r8_close_release()
        seeded = self.tracker.read_text()

        def wrong_tip(state, auth):
            auth["tip"] = "0" * 40

        def wrong_parking(state, auth):
            auth["parked_at"] = "2000-01-01T00:00:00Z"

        def option_b(state, auth):
            auth["response_option"] = "b"
            state["beads"][T1]["metadata"]["gc.escalation_response_option"] = "b"

        def wrong_resume_cause(state, auth):
            auth["resume_cause"] = "repair_delivered"

        def undelivered_repair(state, auth):
            state["beads"][R8_CLOSE_RELEASE_REPAIR]["status"] = "open"

        def wrong_merge_target(state, auth):
            state["beads"][R8_CLOSE_RELEASE_REPAIR]["metadata"]["merged_target"] = "dev"

        for name, change in (("tip", wrong_tip), ("parking", wrong_parking),
                             ("option b", option_b), ("resume cause", wrong_resume_cause),
                             ("delivery", undelivered_repair), ("merge target", wrong_merge_target)):
            with self.subTest(name=name):
                self.tracker.write_text(seeded)
                self.write_log.write_text("")
                state = self.tracker_state()
                auth = json.loads(json.dumps(authorization))
                change(state, auth)
                self.tracker.write_text(json.dumps(state))

                answer = self.advance(CONVOY, env={**self.env, R8_CLOSE_RELEASE_ENV: json.dumps(auth)})

                self.assertNotEqual("closed", self.bead(T1)["status"], name)
                self.assertNotIn("withdrawn", self.shown_state(T1)["gates"], name)
                self.assertEqual([], self.of(answer, "closed_without_merge"), name)

    def overridden_then_returned(self, override=True):
        """T1 stopped still refused, its one Blocking Finding overridden by
        the operator, then returned by red tests on the merged result
        (af-n4bn62: F and G1 of af-strhoy, 21/10/2026). Without `override`
        the finding is left as it is and the merge red is written as
        bin/spec-integration writes it."""
        base = self.integrated(regression="false")
        self.resumable()
        self.evaluated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        self.run_ok(STATE, "open-code-review", CONVOY, T1, "--kind", "review", "--commit", tip, "--base", base)
        review = self.tmp / "review-t1.json"
        review.write_text(json.dumps({"commit": tip, "answers": {}, "recorded_by": "delivery-reviewer-fx",
                                      **self.BLOCKS}))
        self.run_ok(STATE, "record-code-review", CONVOY, T1, "--file", review)
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "still_refused", "--detail", "revue de code (F1.1)")
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        if override:
            self.run_ok(STATE, "override-finding", CONVOY, T1, "--finding", "F1.1", "--approver", "benjamin-hurand",
                        "--words", "Je passe outre F1.1.")
            self.advance(CONVOY)  # evaluated at the tip, then the merge returns it: red tests
        else:
            self.run_ok(STATE, "set-merge", CONVOY, T1, "--outcome", "red", "--ticket-commit", tip,
                        "--integration", base, "--commit", tip)
        self.assertEqual("red", self.shown_state(T1)["merge"]["outcome"])
        self.write_log.write_text("")

    def test_a_ticket_stopped_still_refused_and_overridden_that_the_merge_returned_is_resumed_once(self):
        self.overridden_then_returned()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "returned")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")], answer)
        self.assertEqual(1, len(self.resume_launches()))
        shown = self.shown_state(T1)
        # The stop is lifted, not erased: the resume keeps it, and its request leaves the operator's list.
        self.assertIsNone(shown["stop"])
        self.assertEqual("still_refused", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual(["F1.1"], [entry["finding"] for entry in shown["overrides"]])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_stopped_still_refused_without_its_override_is_not_resumed_by_a_returned_merge(self):
        self.overridden_then_returned(override=False)
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([], self.resume_launches())
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_ticket_parked_at_a_resume_its_red_merge_asked_for_names_that_cause_and_the_failing_tests(self):
        # af-w6xtw0: the operator read « 3 reprises » and not why the last one was.
        failing = " ; ".join(f"echo FAILED: tests/{name}-test.py" for name in ("a", "b", "c", "d"))
        self.integrated(regression=f"sh -c '{failing} ; exit 1'")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)  # the merge returns it: red tests on the merged result
        self.earlier_resumes("returned", 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        detail = self.park_of(T1)["detail"]
        self.assertIn("reprises épuisées pour la cause returned", detail)
        self.assertIn("dernière reprise enregistrée : returned", detail)
        self.assertIn("tests rouges sur le résultat fusionné", detail)
        self.assertIn("tests/a-test.py, tests/b-test.py, tests/c-test.py, …", detail)
        self.assertNotIn("tests/d-test.py", detail)

    def test_a_red_merge_whose_output_names_no_test_still_parks_with_the_merged_commit(self):
        self.integrated(regression="sh -c 'echo boom ; exit 1'")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)
        self.earlier_resumes("returned", 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        detail = self.park_of(T1)["detail"]
        self.assertRegex(detail, r"tests rouges sur le résultat fusionné [0-9a-f]{7,12}\)$")

    def test_a_ticket_resumed_for_three_different_causes_is_not_parked_and_keeps_being_resumed(self):
        # ADR-0030 L2 (the af-ltchro case): an interruption, a correction
        # round and a commit after a verdict are three causes, none at its bound.
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)  # an interruption: one resume
        # A correction round, as bin/convoy-state open-correction counts it,
        # then a commit after a verdict, as invalidate-verdicts counts it.
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "parked"))
        self.assertIsNone(self.park_of(T1))
        self.assertEqual(2, self.shown_state(T1)["resumes_left"])
        # Interrupted once more, it is restarted.
        self.interrupted(T1, "auteur-2")
        again = self.advance(CONVOY)
        self.assertEqual([(T1, "interrupted")], [(r["id"], r["cause"]) for r in self.of(again, "resumed")])
        self.assertEqual(4, self.resumes())

    def test_a_ticket_at_the_last_resume_of_one_cause_is_parked_with_its_descendants_and_not_restarted(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)  # an interruption: one resume
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        for _ in range(3):  # three commits after a verdict: that cause is at its bound
            self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [parked] = self.of(answer, "parked")
        self.assertEqual((T1, "resumes_exhausted", [T1, T3]), (parked["id"], parked["cause"], parked["parked"]))
        self.assertIn("reprises épuisées pour la cause commit_after_verdict", self.park_of(T1)["detail"])
        for ticket_id in (T1, T3):
            park = self.park_of(ticket_id)
            self.assertEqual(("resumes_exhausted", T1), (park["cause"], park["origin"]), ticket_id)
        self.assertIsNone(self.park_of(T2))
        self.assertEqual([], self.slung())
        # Interrupted once more, it is not restarted.
        self.interrupted(T1, "auteur-2")
        again = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(again, "resumed"), self.slung()))
        self.assertEqual(5, self.resumes())

    def test_a_ticket_interrupted_three_times_is_restarted_twice_and_parked_at_the_third(self):
        self.started_convoy()
        seen = []
        for name in ("auteur-1", "auteur-2", "auteur-3"):
            self.interrupted(T1, name)
            answer = self.advance(CONVOY)
            seen.append((len(self.of(answer, "resumed")), len(self.of(answer, "parked"))))

        self.assertEqual([(1, 0), (1, 0), (0, 1)], seen)
        self.assertEqual(2, len(self.resume_launches()))
        self.assertEqual(3, self.resumes())
        self.assertEqual("resumes_exhausted", self.park_of(T3)["cause"])

    def test_the_tickets_that_wait_for_no_parked_ticket_keep_starting(self):
        self.resumable(ceiling=1)
        self.advance(CONVOY)  # T1 alone: the ceiling
        self.run_ok(STATE, "set-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--value", 3)
        self.close_through_gate("fx-o1", OTHER)
        self.resumable()

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "parked")])
        self.assertEqual([T2], self.started(answer))
        self.assert_started_through_door(T2)
        self.assertEqual({T3}, {entry["id"] for entry in self.of(answer, "waiting")})

    def test_a_convoy_left_with_parked_tickets_only_raises_exactly_one_request_naming_each_and_its_cause(self):
        self.exhausted_and_alone()

        answer = self.advance(CONVOY)

        needs = self.needs()
        self.assertEqual(1, len(needs), needs)
        self.assertTrue(needs[0].startswith(f"{self.grouped_bead()} — "), needs)
        for named in (CONVOY, T1, T3, "reprises épuisées"):
            self.assertIn(named, needs[0])
        self.assertEqual([["mail", "human", f"NEEDS BENJAMIN: {self.grouped_bead()}"]], self.log("mail"))
        self.assertTrue(self.of(answer, "grouped_request")["raised"])
        # One request for the convoy, none per ticket.
        for ticket_id in (T1, T3):
            self.assertNotIn("gc.needs_benjamin", self.bead(ticket_id)["metadata"], ticket_id)
        description = self.bead(self.grouped_bead())["description"]
        for named in (T1, T3, "reprises épuisées"):
            self.assertIn(named, description)

    def test_the_grouped_request_names_a_ticket_its_own_exit_parked_with_that_cause(self):
        self.exhausted_and_alone()
        self.edit(T2, status="open", metadata={k: v for k, v in self.bead(T2)["metadata"].items()
                                                if k != "gc.flow.gate.ticket_end"})
        self.run_ok(STATE, "park", CONVOY, T2, "--cause", "operator_request", "--detail", "Accès à l'horloge")

        self.advance(CONVOY)

        description = self.bead(self.grouped_bead())["description"]
        self.assertIn(T2, description)
        self.assertIn("demande opérateur", description)

    def test_no_grouped_request_while_a_ticket_that_is_not_parked_is_left(self):
        self.started_convoy()
        for name in ("auteur-1", "auteur-2", "auteur-3"):
            self.interrupted(T1, name)
            self.advance(CONVOY)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.needs())
        self.assertIsNone(self.grouped_bead())
        self.assertEqual({}, self.of(answer, "grouped_request") or {})

    def test_the_same_parked_convoy_seen_on_several_passes_raises_one_request(self):
        self.exhausted_and_alone()

        for _ in range(3):
            self.advance(CONVOY)

        self.assertEqual(1, len(self.needs()))
        self.assertEqual(1, len(self.log("mail")))
        self.assertEqual(1, len([entry for entry in self.log("create") if self.GROUPED in entry[2]]))

    def test_a_grouped_request_that_could_not_be_raised_fails_the_pass_and_is_raised_by_the_next(self):
        self.exhausted_and_alone()

        proc = self.run_cmd(TOOL, CONVOY, env={**self.env, "CONVOY_STATE_FAKE_MAIL_FAIL": "1"})

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.advance(CONVOY)
        self.assertEqual(1, len(self.needs()))
        self.assertEqual(1, len([entry for entry in self.log("create") if self.GROUPED in entry[2]]))

    def test_the_answer_that_lifts_makes_the_ticket_and_its_descendants_startable_again(self):
        self.exhausted_and_alone()
        self.advance(CONVOY)
        request = self.grouped_bead()
        self.run_ok(ESCALATION, "repondre", request, self.LIFT, "--actor", "operateur-test")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, [T1, T3]), (lifted["id"], lifted["lifted"]))
        self.assertIsNone(self.park_of(T1))
        self.assertIsNone(self.park_of(T3))
        # The ticket is sent again to an author session by the pass itself.
        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        self.assertEqual(3, self.shown_state(T1)["resumes_left"])
        # The request is over: off the list, its bead closed, its record gone.
        self.assertEqual([], self.needs())
        self.assertEqual("closed", self.bead(request)["status"])
        self.assertIsNone(self.grouped_bead())
        # And the ticket that waited for it starts once it is closed.
        self.close_through_gate(T1)
        self.assertEqual([T3], self.started(self.advance(CONVOY)))

    def test_a_grouped_answer_recorded_during_another_resume_is_applied_before_withdrawal(self):
        self.exhausted_and_alone()
        metadata = {key: value for key, value in self.bead(T2)["metadata"].items()
                    if key != "gc.flow.gate.ticket_end"}
        self.edit(T2, status="in_progress", metadata=metadata)
        request = {"quoi": "Accès à l'horloge", "pourquoi": "Le ticket attend cette donnée",
                   "que_faire": [{"option": "Donner l'accès", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T2, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T2, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T2, "--exit", "operator_request")
        self.advance(CONVOY)
        grouped = self.grouped_bead()
        self.run_ok(ESCALATION, "repondre", T2, "a", "--actor", "operateur-test")
        self.write_log.write_text("")

        answer = self.advance(CONVOY, env={**self.env, "CONVOY_STATE_FAKE_ANSWER_ON_SLING": f"{grouped}=a"})

        self.assertEqual({T1, T2}, {entry["id"] for entry in self.of(answer, "lifted")})
        resumed = [entry["id"] for entry in self.of(answer, "resumed")]
        self.assertEqual(1, resumed.count(T1))
        self.assertEqual(1, resumed.count(T2))
        self.assertIsNone(self.park_of(T1))
        self.assertIsNone(self.park_of(T3))
        self.assertEqual("closed", self.bead(grouped)["status"])
        self.assertIsNone(self.grouped_bead())

    def test_a_grouped_answer_recorded_while_changed_parkings_are_re_raised_is_applied_first(self):
        self.exhausted_and_alone()
        self.advance(CONVOY)
        grouped = self.grouped_bead()
        metadata = self.bead(T1)["metadata"]
        park = json.loads(metadata["gc.flow.park"])
        park["at"] = "9998-01-01T00:00:00Z"
        metadata["gc.flow.park"] = json.dumps(park)
        self.edit(T1, metadata=metadata)

        answer = self.advance(
            CONVOY, env={**self.env, "CONVOY_STATE_FAKE_ANSWER_ON_GROUPED_NOTE": f"{grouped}=a"})

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "lifted")])
        self.assertIsNone(self.park_of(T1))
        self.assertIsNone(self.park_of(T3))
        self.assertEqual("closed", self.bead(grouped)["status"])
        self.assertIsNone(self.grouped_bead())

    def test_the_answer_that_leaves_the_tickets_parked_lifts_nothing_and_is_not_asked_again(self):
        self.exhausted_and_alone()
        self.advance(CONVOY)
        self.run_ok(ESCALATION, "repondre", self.grouped_bead(), self.LEAVE, "--actor", "operateur-test")
        self.write_log.write_text("")

        for _ in range(2):
            answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "lifted"))
        self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"])
        self.assertEqual([], self.needs())
        self.assertEqual(([], []), (self.log("mail"), self.slung()))

    def test_an_answer_to_the_request_of_a_ticket_its_own_exit_parked_lifts_it_and_resumes_it(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {"quoi": "Accès à l'horloge de référence", "pourquoi": "L'auteur n'a pas cet accès",
                   "que_faire": [{"option": "Donner l'accès", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        unanswered = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(unanswered, "lifted"), self.of(unanswered, "resumed")))
        self.assertEqual("operator_request", self.park_of(T3)["cause"])
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, [T1, T3])], [(entry["id"], entry["lifted"]) for entry in self.of(answer, "lifted")])
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertIsNone(self.park_of(T3))
        self.assertEqual(1, self.resumes())

    def request_answered(self, name):
        """The session `name` took T1 and left it by an operator request,
        which parks it; the operator answered it."""
        self.taken(T1, name)
        request = {"quoi": f"Demande de {name}", "pourquoi": "L'auteur n'a pas cet accès",
                   "que_faire": [{"option": "Donner l'accès", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

    def test_each_answered_request_resumes_its_ticket_beyond_any_bound_and_asks_benjamin_nothing(self):
        # af-npz9v1.41: R2 (af-cifk1e), its third answer counted on 28/10/2026
        # at 18:28 Paris, was parked for exhausted resumes, never sent.
        self.started_convoy()
        for name in ("auteur-1", "auteur-2", "auteur-3", "auteur-4"):
            self.request_answered(name)
            answer = self.advance(CONVOY)
            self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")], name)
            self.assertEqual([], self.of(answer, "parked"), name)

        self.assertIsNone(self.park_of(T1))
        self.assertEqual(4, len(self.resume_launches()))
        self.assertEqual(4, self.resumes())
        self.assertEqual([], self.needs())

    def test_a_ticket_parked_at_its_third_answer_is_lifted_and_its_counted_resume_sent_once(self):
        # af-npz9v1.41: the state R2 (af-cifk1e) was left in on 28/10/2026 at
        # 18:29 Paris, as the pass then wrote it: its third answered resume
        # counted, no session sent, the ticket parked for exhausted resumes.
        self.started_convoy()
        for name in ("auteur-1", "auteur-2"):
            self.request_answered(name)
            self.advance(CONVOY)
        self.request_answered("auteur-3")
        self.run_ok(STATE, "lift-park", CONVOY, T1, "--request", T1, "--option", "a")
        self.run_ok(STATE, "open-resume", CONVOY, T1, "--cause", "answered", "--ref", "exit:troisième")
        metadata = self.bead(T1)["metadata"]
        park = {"cause": "resumes_exhausted", "origin": T1, "at": "2026-10-28T17:29:01Z",
                "detail": "reprises épuisées pour la cause answered (3 reprises en tout)"}
        self.edit(T1, metadata={**metadata, "gc.flow.park": json.dumps(park)})
        self.edit(T3, metadata={**self.bead(T3)["metadata"], "gc.flow.park": json.dumps(park)})
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, None, T1, [T1, T3]), (lifted["id"], lifted["option"], lifted["request"], lifted["lifted"]))
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual((None, None), (self.park_of(T1), self.park_of(T3)))
        self.assertEqual(1, len(self.resume_launches()))
        self.assertEqual(3, self.resumes())
        self.assertEqual([], self.needs())
        # The same state again: nothing more is lifted nor sent.
        again = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(again, "lifted"), self.of(again, "resumed")))
        self.assertEqual(1, len(self.resume_launches()))

    def test_a_ticket_parked_at_the_bound_of_a_bounded_cause_is_not_lifted_without_an_answer(self):
        self.exhausted_and_alone()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "lifted"))
        self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"])
        proc = self.run_cmd(STATE, "lift-park", CONVOY, T1, "--request", T1)
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("demande groupée", proc.stdout)
        self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"])

    def test_the_accepting_answer_to_a_planning_exception_naming_no_anchor_lifts_it_and_resumes_it(self):
        # ADR-0030 L5: every Planning Exception has an accept path.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {"quoi": f"Planning Exception (semantic) sur {T1} : la Spec dit X, le produit fait Y",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."},
                                 {"option": "Accepter l'écart décrit", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "la Spec dit X, le produit fait Y", "--accept-option", "c")
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "planning_exception")
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking
        self.run_ok(ESCALATION, "repondre", T1, "c", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, [T1, T3])], [(entry["id"], entry["lifted"]) for entry in self.of(answer, "lifted")])
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])

    def evaluation_parked(self):
        """T1 finished; its last Ticket Evaluation found the demonstration
        line unobservable by the criterion (the round as bin/convoy-state
        records it), and the request it raised parks T1, with no entry under
        `planning_exceptions` (af-ten1sp)."""
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        line = {"text": "la ligne de démonstration", "state": "unobservable", "evidence": "evaluation.demo",
                "reason": "aucun jeu lancé n'a de source CI absente", "cause": "criterion"}
        round_ = {"kind": "evaluation", "commit": tip, "criteria": [], "demonstration_line": line,
                  "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
                  "environment": [{"dataset": None, "address": "http://127.0.0.1:40000"}],
                  "recorded_by": "delivery-evaluator-fx", "outcome": "planning_exception", "verdict": "unfavorable",
                  "at": "2026-10-21T04:13:02Z"}
        metadata = self.bead(T1)["metadata"]
        self.edit(T1, metadata={**metadata, "gc.flow.evaluation": json.dumps({"rounds": [round_]})})
        request = {"quoi": f"Planning Exception sur {T1} : inobservable sur le produit lancé (ligne de démonstration)",
                   "pourquoi": "Un critère gelé que l'Evaluator ne peut pas observer ne se dispense ni ne se reformule.",
                   "que_faire": [{"option": "Juger ce qui est inobservable prouvé par son test de critère vert",
                                  "consequence": "Le parcage est levé."},
                                 {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."},
                                 {"option": "Réévaluer sur le produit relancé", "consequence": "Rien n'est prouvé."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.assertEqual([], self.of(self.advance(CONVOY), "lifted"))
        self.assertEqual([], self.shown_state(T1)["planning_exceptions"])
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking

    def test_the_answer_a_to_an_evaluation_planning_exception_lifts_it_and_judges_the_item_proven_by_test(self):
        # Benjamin, 21/10/2026 about 16:55 Paris (af-ten1sp): « Preuve par le test ».
        self.evaluation_parked()
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "benjamin")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "a")], [(entry["id"], entry["option"]) for entry in self.of(answer, "lifted")])
        self.assertIsNone(self.park_of(T1))
        self.assertEqual([{"what": "ligne de démonstration", "text": "la ligne de démonstration"}],
                         self.shown_state(T1)["park_lifts"][-1]["proven_by_test"])

    def test_the_answer_a_proof_reaches_ticket_end_and_the_next_pass_is_idempotent(self):
        tip = self.finished_interface_ticket()
        decision_commit = self.git("rev-parse", "main")
        self.assertNotEqual(decision_commit, tip)
        line = {"text": self.shown_state(T1)["demonstration_line"], "state": "unobservable",
                "evidence": "evaluation.demo", "reason": "la demi-phrase ne se voit pas sur le produit lancé",
                "cause": "criterion"}
        round_ = {"kind": "evaluation", "commit": decision_commit, "criteria": [], "demonstration_line": line,
                  "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
                  "environment": [{"dataset": "content", "address": "http://127.0.0.1:40000"}],
                  "recorded_by": "delivery-evaluator-fx", "outcome": "planning_exception", "verdict": "unfavorable",
                  "at": "2026-10-21T04:13:02Z"}
        metadata = self.bead(T1)["metadata"]
        self.edit(T1, metadata={**metadata,
                                "gc.flow.evaluation": json.dumps({"rounds": [round_]}),
                                "gc.flow.verdict.evaluation": json.dumps({
                                    "state": "unfavorable", "commit": decision_commit, "at": round_["at"]})})
        request = {"quoi": f"Planning Exception sur {T1} : ligne de démonstration inobservable",
                   "pourquoi": "Le produit lancé ne peut pas montrer cette demi-phrase.",
                   "que_faire": [{"option": "Juger ce qui est inobservable prouvé par son test de critère vert",
                                   "consequence": "Le parcage est levé."},
                                  {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."},
                                  {"option": "Réévaluer sur le produit relancé", "consequence": "Rien n'est prouvé."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.evaluated({"states": {"demo": {"state": "unobservable", "cause": "criterion",
                                             "reason": "toujours invisible sur le produit lancé"}}})
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "benjamin")

        answer = self.advance(CONVOY)

        shown = self.shown_state(T1)
        last = shown["evaluation"]["rounds"][-1]
        self.assertEqual(("favorable", ["ligne de démonstration"]),
                         (last["outcome"], last["proven_by_test"]))
        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "lifted")])
        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "integration")["merged"]])
        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "ticket_end")["closed"]])
        self.assertEqual("closed", shown["status"])
        self.assertIn("prouvée par son test", shown["gates"]["ticket_end"]["conditions"][2]["detail"])
        gate = shown["gates"]["ticket_end"]

        again = self.advance(CONVOY)

        self.assertIsNone(self.ticket_end_of(again))
        after = self.shown_state(T1)
        self.assertEqual(("closed", gate), (after["status"], after["gates"]["ticket_end"]))

    def test_the_answer_c_to_an_evaluation_planning_exception_lifts_it_and_judges_nothing_proven(self):
        # af-npz9v1.38: evaluated again on the products launched again.
        self.evaluation_parked()
        self.run_ok(ESCALATION, "repondre", T1, "c", "--actor", "benjamin")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "c")], [(entry["id"], entry["option"]) for entry in self.of(answer, "lifted")])
        self.assertIsNone(self.park_of(T1))
        self.assertNotIn("proven_by_test", self.shown_state(T1)["park_lifts"][-1])

    def test_the_answer_b_to_an_evaluation_planning_exception_leaves_it_parked(self):
        self.evaluation_parked()
        self.run_ok(ESCALATION, "repondre", T1, "b", "--actor", "benjamin")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "lifted"))
        self.assertEqual("planning_exception", self.park_of(T1)["cause"])

    def already_green_excepted(self):
        """T1 stopped with all its criteria already green while its author
        session is alive; the author raises its Planning Exception, the
        request parks T1, then the session is over (ADR-0030 L5)."""
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")
        before_exception = self.advance(CONVOY)
        self.assertEqual([], self.of(before_exception, "tdd_stops"))
        request = {"quoi": f"Planning Exception (semantic) sur {T1} : critères tous déjà verts",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Accepter l'écart décrit", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "critères tous déjà verts", "--accept-option", "b")
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "planning_exception")
        self.edit(sessions=[])
        parked = self.advance(CONVOY)
        self.assertEqual([], self.of(parked, "tdd_stops"))
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking

    def escalation_options(self, ticket_id):
        metadata = self.bead(ticket_id)["metadata"]
        return [entry["option"] for entry in json.loads(metadata["gc.escalation_que_faire"])]

    def test_a_ticket_whose_criteria_are_all_already_green_reaches_the_operator_once_its_exception_is_accepted(self):
        # ADR-0030 L5: « accept » lifts the parking, not the stop; the stop
        # then reaches the operator, once, instead of stalling the convoy.
        self.already_green_excepted()
        self.run_ok(ESCALATION, "repondre", T1, "b", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "lifted")])
        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([{"ticket": T1, "reason": "criterion_already_green"}], self.of(answer, "tdd_stops")["escalated"])
        needs = [line for line in self.needs() if T1 in line]
        self.assertEqual(1, len(needs), needs)
        self.assertIn("critères tous déjà verts", needs[0])
        # One decision, one request: close it as satisfied, or leave it
        # stopped; no second Planning Exception is offered (af-npz9v1.9).
        options = self.escalation_options(T1)
        self.assertTrue(any("satisfait" in option for option in options), options)
        self.assertFalse(any("Planning Exception" in option for option in options), options)

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    def test_an_already_green_ticket_whose_exception_is_answered_otherwise_stays_parked_and_its_stop_is_not_raised(self):
        self.already_green_excepted()
        self.run_ok(ESCALATION, "repondre", T1, "a", "--actor", "operateur-test")

        for _ in range(2):
            answer = self.advance(CONVOY)
            self.assertEqual(([], []), (self.of(answer, "lifted"), self.of(answer, "tdd_stops")))
        self.assertEqual("planning_exception", self.park_of(T1)["cause"])
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

    def test_an_already_green_ticket_whose_author_ended_without_an_exception_reaches_the_operator_once(self):
        # af-npz9v1.9: no silent block when the author never raises one.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")

        answer = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "reason": "criterion_already_green"}], self.of(answer, "tdd_stops")["escalated"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))
        again = self.advance(CONVOY)
        self.assertEqual([], self.of(again, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    def test_an_exception_raised_before_the_already_green_stop_does_not_raise_it(self):
        # af-npz9v1.9: only an exception raised after the stop settles it.
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "une question plus ancienne", "--accept-option", "c")
        metadata = self.bead(T1)["metadata"]
        record = json.loads(metadata["gc.flow.planning_exceptions"])
        record["entries"][-1]["at"] = "2000-01-01T00:00:00Z"
        metadata["gc.flow.planning_exceptions"] = json.dumps(record)
        self.edit(T1, metadata=metadata)
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "tdd_stops"))
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

    # --- the stops of the convoy: red integration branch, open Planning Exceptions (T21, af-cbp84n) ---

    def test_a_red_integration_branch_starts_no_ticket_but_its_repair(self):
        self.red_recorded(self.integrated())
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        # T1 and T2 are ready and places are free: neither starts.
        self.assertEqual([self.REPAIR], self.started(answer))
        self.assertEqual([self.REPAIR], self.slung())
        self.assertEqual(before, self.tickets_snapshot())
        stop = self.stop_of(answer)
        self.assertEqual(("integration_red", self.RED_CONTROL, self.REPAIR), (stop["reason"], stop["control"], stop["repair"]))
        for ticket_id, reason in self.waiting_reasons(answer).items():
            self.assertIn(self.RED_BRANCH, reason, ticket_id)
            self.assertIn(self.RED_CONTROL, reason, ticket_id)
        self.assertEqual({T1, T2, T3}, set(self.waiting_reasons(answer)))
        self.assertTrue(answer["ok"])

    def test_a_red_integration_branch_merges_no_finished_ticket(self):
        base = self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        self.red_recorded(base)

        answer = self.advance(CONVOY)

        integration = self.integration_of(answer)
        self.assertEqual(self.RED_CONTROL, integration["red"]["control"])
        self.assertEqual(self.RED_BRANCH, integration["stopped"])
        self.assertNotIn("merged", integration)
        self.assertIsNone(self.shown(T1)["merge"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        # The convoy is stopped, the pass is not a failure.
        self.assertTrue(answer["ok"])

    def test_several_passes_on_the_same_red_start_and_merge_nothing_more(self):
        self.red_recorded(self.integrated())
        self.advance(CONVOY)
        self.write_log.write_text("")
        before = self.tracker.read_bytes()

        for _ in range(2):
            answer = self.advance(CONVOY)
            self.assertEqual([], self.started(answer))

        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([], self.slung())
        self.assertEqual([], self.log("create"))

    def test_the_starts_and_the_merges_resume_by_themselves_once_the_red_is_withdrawn(self):
        base = self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        self.red_recorded(base)
        self.advance(CONVOY)
        # What the merge command writes once the control is green again.
        self.run_ok(STATE, "clear-integration-red", CONVOY)
        self.close_through_gate(T2)

        answer = self.advance(CONVOY)

        self.assertIsNone(self.stop_of(answer))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])
        self.assertEqual(tip, self.shown(T1)["merge"]["ticket_commit"])
        # T3 waited for T1 and T2: closed by the pass and by the gate, it starts at the next one.
        self.assertEqual([T3], self.started(self.advance(CONVOY)))

    def test_a_red_without_its_repair_that_the_patch_door_cannot_publish_fails_the_pass_and_starts_nothing(self):
        base = self.integrated()
        self.run_ok(STATE, "record-integration-red", CONVOY, "--commit", base, "--integration", base,
                    "--protected", base, "--control", self.RED_CONTROL)
        self.write_log.write_text("")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        # This convoy was not published by the publication door: nothing to revise.
        self.assertIn("porte de patch", self.of(answer, "repair")["error"])
        self.assertEqual(([], []), (self.started(answer), self.slung()))
        self.assertEqual(before, self.tickets_snapshot())

    def test_two_open_planning_exceptions_start_no_new_ticket_and_the_tickets_at_work_go_on(self):
        self.three_at_work()
        self.planning_exception(self.A)
        self.planning_exception(self.B)
        before = self.bead(self.D)

        answer = self.advance(CONVOY)

        # D is ready and places are free: it does not start.
        self.assertEqual([], self.started(answer))
        self.assertEqual(before, self.bead(self.D))
        stop = self.stop_of(answer)
        self.assertEqual(("planning_exceptions", [self.A, self.B], 2), (stop["reason"], stop["open"], stop["bound"]))
        self.assertIn("2 Planning Exceptions ouvertes", self.waiting_reasons(answer)[self.D])
        # C was at work: its resume is sent, it finishes.
        self.assertEqual([(self.C, "interrupted")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertTrue(answer["ok"])

    def test_one_open_planning_exception_lets_the_tickets_that_are_not_parked_start(self):
        self.three_at_work()
        self.planning_exception(self.A)

        answer = self.advance(CONVOY)

        self.assertEqual([self.D], self.started(answer))
        self.assertIsNone(self.stop_of(answer))
        # B's session is over without an exit, C left by « interrompu »: both are resumed.
        self.assertEqual([self.B, self.C], [r["id"] for r in self.of(answer, "resumed")])
        self.assertEqual("planning_exception", self.park_of(self.A)["cause"])

    def test_the_starts_resume_by_themselves_once_one_of_the_two_planning_exceptions_is_answered(self):
        self.three_at_work()
        self.planning_exception(self.A)
        self.planning_exception(self.B)
        self.assertEqual([], self.started(self.advance(CONVOY)))
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the exception
        self.run_ok(ESCALATION, "repondre", self.B, "a", "--actor", "operateur-test")

        answer = self.advance(CONVOY)

        self.assertEqual([self.D], self.started(answer))
        self.assertIsNone(self.stop_of(answer))

    def test_a_planning_exception_raised_by_an_evaluation_counts_as_an_open_one(self):
        self.three_at_work()
        self.planning_exception(self.A)
        # What bin/ticket-evaluation leaves of a criterion the Evaluator cannot observe: the parking alone.
        self.run_ok(STATE, "park", CONVOY, self.B, "--cause", "planning_exception",
                    "--detail", f"Planning Exception sur {self.B} : inobservable sur le produit lancé (critère 1)")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.started(answer))
        self.assertEqual([self.A, self.B], self.stop_of(answer)["open"])

    def test_the_bound_of_the_open_planning_exceptions_is_the_one_of_the_settings(self):
        for bound, exceptions, started in ((1, (self.A,), []), (3, (self.A, self.B), [self.D])):
            with self.subTest(bound=bound):
                self.three_at_work(bounds={"resumes": 3, "open_planning_exceptions": bound})
                for ticket_id in exceptions:
                    self.planning_exception(ticket_id)

                answer = self.advance(CONVOY)

                self.assertEqual(started, self.started(answer))
                self.assertEqual(bound if not started else None, (self.stop_of(answer) or {}).get("bound"))

    def test_a_malformed_bound_of_the_open_planning_exceptions_refuses_the_pass_and_starts_nothing(self):
        for value in (0, "deux", None):
            with self.subTest(value=value):
                self.four_tickets(ceiling=3, bounds={"resumes": 3, "open_planning_exceptions": value})
                before = self.tracker.read_bytes()

                answer = self.advance(CONVOY, expect=EXIT_REFUSED)

                self.assertIn("bounds.open_planning_exceptions", answer["error"])
                self.assertEqual(before, self.tracker.read_bytes())
                self.assertEqual([], self.slung())


if __name__ == "__main__":
    unittest.main()
