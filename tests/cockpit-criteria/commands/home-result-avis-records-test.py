#!/usr/bin/env python3
"""Criterion test 2 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 30, 113 and 114, Implementation Decision 6 of af-2zseit kept,
Testing Decisions 1, 2 and 8), on the records of D01: the cockpit
launched, Avis, then bin/owner-answer run by the session with the message
copied.

The records are produced as Testing Decisions 2 says: the reference driver
of the Fixture City walks one convoy to its Delivered Outcome, its dossier
carrying one proposition (the harness FixtureCityWalk of
tests/convoy-stops-fixture-city-test.py, walked once and restored). The
tracker the commands wrote is the tracker of a cockpit the launcher of the
profile, bin/project-launch, starts (pour_moi.serve_tracker), walked in a
headless Chromium (result_trial.walk), which records what the page copies.

Avis prepares « accepté » only once each proposition of the dossier has its
verdict, and not while one is to do before accepting; the message is
copied, and nothing is recorded by the copy. The session then does what
the message says, and nothing else: it runs the lines of bin/owner-answer
the message holds, in the repository of the project and as its approver.
The answer recorded is then read back by the cockpit, on the records as
the command wrote them: the exact words, the commit and the fingerprint of
the dossier judged.

False if the cockpit records a judgement itself, says it recorded at the
copy, or prepares an acceptance without a verdict on each proposition.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import shlex
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import serve_tracker  # noqa: E402
from result_trial import controls, folded, last, result_of, shown, walk  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: the test classes named at the top
# of a file are the ones collected there.
stops = load("convoy-stops-fixture-city-test.py")
# bin/owner-answer, the entry point of the profile the session runs.
OWNER = ROOT / "bin" / "owner-answer"
# A line of the message that runs it, as a session reads it.
OWNER_LINE = re.compile(r"(?m)^\s*(?:\$\s*)?(?:\./)?bin/owner-answer\s.*$")
APPROVER = "benjamin"

WORDS = "Ton avis"
VERDICT = "Verdict sur la proposition"
PREPARE = "Continuer avec un agent"
COPY = "Copier pour ma session"
HISTORY = "Historique et preuves"


class HomeResultAvisRecords(stops.FixtureCityWalk):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        super().tearDownClass()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def records(self) -> dict:
        """What the commands wrote in the tracker of the city."""
        return json.loads(self.tracker.read_text(encoding="utf-8"))

    def enabled(self, page: dict, name: str) -> bool:
        found = controls(page, name)
        self.assertEqual(1, len(found), f"not one « {name} » on the page: {[c['name'] for c in page['controls']]}")
        return not found[0]["disabled"]

    def run_as_the_session(self, message: str) -> list[dict]:
        """The lines of bin/owner-answer the message holds, run one after
        the other as the session runs them: in the repository of the project
        and as its approver -- what the session knows of its own place --,
        every other argument as the message writes it. Their answers."""
        lines = OWNER_LINE.findall(message.replace("\\\n", " "))
        self.assertTrue(lines, f"the message holds no line of bin/owner-answer: {message}")
        answers = []
        for line in lines:
            argv = shlex.split(line)
            args = argv[next(i for i, word in enumerate(argv) if word.endswith("bin/owner-answer")) + 1:]
            kept, skip = [], False
            for word in args:
                if skip:
                    skip = False
                elif word in ("--repo", "--approved-by"):
                    skip = True
                else:
                    kept.append(word)
            proc = self.tool(OWNER, *kept, "--repo", self.repo, "--approved-by", APPROVER)
            self.assertEqual(0, proc.returncode, f"{line}\n{proc.stdout}{proc.stderr}")
            answers.append(json.loads(proc.stdout))
        return answers

    # --- Criterion 2 ------------------------------------------------------------

    def test_acceptance_needs_a_verdict_on_each_proposition_then_the_session_records_the_message_copied(self):
        delivered = self.walk_to_delivered(inject="proposition")
        [proposition] = [finding for ticket in self.shown()["tickets"] for finding in ticket.get("findings") or []
                         if finding["classification"] == "proposal"]
        words = "Accepté, c’est ce que je voulais pour la liste."
        address = serve_tracker(self.tree, self.records()["beads"])
        chantier, before = result_of(address)

        walked = walk(address, [
            {"click": "Avis"},                                               # 0
            {"fill": WORDS, "value": words}, {"check": "Accepté"},           # 1, 2: no verdict yet
            {"choose": VERDICT, "option": "Avant d’accepter"},               # 3
            {"choose": VERDICT, "option": "Sans suite"},                     # 4
            {"click": PREPARE},                                              # 5
            {"click": COPY},                                                 # 6
        ])
        self.assertEqual([], [i for i, step in enumerate(walked["steps"]) if not step["found"]],
                         f"a control of the walk is not on the page: {last(walked)['controls']}")
        pages = [step["page"] for step in walked["steps"]]
        self.assertIn(proposition["text"], shown(pages[2]), "Avis does not show the proposition of the dossier")
        self.assertFalse(self.enabled(pages[2], PREPARE), "« accepté » is prepared without a verdict on the proposition")
        self.assertFalse(self.enabled(pages[3], PREPARE),
                         "« accepté » is prepared while a proposition is to do before accepting")
        self.assertTrue(self.enabled(pages[4], PREPARE), "« accepté » with each verdict given cannot be prepared")

        copied = pages[6]["copied"]
        self.assertEqual(1, len(copied), "copying did not copy one message")
        message = copied[0]
        self.assertEqual(1, len([text for text in folded(pages[5], "Message pour ma session") if message in text]),
                         "the message copied is not the one prepared")
        for said in (words, delivered["commit"], delivered["pack"]):
            self.assertIn(said, message, f"the message does not carry « {said} »")
        self.assertNotRegex(message, r"(?i)recommand", "the message is not neutral")
        # The copy records nothing: the cockpit serves the result as before,
        # and the records of the city are as the commands left them.
        self.assertEqual((chantier, before), result_of(address), "the cockpit recorded something at the copy")
        unrecorded = self.shown()["convoy"]["judgement"] or {}
        self.assertEqual(([], []), (unrecorded.get("verdicts") or [], unrecorded.get("answers") or []),
                         "something was recorded before the session ran")

        # The session runs what the message says.
        self.run_as_the_session(message)
        judgement = self.shown()["convoy"]["judgement"]
        self.assertEqual([(proposition["id"], "sans_suite")],
                         [(verdict["proposition"], verdict["verdict"]) for verdict in judgement["verdicts"]])
        answer = judgement["answers"][-1]
        self.assertEqual(("accepted", words, delivered["commit"], delivered["pack"]),
                         (answer["response"], answer["words"], answer["commit"], answer["pack"]))

        # The answer recorded, read back by the cockpit.
        self.tree.stop_all()
        recorded = last(walk(serve_tracker(self.tree, self.records()["beads"]), [{"click": HISTORY}]))
        [history] = folded(recorded, HISTORY) or [""]
        self.assertIn("Réponse enregistrée", history, "the cockpit does not show the answer recorded")
        self.assertIn(words, history, "the answer is not shown in its exact words")
        self.assertIn(delivered["commit"][:7], history, "the answer is not shown with the commit judged")
        self.assertIn(delivered["pack"].removeprefix("sha256:")[:12], history,
                      "the answer is not shown with the fingerprint of the dossier judged")
        self.assertIn("Tu as accepté", shown(recorded))


if __name__ == "__main__":
    unittest.main()
