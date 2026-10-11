#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/convoy-stops-fixture-city-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); each case starts from a convoy walked to its Delivered Outcome and replays real passes
"""Benjamin's answer to a Delivered Outcome (T29, af-mcd7pw; Spec af-wf4w5r
§11) and what the next pass does with it (T30, af-vlzc6v; Spec §9 and §11),
on the convoy the reference driver of the Fixture City Oracle walks to the
end of its Spec: the answer recorded by the real bin/owner-answer, the
repair of a returned finding, the one merge into the protected branch and
the closing of the convoy, or the closing alone.

These cases were in tests/convoy-stops-fixture-city-test.py (af-vqew1x: that
file, alone on one core, set the duration of a CI run). The harness
FixtureCityWalk is loaded from there; the cases of the acceptance are in
tests/acceptance-fixture-city-test.py."""

import html
import importlib.machinery
import importlib.util
import json
import subprocess
import time
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
# named at the top of a file, and the cases of that file run there.
stops = load("convoy-stops-fixture-city-test.py")
ADVANCE = stops.ADVANCE
ESCALATION = stops.ESCALATION
SESSION = stops.SESSION
OWNER = stops.OWNER
EXIT_REFUSED = stops.EXIT_REFUSED
THIRTY_DAYS = stops.THIRTY_DAYS
CLOCKS = stops.CLOCKS
answers = stops.answers


class OwnerAnswerOnTheFixtureCity(stops.FixtureCityWalk):
    """T29 (af-mcd7pw; Spec §11) on the convoy the reference driver walks to
    the end of its Spec: Benjamin's answer is recorded by the real
    bin/owner-answer, and the repair of the finding he returns is published,
    delivered and judged again by the real passes of the order."""

    APPROVER = "benjamin"
    FINDING = "La liste des éléments ne se relit pas en JSON à l'adresse /items."
    LATER = "Un export CSV de la liste serait utile."
    REPAIR = {
        "title": "Servir la liste des éléments en JSON",
        "what_it_delivers": "Le produit sert la liste des éléments du jeu de données en JSON à l'adresse /items.",
        "demonstration_line": "Sur le produit lancé avec le jeu de données « content », GET /items rend les trois éléments.",
        "acceptance_criteria": [{
            "entry_point": "GET /items sur le produit lancé avec le jeu de données « content »",
            "observable": "le champ items contient « alpha », « beta », « gamma »",
            "false_if": "un élément manque, ou /items ne répond pas"}]}

    def owner(self, command, *args):
        return self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", self.APPROVER, *args)

    def owner_ok(self, command, *args):
        proc = self.owner(command, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def pack(self):
        """The Evidence Pack of the convoy as bin/evidence-pack holds it, and its page."""
        pack = json.loads(self.tool_ok(ROOT / "bin" / "evidence-pack", "check", self.convoy, "--repo", self.repo).stdout)
        return pack, Path(pack["page"]).read_text(encoding="utf-8")

    def last_pass(self):
        """What the last pass of the order answered about the convoy."""
        answer = json.loads((self.workspace / "order-pass.json").read_text(encoding="utf-8"))
        return next(result for result in answer["convoys"] if result["id"] == self.convoy)

    def test_accepted_waits_for_the_verdicts_a_returned_finding_is_repaired_and_judged_again_then_accepted(self):
        first = self.walk_to_delivered(inject="proposition", real=True)
        self.assert_one_acceptance_request(first)
        first_pack, first_page = self.pack()
        self.assertNotIn("Depuis ton dernier jugement", first_page)
        self.assertNotIn('<section id="rubrique-0">', first_page)
        shown = self.shown()
        integration = shown["convoy"]["integration"]["branch"]
        tracked = [ticket["id"] for ticket in shown["tickets"]]
        # The dossier carries one « proposition »: what the author found « hors ticket ».
        [proposition] = [finding for ticket in shown["tickets"] for finding in ticket.get("findings") or []
                         if finding["classification"] == "proposal"]
        main = self.tip("main")

        # « accepté » while the proposition has no verdict: refused, nothing written.
        before = self.tracker.read_bytes()
        refused = self.owner("record", "--response", "accepté", "--words", "C'est bon pour moi.",
                             "--commit", first["commit"], "--pack-digest", first["pack"])
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout + refused.stderr)
        error = json.loads(refused.stdout)["error"]
        self.assertTrue(error.startswith("refus : "), error)
        self.assertIn("verdict", error)
        self.assertIn(proposition["id"], error)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(shown, self.shown())

        # His verdict on it, then one finding that cites the second user story of the Spec.
        self.owner_ok("verdict", "--proposition", proposition["id"], "--verdict", "sans suite", "--words", "Pas utile.")
        findings = self.workspace / "owner-findings.json"
        findings.write_text(json.dumps({"findings": [
            {"text": self.FINDING, "cites": {"kind": "user_story", "ref": "user story 2"}, "repair": self.REPAIR},
            {"text": self.LATER, "later": True}]}, ensure_ascii=False), encoding="utf-8")
        returned = self.owner_ok("record", "--response", "constats rendus", "--words", "Il manque le JSON.",
                                 "--commit", first["commit"], "--pack-digest", first["pack"], "--findings", findings)
        self.assertEqual(["repair", "later"], [finding["route"] for finding in returned["findings"]])
        # The proposition door of the fixture creates nothing: his answer is recorded all the same.
        self.assertEqual([2], [pending["finding"] for pending in returned["proposals_pending"]])

        # Nothing closed, nothing merged; the Outcome is no longer Delivered and its rounds start again.
        shown = self.shown()
        self.assertIsNone(shown["convoy"]["delivered"])
        self.assertEqual(0, shown["convoy"]["counters"]["end_rounds"])
        self.assertEqual("findings", shown["convoy"]["judgement"]["answers"][-1]["response"])
        self.assertNotEqual("closed", json.loads(self.tracker.read_text())["beads"][self.convoy]["status"])
        self.assertEqual(tracked, [ticket["id"] for ticket in shown["tickets"]])
        self.assertEqual((main, first["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertEqual([], self.requests())
        self.assertFalse(shown["unruled"])

        # The next pass publishes the one repair of the finding, by code, and says so; the door
        # answers again, and the same pass creates the proposition of his « plus tard ».
        (self.workspace / "proposal-door").write_text(
            '#!/bin/sh\n[ "$1" = create ] && echo "PROPOSITION CRÉÉE: fx-later — notée" || echo 0\n')
        self.order_pass()
        [published] = self.last_pass()["acceptance"]["owner_repairs"]
        self.assertEqual([{"finding": 2, "proposal": "fx-later"}], self.last_pass()["acceptance"]["owner_proposals"])
        self.assertEqual("fx-later", self.shown()["convoy"]["judgement"]["answers"][-1]["findings"][1]["proposal"])
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual((1, repair["id"], True), (published["finding"], published["id"], published["published"]))
        self.assertEqual(("repair", "open"), (repair["kind"], repair["status"]))
        self.assertEqual(repair["id"], shown["convoy"]["judgement"]["answers"][-1]["findings"][0]["ticket"])
        self.assertIsNone(shown["convoy"]["delivered"])

        # The whole flow passes again by itself: the repair through the ticket-end gate, then the
        # whole end of the Spec at the new tip.
        second = None
        for _ in range(48):
            event = self.driver("advance")
            second = self.shown()["convoy"]["delivered"]
            if second:
                break
            self.assertFalse(event["idle"], "the walk settled before the Outcome was Delivered again")
        self.assertTrue(second, "the Outcome is not Delivered again after 48 events")
        shown = self.shown()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in shown["tickets"]])
        self.assertEqual(["closed"] * len(shown["tickets"]), [ticket["status"] for ticket in shown["tickets"]])
        self.assertNotEqual(first["commit"], second["commit"])
        self.assertEqual(second["commit"], self.tip(integration))
        self.assertEqual(main, self.tip("main"))
        # What the repair delivered is in it: the product, on top of what Benjamin judged first.
        changed = subprocess.run(("git", "-C", str(self.repo), "diff", "--name-only", first["commit"], second["commit"]),
                                 text=True, capture_output=True, check=True).stdout.split()
        self.assertTrue([path for path in changed if path.endswith("/app.py")], changed)
        # A fresh Outcome Evaluation and a fresh end review, both at the new tip.
        rounds = shown["convoy"]["outcome_evaluation"]["rounds"]
        self.assertEqual([first["commit"], second["commit"]], [entry["commit"] for entry in rounds][-2:])
        self.assertEqual(second["commit"], shown["convoy"]["end_review"]["rounds"][-1]["commit"])
        self.assertEqual(0, shown["convoy"]["counters"]["end_rounds"])
        self.assertFalse(shown["unruled"])

        # A second dossier arrives, and it opens with what was done since his last judgement.
        self.assert_one_acceptance_request(second)
        second_pack, page = self.pack()
        self.assertNotEqual((first_pack["digest"], first_pack["page"]), (second_pack["digest"], second_pack["page"]))
        start, end = page.index('<section id="rubrique-0">'), page.index('<section id="rubrique-1">')
        self.assertLess(start, end)
        rubric = page[start:end]
        self.assertIn("Depuis ton dernier jugement", rubric)
        self.assertIn(html.escape(self.FINDING), rubric)
        self.assertIn(repair["id"], rubric)

        # « accepté », now: recorded with his words, the commit and the fingerprint. Nothing closes.
        words = "Accepté, le JSON est là."
        accepted = self.owner_ok("record", "--response", "accepté", "--words", words,
                                 "--commit", second["commit"], "--pack-digest", second["pack"])
        self.assertEqual("accepted", accepted["response"])
        shown = self.shown()
        last = shown["convoy"]["judgement"]["answers"][-1]
        self.assertEqual(("accepted", words, self.APPROVER, second["commit"], second["pack"]),
                         (last["response"], last["words"], last["approver"], last["commit"], last["pack"]))
        self.assertEqual(["findings", "accepted"], [entry["response"] for entry in shown["convoy"]["judgement"]["answers"]])
        self.assertEqual(second, shown["convoy"]["delivered"])
        self.assertNotEqual("closed", json.loads(self.tracker.read_text())["beads"][self.convoy]["status"])
        self.assertEqual((main, second["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertFalse(shown["unruled"])


class PromotionOnTheFixtureCity(OwnerAnswerOnTheFixtureCity):
    """T30 (af-vlzc6v; Spec §9 and §11) on the convoy the reference driver
    walks to its Delivered Outcome: Benjamin's answer is recorded by the real
    bin/owner-answer, and the next pass of the order follows it by itself --
    the one merge into the protected branch and the closing of the convoy,
    or the closing alone."""

    WORDS = "Accepté, c'est ce que je voulais."
    REASON = "Le besoin a disparu."
    test_accepted_waits_for_the_verdicts_a_returned_finding_is_repaired_and_judged_again_then_accepted = None

    def judged(self, real=False):
        """The Delivered Outcome, every proposition of its dossier judged.
        Returns its record, the integration branch and the protected tip.
        With `real`, the walk to it runs in the test (see walk_to_delivered)."""
        delivered = self.walk_to_delivered(inject="proposition", real=real)
        shown = self.shown()
        for ticket in shown["tickets"]:
            for finding in ticket.get("findings") or []:
                if finding["classification"] == "proposal":
                    self.owner_ok("verdict", "--proposition", finding["id"], "--verdict", "sans suite", "--words", "Vu.")
        return delivered, shown["convoy"]["integration"]["branch"], self.tip("main")

    def accept(self, delivered):
        return self.owner_ok("record", "--response", "accepté", "--words", self.WORDS,
                             "--commit", delivered["commit"], "--pack-digest", delivered["pack"])

    def rev_list(self, *args):
        return subprocess.run(("git", "-C", str(self.repo), "rev-list", *args), text=True, capture_output=True,
                              check=True).stdout.split()

    def commit_to_main(self, path, text):
        """The protected branch receives a commit from elsewhere."""
        tree = self.workspace / "elsewhere"
        git = ("git", "-c", "user.name=Ailleurs", "-c", "user.email=ailleurs@example.invalid")
        subprocess.run((*git, "-C", str(self.repo), "worktree", "add", "-q", "--detach", str(tree), "main"), check=True)
        try:
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_text(text)
            subprocess.run((*git, "-C", str(tree), "add", "-A"), check=True)
            subprocess.run((*git, "-C", str(tree), "commit", "-q", "-m", "écrit ailleurs"), check=True)
            commit = subprocess.run(("git", "-C", str(tree), "rev-parse", "HEAD"), text=True, capture_output=True,
                                    check=True).stdout.strip()
            subprocess.run(("git", "-C", str(self.repo), "update-ref", "refs/heads/main", commit), check=True)
            return commit
        finally:
            subprocess.run(("git", "-C", str(self.repo), "worktree", "remove", "--force", str(tree)), check=True)

    def test_the_protected_branch_holds_nothing_of_the_convoy_before_accepted_then_one_merge_and_the_convoy_is_closed(self):
        delivered, integration, main = self.judged(real=True)
        # Delivered, and judged: the protected branch holds no commit of the convoy.
        convoy_commits = self.rev_list(f"main..{integration}")
        self.assertIn(delivered["commit"], convoy_commits)
        self.assertEqual([], self.rev_list("main", "--not", f"{integration}"))
        self.accept(delivered)
        self.assertEqual(main, self.tip("main"))
        self.assertEqual(("open", "delivered"), (self.shown()["convoy"]["status"], self.shown()["convoy"]["outcome"]))

        self.order_pass()

        promotion = self.last_pass()["promotion"]
        merged = self.tip("main")
        self.assertEqual((True, merged, delivered["commit"], True, "accepted"),
                         tuple(promotion[key] for key in ("promoted", "merged", "judged", "closed", "how")))
        self.assertEqual([merged], self.rev_list("--first-parent", f"{main}..main"))
        self.assertEqual([merged, main, delivered["commit"]], self.rev_list("--parents", "-n", "1", merged))
        self.assertEqual([], self.rev_list(f"main..{integration}"))
        shown = self.shown()
        self.assertEqual(("closed", "accepted", self.WORDS, self.APPROVER),
                         (shown["convoy"]["status"], shown["convoy"]["outcome"], shown["convoy"]["closed"]["said"],
                          shown["convoy"]["closed"]["approver"]))
        self.assertEqual((delivered["commit"], merged),
                         (shown["convoy"]["promotion"]["judged"], shown["convoy"]["promotion"]["merged"]))
        self.assertFalse(shown["unruled"])
        self.assertEqual([], self.requests())
        # The passes that follow leave it alone: closed by command, it is no longer walked.
        before = self.tracker.read_bytes()
        answer = json.loads(self.tool(ADVANCE, "--all", "--stopped-ok").stdout or "{}")
        self.assertNotIn(self.convoy, [result["id"] for result in answer.get("convoys", [])])
        self.assertEqual((before, merged), (self.tracker.read_bytes(), self.tip("main")))

    def test_an_abandoned_convoy_is_closed_with_the_reason_and_the_protected_branch_does_not_move(self):
        delivered, integration, main = self.judged()
        self.owner_ok("record", "--response", "abandonné", "--reason", self.REASON)

        self.order_pass()

        promotion = self.last_pass()["promotion"]
        self.assertEqual((False, None, True, "abandoned", self.REASON),
                         tuple(promotion[key] for key in ("promoted", "merged", "closed", "how", "said")))
        shown = self.shown()
        self.assertEqual(("closed", "abandoned", None),
                         (shown["convoy"]["status"], shown["convoy"]["outcome"], shown["convoy"]["promotion"]))
        self.assertEqual((main, delivered["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertFalse(shown["unruled"])

    def test_a_protected_branch_in_conflict_after_accepted_merges_nothing_and_the_pass_publishes_one_repair(self):
        delivered, integration, _ = self.judged()
        self.accept(delivered)
        tracked = [ticket["id"] for ticket in self.shown()["tickets"]]
        [written] = [path for path in subprocess.run(
            ("git", "-C", str(self.repo), "diff", "--name-only", "--diff-filter=A", "main", integration),
            text=True, capture_output=True, check=True).stdout.split()][:1]
        moved = self.commit_to_main(written, "écrit ailleurs, autrement\n")

        self.driver("advance")

        promotion = self.last_pass()["promotion"]
        self.assertEqual((False, "conflict"), (promotion["promoted"], promotion["cause"]))
        self.assertIn("rien n'est fusionné", promotion["reason"])
        self.assertNotIn("error", promotion)
        self.assertEqual((moved, delivered["commit"]), (self.tip("main"), self.tip(integration)))
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual(("repair", "open", repair["id"]), (repair["kind"], repair["status"], promotion["repair"]["id"]))
        self.assertEqual(repair["id"], shown["convoy"]["integration_red"]["repair"])
        # Back before the end of the Spec: neither Delivered nor accepted, and not closed.
        last = shown["convoy"]["judgement"]["answers"][-1]
        self.assertEqual(("accepted", "conflict"), (last["response"], last["voided"]["cause"]))
        self.assertEqual((None, None, "open"),
                         (shown["convoy"]["delivered"], shown["convoy"]["acceptance"], shown["convoy"]["status"]))
        self.assertFalse(shown["unruled"])
        # One repair, whatever the number of passes.
        self.order_pass()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in self.shown()["tickets"]])
        self.assertEqual(moved, self.tip("main"))


if __name__ == "__main__":
    unittest.main()
